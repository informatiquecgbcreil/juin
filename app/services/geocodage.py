"""Géocodage des adresses participants via la Base Adresse Nationale (BAN).

API publique, gratuite et SANS authentification de l'État français
(``https://api-adresse.data.gouv.fr/search/``). On ne transmet qu'une chaîne
d'adresse — jamais le nom du participant — et l'on stocke localement les
coordonnées renvoyées. Aucune dépendance externe (urllib de la stdlib).

Garanties :
- l'adresse reste 100 % FACULTATIVE : un participant sans adresse exploitable
  est simplement « non localisé » (lat/lon NULL), jamais bloqué ;
- une erreur réseau ne fait JAMAIS échouer une requête web et n'avance pas le
  curseur : le participant reste « à géocoder » et sera retenté plus tard ;
- idempotent : on mémorise la dernière adresse résolue (``geocode_query``) et
  on ne re-géocode que si elle a changé.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from flask import current_app

from app.extensions import db
from app.utils.dates import utcnow

DEFAULT_BASE_URL = "https://api-adresse.data.gouv.fr"
DEFAULT_USER_AGENT = "AppGestion-ERP/1.0 (geocodage interne)"


class GeocodageError(RuntimeError):
    """Erreur d'appel au géocodage (réseau, HTTP, réponse invalide).

    ``retryable`` distingue un incident temporaire (réseau / 5xx / quota,
    on retentera) d'un rejet définitif (4xx : adresse non interprétable).
    """

    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


def _config() -> tuple[str, str]:
    cfg = current_app.config
    base = (cfg.get("GEOCODAGE_BASE_URL") or DEFAULT_BASE_URL).strip().rstrip("/")
    ua = (cfg.get("GEOCODAGE_USER_AGENT") or DEFAULT_USER_AGENT).strip()
    return base, ua


def geocodage_actif() -> bool:
    """Actif tant qu'une URL de base est disponible (BAN par défaut)."""
    base, _ = _config()
    return bool(base)


def construire_requete(adresse: str | None, ville: str | None) -> str:
    """Chaîne d'adresse normalisée envoyée à la BAN (et clé de détection de
    changement). L'adresse complète est facultative : avec seulement la ville,
    on géocode à la commune ; si rien n'est exploitable, on renvoie ""."""
    parts = []
    a = (adresse or "").strip()
    v = (ville or "").strip()
    if a:
        parts.append(a)
    if v:
        parts.append(v)
    q = " ".join(parts).strip()
    # La BAN exige au moins 3 caractères significatifs.
    return q if len(q) >= 3 else ""


def _requete_ban(query: str, timeout: int = 10) -> dict:
    base, ua = _config()
    if not base:
        raise GeocodageError("Géocodage non configuré (GEOCODAGE_BASE_URL).")
    url = base + "/search/?" + urllib.parse.urlencode(
        {"q": query, "limit": 1, "autocomplete": 0}
    )
    req = urllib.request.Request(
        url, headers={"User-Agent": ua, "Accept": "application/json"}, method="GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charge = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        # 4xx (sauf 429) = requête définitivement rejetée : inutile de réessayer.
        retryable = exc.code >= 500 or exc.code == 429
        raise GeocodageError(f"HTTP {exc.code} sur la BAN", retryable=retryable) from exc
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise GeocodageError(f"Erreur réseau vers la BAN : {exc}", retryable=True) from exc

    if not charge:
        return {}
    try:
        return json.loads(charge)
    except ValueError as exc:
        raise GeocodageError("Réponse non-JSON de la BAN.", retryable=False) from exc


def geocoder(adresse: str | None, ville: str | None) -> dict | None:
    """Géocode une adresse → {lat, lon, score, precision, label} ou None.

    None = aucune adresse exploitable / aucun résultat (ce n'est pas une
    erreur). Lève ``GeocodageError`` en cas d'échec réseau/HTTP.
    """
    query = construire_requete(adresse, ville)
    if not query:
        return None
    data = _requete_ban(query)
    features = (data or {}).get("features") or []
    if not features:
        return None
    f = features[0]
    coords = (f.get("geometry") or {}).get("coordinates") or []
    if len(coords) < 2:
        return None
    props = f.get("properties") or {}
    return {
        "lat": float(coords[1]),
        "lon": float(coords[0]),
        "score": props.get("score"),
        "precision": props.get("type"),
        "label": props.get("label"),
    }


def _requete_courante(p) -> str:
    return construire_requete(getattr(p, "adresse", None), getattr(p, "ville", None))


def _a_geocoder(p) -> bool:
    """Vrai si l'adresse courante diffère de la dernière résolue."""
    return (p.geocode_query or "") != _requete_courante(p)


def nombre_a_geocoder() -> int:
    from app.models import Participant

    n = 0
    for p in Participant.query.yield_per(200):
        if _a_geocoder(p):
            n += 1
    return n


def synchroniser_geocodages(limit: int = 50) -> dict:
    """Géocode (par lots) les participants dont l'adresse a changé.

    Ne lève jamais : capture les erreurs réseau, s'arrête proprement et
    laisse les participants concernés pour le prochain passage.
    """
    from app.models import Participant

    nb_localises = 0
    nb_non_localises = 0
    nb_erreurs = 0
    erreur_msg = None
    traites = 0

    for p in Participant.query.yield_per(200):
        if traites >= limit:
            break
        if not _a_geocoder(p):
            continue
        courante = _requete_courante(p)
        try:
            res = geocoder(p.adresse, p.ville)
        except GeocodageError as exc:
            if exc.retryable:
                # Réseau probablement indisponible : on arrête et on retentera.
                nb_erreurs += 1
                erreur_msg = str(exc)
                break
            # Adresse définitivement non interprétable : on marque « non localisé »
            # pour ne pas boucler dessus à chaque passage.
            res = None

        traites += 1
        if res:
            p.latitude = res["lat"]
            p.longitude = res["lon"]
            p.geocode_score = res.get("score")
            p.geocode_precision = res.get("precision")
            nb_localises += 1
        else:
            p.latitude = None
            p.longitude = None
            p.geocode_score = None
            p.geocode_precision = None
            nb_non_localises += 1
        p.geocoded_at = utcnow()
        p.geocode_query = courante

    db.session.commit()
    return {
        "localises": nb_localises,
        "non_localises": nb_non_localises,
        "erreurs": nb_erreurs,
        "erreur": erreur_msg,
        "restants": nombre_a_geocoder(),
    }
