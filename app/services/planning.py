"""Planning interne — salles, réservations (conflits) et prêts de matériel.

Trois briques :
- réservations de salles avec détection de conflit (même salle, même jour,
  créneaux qui se chevauchent) ;
- vue « semaine équipe » agrégeant séances d'ateliers et réservations de
  salles sur 7 jours ;
- prêts de matériel de l'inventaire (sortie / retour), avec repérage des
  retards.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func

from app.extensions import db
from app.models import (
    AtelierActivite,
    PretMateriel,
    ReservationSalle,
    Salle,
    SessionActivite,
    _hhmm_en_minutes,
)


# ---------------------------------------------------------------------------
# Salles & réservations
# ---------------------------------------------------------------------------

def salles_actives() -> list[Salle]:
    return Salle.query.filter_by(actif=True).order_by(Salle.nom.asc()).all()


def lundi_de(jour: date) -> date:
    """Lundi de la semaine contenant ``jour``."""
    return jour - timedelta(days=jour.weekday())


def _chevauche(debut_a: int, fin_a: int, debut_b: int, fin_b: int) -> bool:
    """Deux créneaux [début, fin[ (en minutes) se chevauchent-ils ?"""
    return debut_a < fin_b and debut_b < fin_a


def conflits_reservation(
    salle_id: int,
    jour: date,
    heure_debut: str,
    heure_fin: str,
    exclure_id: int | None = None,
) -> list[ReservationSalle]:
    """Réservations existantes de la salle qui chevauchent le créneau proposé."""
    debut = _hhmm_en_minutes(heure_debut)
    fin = _hhmm_en_minutes(heure_fin)
    q = ReservationSalle.query.filter(
        ReservationSalle.salle_id == salle_id,
        ReservationSalle.date_reservation == jour,
    )
    if exclure_id is not None:
        q = q.filter(ReservationSalle.id != exclure_id)
    return [
        r for r in q.all()
        if _chevauche(debut, fin, r.debut_minutes, r.fin_minutes)
    ]


class ReservationInvalide(ValueError):
    """Erreur métier à afficher telle quelle (créneau, conflit…)."""


def creer_reservation(
    *,
    salle: Salle,
    titre: str,
    jour: date,
    heure_debut: str,
    heure_fin: str,
    secteur: str | None = None,
    description: str | None = None,
    session_id: int | None = None,
    user_id: int | None = None,
) -> ReservationSalle:
    """Crée une réservation après contrôle du créneau et des conflits."""
    titre = (titre or "").strip()
    if not titre:
        raise ReservationInvalide("Donnez un intitulé à la réservation.")
    if _hhmm_en_minutes(heure_fin) <= _hhmm_en_minutes(heure_debut):
        raise ReservationInvalide("L'heure de fin doit être après l'heure de début.")

    conflits = conflits_reservation(salle.id, jour, heure_debut, heure_fin)
    if conflits:
        c = conflits[0]
        raise ReservationInvalide(
            f"« {salle.nom} » est déjà réservée le {jour.strftime('%d/%m/%Y')} "
            f"de {c.heure_debut} à {c.heure_fin} ({c.titre}). Choisissez un autre "
            "créneau ou une autre salle."
        )

    reservation = ReservationSalle(
        salle_id=salle.id,
        titre=titre,
        date_reservation=jour,
        heure_debut=heure_debut,
        heure_fin=heure_fin,
        secteur=(secteur or "").strip() or None,
        description=(description or "").strip() or None,
        session_id=session_id,
        created_by_user_id=user_id,
    )
    db.session.add(reservation)
    db.session.commit()
    return reservation


# ---------------------------------------------------------------------------
# Vue semaine équipe
# ---------------------------------------------------------------------------

def semaine_equipe(jour: date, secteur: str | None = None) -> dict:
    """Séances d'ateliers + réservations de salles sur la semaine de ``jour``.

    Retourne 7 jours, chacun avec ses éléments triés par heure de début.
    """
    lundi = lundi_de(jour)
    dimanche = lundi + timedelta(days=6)

    date_eff = func.coalesce(SessionActivite.rdv_date, SessionActivite.date_session)
    sessions_q = (
        db.session.query(SessionActivite, AtelierActivite)
        .join(AtelierActivite, AtelierActivite.id == SessionActivite.atelier_id)
        .filter(
            SessionActivite.is_deleted.is_(False),
            AtelierActivite.is_deleted.is_(False),
            date_eff >= lundi,
            date_eff <= dimanche,
        )
    )
    if secteur:
        sessions_q = sessions_q.filter(SessionActivite.secteur == secteur)

    reservations_q = ReservationSalle.query.filter(
        ReservationSalle.date_reservation >= lundi,
        ReservationSalle.date_reservation <= dimanche,
    )
    if secteur:
        reservations_q = reservations_q.filter(
            db.or_(ReservationSalle.secteur == secteur, ReservationSalle.secteur.is_(None))
        )

    par_jour: dict[date, list[dict]] = {lundi + timedelta(days=i): [] for i in range(7)}

    for session, atelier in sessions_q.all():
        jour_s = session.rdv_date or session.date_session
        if jour_s not in par_jour:
            continue
        debut = session.heure_debut or session.rdv_debut or ""
        fin = session.heure_fin or session.rdv_fin or ""
        annulee = (session.statut or "").strip().lower() == "annulee"
        par_jour[jour_s].append({
            "type": "seance",
            "titre": atelier.nom,
            "secteur": session.secteur,
            "heure_debut": debut,
            "heure_fin": fin,
            "tri": _hhmm_en_minutes(debut),
            "annulee": annulee,
            "session_id": session.id,
            "salle": None,
        })

    for r in reservations_q.all():
        if r.date_reservation not in par_jour:
            continue
        par_jour[r.date_reservation].append({
            "type": "reservation",
            "titre": r.titre,
            "secteur": r.secteur,
            "heure_debut": r.heure_debut,
            "heure_fin": r.heure_fin,
            "tri": r.debut_minutes,
            "annulee": False,
            "reservation_id": r.id,
            "salle": r.salle.nom if r.salle else None,
            "couleur": r.salle.couleur if r.salle else None,
        })

    jours = []
    for i in range(7):
        j = lundi + timedelta(days=i)
        elements = sorted(par_jour[j], key=lambda e: (e["tri"], e["titre"]))
        jours.append({
            "date": j,
            "is_today": j == date.today(),
            "elements": elements,
            "nb_seances": sum(1 for e in elements if e["type"] == "seance"),
            "nb_reservations": sum(1 for e in elements if e["type"] == "reservation"),
        })

    return {
        "lundi": lundi,
        "dimanche": dimanche,
        "semaine_precedente": lundi - timedelta(days=7),
        "semaine_suivante": lundi + timedelta(days=7),
        "jours": jours,
    }


# ---------------------------------------------------------------------------
# Prêts de matériel
# ---------------------------------------------------------------------------

def prets_en_cours(secteur: str | None = None) -> list[PretMateriel]:
    from app.models import InventaireItem

    q = PretMateriel.query.filter(PretMateriel.date_retour_reel.is_(None))
    if secteur:
        q = q.join(InventaireItem).filter(InventaireItem.secteur == secteur)
    return q.order_by(PretMateriel.date_retour_prevue.asc().nullslast(),
                      PretMateriel.date_pret.asc()).all()


def prets_en_retard(secteur: str | None = None) -> list[PretMateriel]:
    return [p for p in prets_en_cours(secteur) if p.en_retard]


def enregistrer_retour(pret: PretMateriel, jour: date | None = None) -> None:
    pret.date_retour_reel = jour or date.today()
    db.session.commit()
