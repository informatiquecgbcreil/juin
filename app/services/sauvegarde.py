"""Création et inventaire des sauvegardes de l'instance.

La logique est partagée entre :
- le script en ligne de commande ``tools/backup_instance.py`` (tâche planifiée) ;
- la page d'administration « Sauvegardes » (bouton « Sauvegarder maintenant »).

Une sauvegarde produit, dans le dossier ``backups/`` à la racine du projet :
- une copie de la base de données (fichier ``.db`` pour SQLite, dump ``.sql`` via
  ``pg_dump`` pour PostgreSQL) ;
- une archive ``.zip`` des pièces jointes (dossier d'upload).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from flask import current_app


def _safe_name(valeur: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in valeur)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for bloc in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloc)
    return h.hexdigest()


def dossier_sauvegardes() -> Path:
    """Dossier de stockage des sauvegardes (créé si besoin)."""
    out_dir = Path(current_app.root_path).parent / "backups"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _copy_sqlite(db_uri: str, cible: Path) -> None:
    src = Path(db_uri.replace("sqlite:///", "", 1))
    if not src.exists():
        raise RuntimeError(f"Base SQLite introuvable : {src}")
    shutil.copy2(src, cible)


def _uri_libpq(db_uri: str) -> str:
    """Ramène une URI SQLAlchemy PostgreSQL (``postgresql+psycopg2://…``) à la
    forme ``postgresql://…`` attendue par ``pg_dump``."""
    for prefixe in ("postgresql+psycopg2://", "postgresql+psycopg://", "postgresql+pg8000://"):
        if db_uri.startswith(prefixe):
            return "postgresql://" + db_uri[len(prefixe):]
    return db_uri


def _trouver_pg_dump() -> str | None:
    """Localise l'exécutable pg_dump, sans exiger qu'il soit dans le PATH.

    Ordre de recherche :
    1. le PATH du système ;
    2. la variable PG_DUMP_PATH (config Flask ou variable d'environnement) ;
    3. les emplacements d'installation PostgreSQL courants sous Windows
       (``C:\\Program Files\\PostgreSQL\\<version>\\bin\\pg_dump.exe``),
       version la plus récente d'abord.
    """
    exe = shutil.which("pg_dump") or shutil.which("pg_dump.exe")
    if exe:
        return exe

    configure = (
        current_app.config.get("PG_DUMP_PATH") or os.environ.get("PG_DUMP_PATH") or ""
    ).strip()
    if configure and Path(configure).exists():
        return configure

    def _version(verdir: Path) -> int:
        m = re.match(r"(\d+)", verdir.name)
        return int(m.group(1)) if m else -1

    for base in (r"C:\Program Files\PostgreSQL", r"C:\Program Files (x86)\PostgreSQL"):
        racine = Path(base)
        if not racine.exists():
            continue
        for verdir in sorted(
            (d for d in racine.iterdir() if d.is_dir()), key=_version, reverse=True
        ):
            candidat = verdir / "bin" / "pg_dump.exe"
            if candidat.exists():
                return str(candidat)
    return None


def _pg_dump(db_uri: str, cible: Path) -> None:
    exe = _trouver_pg_dump()
    if not exe:
        raise RuntimeError(
            "La commande pg_dump est introuvable. Elle est normalement fournie avec "
            "PostgreSQL (dossier « bin »). Ajoutez ce dossier au PATH du serveur, ou "
            "définissez la variable PG_DUMP_PATH avec le chemin complet vers pg_dump.exe."
        )
    # --clean --if-exists : le dump recrée proprement les objets à la
    # restauration (DROP ... IF EXISTS puis CREATE), ce qui le rend rejouable
    # via psql même sur une base déjà peuplée.
    cmd = [exe, "--format=plain", "--clean", "--if-exists",
           "--no-owner", "--no-privileges", _uri_libpq(db_uri)]
    try:
        with cible.open("wb") as f:
            proc = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE)
    except FileNotFoundError as exc:  # pg_dump introuvable malgré la détection
        raise RuntimeError(
            f"Impossible d'exécuter pg_dump ({exe}). Vérifiez l'installation de PostgreSQL."
        ) from exc
    if proc.returncode != 0:
        detail = (proc.stderr or b"").decode("utf-8", "replace").strip()
        message = "La sauvegarde PostgreSQL (pg_dump) a échoué."
        if detail:
            message += f" Détail : {detail}"
        raise RuntimeError(message)


