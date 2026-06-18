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
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from flask import current_app


def _safe_name(valeur: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in valeur)


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
    cmd = [exe, "--format=plain", "--no-owner", "--no-privileges", _uri_libpq(db_uri)]
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
