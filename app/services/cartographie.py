"""Agrégation géographique des participants pour la carte (par quartier).

RGPD : on n'expose JAMAIS un domicile individuel. Les participants
géolocalisés sont regroupés par quartier ; le point d'un quartier est le
centroïde (moyenne) des points de ses habitants localisés. Les participants
localisés sans quartier forment un groupe « Sans quartier ». Les participants
non géolocalisés sont seulement comptés (jamais positionnés).
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import extract

from app.extensions import db
from app.models import Participant, Quartier

# Centre de Creil par défaut (utilisé si aucun participant n'est localisé).
CENTRE_DEFAUT = {"lat": 49.2583, "lon": 2.4750}


def repartition_par_quartier(secteur=None, type_public=None, annee=None) -> dict:
    """Retourne l'agrégat par quartier, prêt à sérialiser en JSON pour la carte.

    Filtres optionnels : ``secteur`` (Participant.created_secteur),
    ``type_public`` (Participant.type_public), ``annee`` (année de création).
    """
    q = Participant.query
    if type_public:
        q = q.filter(Participant.type_public == type_public)
    if secteur:
        q = q.filter(Participant.created_secteur == secteur)
    if annee:
        try:
            q = q.filter(extract("year", Participant.created_at) == int(annee))
        except (TypeError, ValueError):
            pass

    participants = q.all()
    quartiers = {qq.id: qq for qq in Quartier.query.all()}

    groupes: dict = {}
    non_localises = 0
    total = 0
    for p in participants:
        total += 1
        if p.latitude is None or p.longitude is None:
            non_localises += 1
            continue
        # Regroupement par quartier si renseigné, sinon par commune (ville),
        # pour que les habitants hors quartier restent lisibles sur la carte.
        if p.quartier_id:
            cle = ("q", p.quartier_id)
        elif (p.ville or "").strip():
            cle = ("v", p.ville.strip())
        else:
            cle = ("sans",)
        g = groupes.get(cle)
        if g is None:
            if cle[0] == "q":
                qq = quartiers.get(cle[1])
                nom = qq.nom if qq else "Quartier inconnu"
                ville = qq.ville if qq else ""
                is_qpv = bool(qq.is_qpv) if qq else False
            elif cle[0] == "v":
                nom, ville, is_qpv = cle[1], cle[1], False
            else:
                nom, ville, is_qpv = "Sans localisation", "", False
            g = groupes[cle] = {
                "id": cle[1] if cle[0] == "q" else None,
                "nom": nom,
                "ville": ville,
                "is_qpv": is_qpv,
                "total": 0,
                "_lat": 0.0,
                "_lon": 0.0,
                "par_secteur": defaultdict(int),
                "par_type_public": defaultdict(int),
            }
        g["total"] += 1
        g["_lat"] += p.latitude
        g["_lon"] += p.longitude
        g["par_secteur"][p.created_secteur or "—"] += 1
        g["par_type_public"][p.type_public or "—"] += 1

    quartiers_out = []
    for g in groupes.values():
        n = g["total"] or 1
        quartiers_out.append(
            {
                "id": g["id"],
                "nom": g["nom"],
                "ville": g["ville"],
                "is_qpv": g["is_qpv"],
                "lat": round(g["_lat"] / n, 6),
                "lon": round(g["_lon"] / n, 6),
                "total": g["total"],
                "par_secteur": dict(sorted(g["par_secteur"].items(), key=lambda x: -x[1])),
                "par_type_public": dict(sorted(g["par_type_public"].items(), key=lambda x: -x[1])),
            }
        )
    quartiers_out.sort(key=lambda x: -x["total"])

    if quartiers_out:
        centre = {
            "lat": sum(x["lat"] for x in quartiers_out) / len(quartiers_out),
            "lon": sum(x["lon"] for x in quartiers_out) / len(quartiers_out),
        }
    else:
        centre = dict(CENTRE_DEFAUT)

    return {
        "centre": centre,
        "quartiers": quartiers_out,
        "total": total,
        "localises": total - non_localises,
        "non_localises": non_localises,
    }


def liste_partenaires(secteur=None) -> dict:
    """Liste des partenaires géolocalisés (un point cliquable par structure).

    Contrairement aux habitants, un partenaire est une structure (information
    publique) : on affiche donc des marqueurs individuels. Filtre optionnel
    par secteur d'intervention.
    """
    from flask import has_request_context, url_for

    from app.models import Partenaire, PartenaireSecteur

    def _fiche_url(pid):
        # url_for nécessite un contexte de requête ; hors requête (tâche/tests),
        # on construit le chemin relatif (le préfixe du blueprint est fixe).
        if has_request_context():
            return url_for("partenaires.edit", partenaire_id=pid)
        return f"/partenaires/{pid}/edit"

    try:
        from app.partenaires.routes import ORIENTATION_DOMAINES
    except Exception:  # pragma: no cover - dégradation si import indisponible
        ORIENTATION_DOMAINES = {}

    q = Partenaire.query
    if secteur:
        q = q.join(PartenaireSecteur).filter(PartenaireSecteur.secteur == secteur)
    partenaires = q.order_by(Partenaire.nom.asc()).distinct().all()

    points = []
    non_localises = 0
    for p in partenaires:
        if p.latitude is None or p.longitude is None:
            non_localises += 1
            continue
        points.append(
            {
                "id": p.id,
                "nom": p.nom,
                "adresse": p.adresse,
                "lat": p.latitude,
                "lon": p.longitude,
                "secteurs": [s.secteur for s in p.secteurs],
                "competences": [ORIENTATION_DOMAINES.get(c, c) for c in p.competences_orientation()],
                "tel": p.tel_general or p.tel_contact,
                "email": p.email_general or p.email_contact,
                "fiche_url": _fiche_url(p.id),
            }
        )

    if points:
        centre = {
            "lat": sum(x["lat"] for x in points) / len(points),
            "lon": sum(x["lon"] for x in points) / len(points),
        }
    else:
        centre = dict(CENTRE_DEFAUT)

    return {
        "centre": centre,
        "partenaires": points,
        "total": len(partenaires),
        "localises": len(points),
        "non_localises": non_localises,
    }