def _zip_dossier(dossier: Path | None, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if dossier and dossier.exists():
            for p in dossier.rglob("*"):
                if p.is_file():
                    zf.write(p, p.relative_to(dossier))


def creer_sauvegarde() -> dict:
    """Crée une sauvegarde complète (base + pièces jointes).

    Retourne un dict décrivant les fichiers produits.
    Lève ``RuntimeError`` avec un message lisible en cas d'échec.
    """
    org = current_app.config.get("ORGANIZATION_NAME", "structure")
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = dossier_sauvegardes()
    base = _safe_name(f"{org}_{stamp}")

    db_uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "") or ""
    uploads_cfg = current_app.config.get("APP_UPLOAD_DIR")
    uploads = Path(uploads_cfg) if uploads_cfg else None

    if db_uri.startswith("sqlite:///"):
        db_artifact = out_dir / f"{base}.db"
        _copy_sqlite(db_uri, db_artifact)
    elif db_uri.startswith("postgresql"):
        db_artifact = out_dir / f"{base}.sql"
        _pg_dump(db_uri, db_artifact)
    else:
        type_base = db_uri.split(":", 1)[0] or "inconnu"
        raise RuntimeError(f"Type de base de données non pris en charge : {type_base}")

    uploads_zip = out_dir / f"{base}_uploads.zip"
    _zip_dossier(uploads, uploads_zip)

    # Empreintes d'intégrité (format compatible « sha256sum ») pour vérifier
    # plus tard qu'une sauvegarde n'est pas corrompue avant de la restaurer.
    sidecar = out_dir / f"{base}.sha256"
    try:
        lignes = [
            f"{_sha256(db_artifact)}  {db_artifact.name}",
            f"{_sha256(uploads_zip)}  {uploads_zip.name}",
        ]
        sidecar.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    except OSError:
        current_app.logger.warning("Empreinte d'intégrité non écrite pour %s", base)

    return {
        "base": base,
        "db_fichier": db_artifact.name,
        "uploads_fichier": uploads_zip.name,
        "horodatage": stamp,
    }


def humaniser_taille(octets: int) -> str:
    taille = float(octets)
    for unite in ("o", "Ko", "Mo", "Go", "To"):
        if taille < 1024 or unite == "To":
            return f"{int(taille)} {unite}" if unite == "o" else f"{taille:.1f} {unite}"
        taille /= 1024
    return f"{octets} o"


def lister_sauvegardes() -> list[dict]:
    """Inventaire des sauvegardes existantes, la plus récente d'abord."""
    out_dir = dossier_sauvegardes()
    items: list[dict] = []
    for p in out_dir.iterdir():
        if not p.is_file() or p.suffix.lower() not in (".db", ".sql", ".zip"):
            continue
        st = p.stat()
        items.append(
            {
                "nom": p.name,
                "taille": st.st_size,
                "taille_lisible": humaniser_taille(st.st_size),
                "modifie": dt.datetime.fromtimestamp(st.st_mtime),
                "type": "Pièces jointes" if p.name.endswith("_uploads.zip") else "Base de données",
            }
        )
    items.sort(key=lambda it: it["modifie"], reverse=True)
    return items


# --------------------------------------------------------------------------
# Lots (base + pièces jointes), intégrité, rétention et restauration.
# --------------------------------------------------------------------------
def verifier_integrite(base: str):
    """Vérifie une sauvegarde via son empreinte ``.sha256``.

    Retourne True (intègre), False (corrompue / fichier manquant) ou None
    (pas d'empreinte enregistrée — intégrité inconnue)."""
    out_dir = dossier_sauvegardes()
    sidecar = out_dir / f"{_safe_name(base)}.sha256"
    if not sidecar.exists():
        return None
    try:
        for ligne in sidecar.read_text(encoding="utf-8").splitlines():
            ligne = ligne.strip()
            if not ligne:
                continue
            attendu, _, nom = ligne.partition("  ")
            cible = out_dir / nom.strip()
            if not cible.exists() or _sha256(cible) != attendu.strip():
                return False
    except OSError:
        return False
    return True


def lister_lots() -> list[dict]:
    """Regroupe les fichiers en « lots » restaurables (base + uploads)."""
    out_dir = dossier_sauvegardes()
    lots: dict[str, dict] = {}
    for p in out_dir.iterdir():
        if not p.is_file():
            continue
        nom = p.name
        if nom.endswith("_uploads.zip"):
            base, role = nom[: -len("_uploads.zip")], "uploads"
        elif p.suffix.lower() in (".db", ".sql"):
            base, role = p.stem, "db"
        else:
            continue
        lot = lots.setdefault(
            base, {"base": base, "db_nom": None, "uploads_nom": None, "taille": 0, "modifie": None}
        )
        if role == "db":
            lot["db_nom"] = nom
        else:
            lot["uploads_nom"] = nom
        st = p.stat()
        lot["taille"] += st.st_size
        m = dt.datetime.fromtimestamp(st.st_mtime)
        if lot["modifie"] is None or m > lot["modifie"]:
            lot["modifie"] = m
    res = list(lots.values())
    for lot in res:
        lot["taille_lisible"] = humaniser_taille(lot["taille"])
        lot["complet"] = bool(lot["db_nom"] and lot["uploads_nom"])
        lot["integre"] = verifier_integrite(lot["base"])
    res.sort(key=lambda l: l["modifie"] or dt.datetime.min, reverse=True)
    return res


