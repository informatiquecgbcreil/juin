"""Détection d'homonymes proches à la création d'une fiche participant.

Une fiche en double fausse toutes les statistiques : ce garde-fou propose
les fiches ressemblantes AVANT de créer, sans jamais bloquer (on peut
toujours forcer la création). Partagé entre le kiosque public et la
création manuelle (/participants/new) pour un comportement identique.
"""
from __future__ import annotations

import unicodedata

from app.models import Participant


def normaliser_nom(texte: str) -> str:
    """Minuscules, sans accents ni caractères non alphabétiques."""
    texte = unicodedata.normalize("NFKD", (texte or "")).encode("ascii", "ignore").decode("ascii")
    return "".join(c for c in texte.lower() if c.isalpha())


def squelette_nom(texte: str) -> str:
    """Forme normalisée avec les lettres doublées réduites : rend identiques
    « Mohammed » et « Mohamed », « Alard » et « Allard »."""
    normalise = normaliser_nom(texte)
    out: list[str] = []
    for c in normalise:
        if not out or out[-1] != c:
            out.append(c)
    return "".join(out)


def _proches(a: str, b: str) -> bool:
    if a == b:
        return True
    if squelette_nom(a) == squelette_nom(b):
        return True
    return len(a) >= 3 and len(b) >= 3 and (a.startswith(b) or b.startswith(a))


def candidats_doublons(nom: str, prenom: str, *, exclure_id: int | None = None) -> list[Participant]:
    """Personnes proches d'un nom/prénom saisi (anti-doublons).

    Deux champs sont « proches » si, après normalisation (casse/accents) :
    identiques, mêmes squelettes (lettres doublées réduites), ou l'un préfixe
    de l'autre (>= 3 lettres). Match global si le nom ET le prénom sont
    proches, avec au moins l'un des deux strictement identique.
    """
    n, p = normaliser_nom(nom), normaliser_nom(prenom)
    if not n or not p:
        return []

    candidats: list[Participant] = []
    for cand in Participant.query.filter(Participant.nom.ilike(f"{nom[:2]}%")).limit(400).all():
        if exclure_id is not None and cand.id == exclure_id:
            continue
        cn, cp = normaliser_nom(cand.nom), normaliser_nom(cand.prenom)
        if not cn or not cp:
            continue
        if (cn == n or cp == p) and _proches(cn, n) and _proches(cp, p):
            candidats.append(cand)
        if len(candidats) >= 5:
            break
    return candidats
