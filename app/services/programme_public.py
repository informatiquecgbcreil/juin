"""Programme public des activités.

Produit une liste **non nominative** des ateliers collectifs à venir, destinée
à être exportée en page HTML autonome et publiée sur un site / hébergement
externe. Aucune donnée personnelle (participants) n'y figure.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.extensions import db
from app.models import AtelierActivite, SessionActivite

_JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
_MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def label_date_fr(d: date) -> str:
    return f"{_JOURS[d.weekday()]} {d.day} {_MOIS[d.month - 1]} {d.year}"


def sessions_a_venir(jours: int = 60) -> list[dict]:
    """Ateliers COLLECTIFS programmés d'aujourd'hui à +``jours``, groupés par date.

    Retourne une liste de ``{"label": "lundi 1 juin 2026", "sessions": [...]}``,
    triée par date croissante. Les rendez-vous individuels sont volontairement
    exclus (ils ne relèvent pas d'un programme public).
    """
    today = date.today()
    limite = today + timedelta(days=jours)
    sessions = (
        SessionActivite.query.filter_by(session_type="COLLECTIF")
        .filter(SessionActivite.is_deleted.is_(False))
        .filter(SessionActivite.date_session >= today)
        .filter(SessionActivite.date_session <= limite)
        .order_by(SessionActivite.date_session.asc(), SessionActivite.heure_debut.asc())
        .all()
    )

    groupes: dict[date, list[dict]] = {}
    for s in sessions:
        atelier = db.session.get(AtelierActivite, s.atelier_id)
        groupes.setdefault(s.date_session, []).append(
            {
                "atelier": atelier.nom if atelier else "Atelier",
                "secteur": s.secteur,
                "debut": s.heure_debut,
                "fin": s.heure_fin,
            }
        )

    return [
        {"label": label_date_fr(d), "sessions": items}
        for d, items in sorted(groupes.items())
    ]