def derniere_sauvegarde() -> dt.datetime | None:
    lots = lister_lots()
    return lots[0]["modifie"] if lots else None


def jours_depuis_derniere() -> int | None:
    d = derniere_sauvegarde()
    if d is None:
        return None
    return (dt.datetime.now() - d).days


def nettoyer_sauvegardes(max_lots: int | None = None) -> int:
    """Conserve les ``max_lots`` lots les plus récents, supprime les plus anciens."""
    if max_lots is None:
        try:
            max_lots = int(current_app.config.get("BACKUP_RETENTION_LOTS") or 30)
        except (TypeError, ValueError):
            max_lots = 30
    lots = lister_lots()
    if len(lots) <= max_lots:
        return 0
    out_dir = dossier_sauvegardes()
    supprimes = 0
    for lot in lots[max_lots:]:
        for nom in (lot["db_nom"], lot["uploads_nom"], f"{lot['base']}.sha256"):
            if not nom:
                continue
            p = out_dir / nom
            if p.exists():
                try:
                    p.unlink()
                    supprimes += 1
                except OSError:
                    pass
    return supprimes


def _trouver_psql() -> str | None:
    exe = shutil.which("psql") or shutil.which("psql.exe")
    if exe:
        return exe
    configure = (
        current_app.config.get("PSQL_PATH") or os.environ.get("PSQL_PATH") or ""
    ).strip()
    if configure and Path(configure).exists():
        return configure
    for base in (r"C:\Program Files\PostgreSQL", r"C:\Program Files (x86)\PostgreSQL"):
        racine = Path(base)
        if not racine.exists():
            continue
        for verdir in sorted((d for d in racine.iterdir() if d.is_dir()), reverse=True):
            candidat = verdir / "bin" / "psql.exe"
            if candidat.exists():
                return str(candidat)
    return None


def _restaurer_sqlite(src_db: Path, db_uri: str) -> None:
    from app.extensions import db

    dst = Path(db_uri.replace("sqlite:///", "", 1))
    dst.parent.mkdir(parents=True, exist_ok=True)
    db.session.remove()
    db.engine.dispose()  # libère les connexions avant d'écraser le fichier
    shutil.copy2(src_db, dst)


def _restaurer_postgres(src_sql: Path, db_uri: str) -> None:
    from app.extensions import db

    exe = _trouver_psql()
    if not exe:
        raise RuntimeError(
            "La commande psql est introuvable. Ajoutez le dossier « bin » de PostgreSQL "
            "au PATH, ou définissez PSQL_PATH avec le chemin complet vers psql.exe."
        )
    db.session.remove()
    db.engine.dispose()
    cmd = [exe, _uri_libpq(db_uri), "-v", "ON_ERROR_STOP=1", "-f", str(src_sql)]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        detail = (proc.stderr or b"").decode("utf-8", "replace").strip()
        raise RuntimeError(f"La restauration PostgreSQL (psql) a échoué. Détail : {detail}")


def _restaurer_uploads(zip_file: Path, upload_dir: Path) -> None:
    upload_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_file, "r") as zf:
        zf.extractall(upload_dir)


def restaurer_lot(base: str) -> dict:
    """Restaure une sauvegarde (base + pièces jointes).

    - Vérifie l'intégrité (refuse si corrompue).
    - Crée d'ABORD une sauvegarde de sécurité de l'état courant.
    - Remplace ensuite la base et les pièces jointes.
    Lève ``RuntimeError`` avec un message lisible en cas de problème.
    """
    base = _safe_name(base)
    out_dir = dossier_sauvegardes()

    db_file = None
    for ext in (".sql", ".db"):
        cand = out_dir / f"{base}{ext}"
        if cand.exists():
            db_file = cand
            break
    uploads_file = out_dir / f"{base}_uploads.zip"
    if db_file is None or not uploads_file.exists():
        raise RuntimeError("Sauvegarde introuvable ou incomplète (base + pièces jointes requises).")

    if verifier_integrite(base) is False:
        raise RuntimeError("Contrôle d'intégrité échoué : la sauvegarde semble corrompue. Restauration annulée.")

    # Filet de sécurité : on sauvegarde l'état courant AVANT d'écraser.
    try:
        securite = creer_sauvegarde()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Sauvegarde de sécurité préalable impossible — restauration annulée ({exc}).")

    db_uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "") or ""
    upload_cfg = current_app.config.get("APP_UPLOAD_DIR")

    if db_uri.startswith("sqlite:///") and db_file.suffix.lower() == ".db":
        _restaurer_sqlite(db_file, db_uri)
    elif db_uri.startswith("postgresql") and db_file.suffix.lower() == ".sql":
        _restaurer_postgres(db_file, db_uri)
    else:
        raise RuntimeError("Type de base courant incompatible avec le fichier de sauvegarde sélectionné.")

    if upload_cfg:
        _restaurer_uploads(uploads_file, Path(upload_cfg))

    return {"base": base, "securite": securite.get("base")}
