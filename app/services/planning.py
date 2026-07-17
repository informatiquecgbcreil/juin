"""Planning interne — salles, réservations (workflow + conflits), prêts.

Workflow demande -> approbation : une demande (réservation ou prêt) part en
statut ``demandee`` ; un valideur (droit ``planning:approve``) l'approuve ou
la refuse. Un demandeur qui a lui-même le droit d'approuver voit sa demande
auto-approuvée (pas de validation à blanc de soi-même).

Conflits : seules les réservations ``approuvee`` bloquent réellement un
créneau ; les ``demandee`` en attente sont signalées mais n'empêchent pas de
déposer une autre demande (le valideur arbitre).
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
from app.utils.dates import utcnow


class ReservationInvalide(ValueError):
    """Erreur métier à afficher telle quelle (créneau, conflit…)."""


def _valider_location(est_location: bool, tarif_montant, locataire) -> float | None:
    """Contrôle la cohérence d'une location. Renvoie le montant nettoyé (ou None
    si opération gratuite)."""
    if not est_location:
        return None
    try:
        montant = float(tarif_montant) if tarif_montant not in (None, "") else 0.0
    except (TypeError, ValueError):
        montant = 0.0
    if montant <= 0:
        raise ReservationInvalide("Indiquez le montant de la location (supérieur à 0).")
    if not (locataire or "").strip():
        raise ReservationInvalide("Indiquez le nom du locataire.")
    return round(montant, 2)


# ---------------------------------------------------------------------------
# Salles
# ---------------------------------------------------------------------------

def salles_actives() -> list[Salle]:
    return Salle.query.filter_by(actif=True).order_by(
        Salle.est_externe.asc(), Salle.nom.asc()
    ).all()


def lundi_de(jour: date) -> date:
    return jour - timedelta(days=jour.weekday())


# ---------------------------------------------------------------------------
# Réservations & conflits
# ---------------------------------------------------------------------------

def _chevauche(debut_a: int, fin_a: int, debut_b: int, fin_b: int) -> bool:
    return debut_a < fin_b and debut_b < fin_a


def _agencer_en_colonnes(elements: list[dict]) -> None:
    """Place les éléments « horodatés » en colonnes côte à côte, façon agenda.

    Mute chaque élément ayant un vrai créneau (``fin_min > debut_min``) en lui
    ajoutant ``lane`` (index de colonne, base 0) et ``lanes`` (nombre de
    colonnes du groupe qui se chevauchent), pour un affichage sans recouvrement
    visuel. Les éléments sans horaire sont ignorés (rendus à part)."""
    timed = sorted(
        (e for e in elements if e.get("fin_min", 0) > e.get("debut_min", 0)),
        key=lambda e: (e["debut_min"], e["fin_min"]),
    )
    i, n = 0, len(timed)
    while i < n:
        cluster = [timed[i]]
        cluster_fin = timed[i]["fin_min"]
        j = i + 1
        while j < n and timed[j]["debut_min"] < cluster_fin:
            cluster.append(timed[j])
            cluster_fin = max(cluster_fin, timed[j]["fin_min"])
            j += 1
        lanes_fin: list[int] = []
        for e in cluster:
            for k, fin in enumerate(lanes_fin):
                if fin <= e["debut_min"]:
                    e["lane"] = k
                    lanes_fin[k] = e["fin_min"]
                    break
            else:
                e["lane"] = len(lanes_fin)
                lanes_fin.append(e["fin_min"])
        for e in cluster:
            e["lanes"] = len(lanes_fin)
        i = j


def conflits_reservation(
    salle_id: int,
    jour: date,
    heure_debut: str,
    heure_fin: str,
    exclure_id: int | None = None,
    statuts: tuple[str, ...] = ("demandee", "approuvee"),
) -> list[ReservationSalle]:
    """Réservations de la salle (aux statuts donnés) chevauchant le créneau."""
    debut, fin = _hhmm_en_minutes(heure_debut), _hhmm_en_minutes(heure_fin)
    q = ReservationSalle.query.filter(
        ReservationSalle.salle_id == salle_id,
        ReservationSalle.date_reservation == jour,
        ReservationSalle.statut.in_(statuts),
    )
    if exclure_id is not None:
        q = q.filter(ReservationSalle.id != exclure_id)
    return [r for r in q.all() if _chevauche(debut, fin, r.debut_minutes, r.fin_minutes)]


def demander_reservation(
    *,
    salle: Salle,
    titre: str,
    jour: date,
    heure_debut: str,
    heure_fin: str,
    motif: str,
    secteur: str | None = None,
    description: str | None = None,
    rappel_jours_avant: int | None = None,
    est_location: bool = False,
    locataire: str | None = None,
    contact: str | None = None,
    tarif_montant: float | None = None,
    tarif_unite: str | None = None,
    caution_montant: float | None = None,
    paiement_mode: str | None = None,
    user=None,
    auto_approuver: bool = False,
) -> ReservationSalle:
    """Dépose une demande de réservation (ou l'approuve directement).

    Si ``est_location`` : mise à disposition facturée (tarif obligatoire).
    """
    titre = (titre or "").strip()
    motif = (motif or "").strip()
    if not titre:
        raise ReservationInvalide("Donnez un intitulé à la réservation.")
    if not motif:
        raise ReservationInvalide("Indiquez le motif de la demande.")
    if _hhmm_en_minutes(heure_fin) <= _hhmm_en_minutes(heure_debut):
        raise ReservationInvalide("L'heure de fin doit être après l'heure de début.")
    tarif_montant = _valider_location(est_location, tarif_montant, locataire)

    # Un créneau déjà APPROUVÉ bloque, quel que soit le statut de la demande.
    conflits = conflits_reservation(salle.id, jour, heure_debut, heure_fin, statuts=("approuvee",))
    if conflits:
        c = conflits[0]
        raise ReservationInvalide(
            f"« {salle.nom} » est déjà réservée (approuvée) le {jour.strftime('%d/%m/%Y')} "
            f"de {c.heure_debut} à {c.heure_fin} ({c.titre}). Choisissez un autre créneau."
        )

    reservation = ReservationSalle(
        salle_id=salle.id,
        titre=titre,
        date_reservation=jour,
        heure_debut=heure_debut,
        heure_fin=heure_fin,
        motif=motif,
        secteur=(secteur or "").strip() or None,
        description=(description or "").strip() or None,
        rappel_jours_avant=rappel_jours_avant,
        est_location=bool(est_location),
        locataire=(locataire or "").strip() or None if est_location else None,
        contact=(contact or "").strip() or None if est_location else None,
        tarif_montant=tarif_montant,
        tarif_unite=(tarif_unite or "").strip() or None if est_location else None,
        caution_montant=caution_montant if est_location else None,
        paiement_mode=(paiement_mode or "").strip() or None if est_location else None,
        statut="approuvee" if auto_approuver else "demandee",
        created_by_user_id=getattr(user, "id", None),
    )
    if auto_approuver:
        reservation.approuve_par_user_id = getattr(user, "id", None)
        reservation.date_decision = utcnow()
    db.session.add(reservation)
    db.session.commit()
    return reservation


def approuver_reservation(reservation: ReservationSalle, approbateur=None) -> None:
    """Approuve une demande (re-contrôle le conflit avec les approuvées)."""
    conflits = conflits_reservation(
        reservation.salle_id, reservation.date_reservation,
        reservation.heure_debut, reservation.heure_fin,
        exclure_id=reservation.id, statuts=("approuvee",),
    )
    if conflits:
        c = conflits[0]
        raise ReservationInvalide(
            f"Impossible d'approuver : le créneau est déjà pris par « {c.titre} » "
            f"({c.heure_debut}–{c.heure_fin}). Refusez ou déplacez la demande."
        )
    reservation.statut = "approuvee"
    reservation.approuve_par_user_id = getattr(approbateur, "id", None)
    reservation.date_decision = utcnow()
    reservation.motif_refus = None
    db.session.commit()


def refuser_reservation(reservation: ReservationSalle, approbateur=None, motif_refus: str | None = None) -> None:
    reservation.statut = "refusee"
    reservation.approuve_par_user_id = getattr(approbateur, "id", None)
    reservation.date_decision = utcnow()
    reservation.motif_refus = (motif_refus or "").strip() or None
    db.session.commit()


def reservations_en_attente(secteur: str | None = None) -> list[ReservationSalle]:
    q = ReservationSalle.query.filter(ReservationSalle.statut == "demandee")
    if secteur:
        q = q.filter(db.or_(ReservationSalle.secteur == secteur, ReservationSalle.secteur.is_(None)))
    return q.order_by(ReservationSalle.date_reservation.asc(), ReservationSalle.heure_debut.asc()).all()


# ---------------------------------------------------------------------------
# Vue semaine équipe
# ---------------------------------------------------------------------------

def semaine_equipe(jour: date, secteur: str | None = None) -> dict:
    """Séances d'ateliers + réservations (approuvées et en attente) sur la
    semaine de ``jour``. Chaque jour porte ses éléments triés par heure."""
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
        ReservationSalle.statut.in_(("demandee", "approuvee")),
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
        par_jour[jour_s].append({
            "type": "seance",
            "titre": atelier.nom,
            "secteur": session.secteur,
            "heure_debut": debut,
            "heure_fin": fin,
            "debut_min": _hhmm_en_minutes(debut),
            "fin_min": _hhmm_en_minutes(fin),
            "annulee": (session.statut or "").strip().lower() == "annulee",
            "statut": "seance",
            "session_id": session.id,
            "salle": None,
            "couleur": "#94a3b8",
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
            "debut_min": r.debut_minutes,
            "fin_min": r.fin_minutes,
            "annulee": False,
            "statut": r.statut,
            "reservation_id": r.id,
            "salle": r.salle.nom if r.salle else None,
            "couleur": (r.salle.couleur if r.salle else None) or "#2563eb",
        })

    jours = []
    for i in range(7):
        j = lundi + timedelta(days=i)
        elements = sorted(par_jour[j], key=lambda e: (e["debut_min"], e["titre"]))
        _agencer_en_colonnes(elements)
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

def demander_pret(
    *,
    item,
    emprunteur: str,
    motif: str,
    quantite: int = 1,
    date_pret: date | None = None,
    date_retour_prevue: date | None = None,
    rappel_jours_avant: int | None = None,
    notes: str | None = None,
    est_location: bool = False,
    contact: str | None = None,
    tarif_montant: float | None = None,
    tarif_unite: str | None = None,
    caution_montant: float | None = None,
    paiement_mode: str | None = None,
    user=None,
    auto_approuver: bool = False,
) -> PretMateriel:
    emprunteur = (emprunteur or "").strip()
    motif = (motif or "").strip()
    if not emprunteur:
        raise ReservationInvalide("Indiquez qui emprunte le matériel.")
    if not motif:
        raise ReservationInvalide("Indiquez le motif de la demande.")
    tarif_montant = _valider_location(est_location, tarif_montant, emprunteur)

    pret = PretMateriel(
        item_id=item.id,
        emprunteur=emprunteur,
        motif=motif,
        quantite=max(1, int(quantite or 1)),
        date_pret=date_pret or date.today(),
        date_retour_prevue=date_retour_prevue,
        rappel_jours_avant=rappel_jours_avant,
        notes=(notes or "").strip() or None,
        est_location=bool(est_location),
        contact=(contact or "").strip() or None if est_location else None,
        tarif_montant=tarif_montant,
        tarif_unite=(tarif_unite or "").strip() or None if est_location else None,
        caution_montant=caution_montant if est_location else None,
        paiement_mode=(paiement_mode or "").strip() or None if est_location else None,
        statut="approuvee" if auto_approuver else "demandee",
        created_by_user_id=getattr(user, "id", None),
    )
    if auto_approuver:
        pret.approuve_par_user_id = getattr(user, "id", None)
        pret.date_decision = utcnow()
    db.session.add(pret)
    db.session.commit()
    return pret


def approuver_pret(pret: PretMateriel, approbateur=None) -> None:
    pret.statut = "approuvee"
    pret.approuve_par_user_id = getattr(approbateur, "id", None)
    pret.date_decision = utcnow()
    pret.motif_refus = None
    db.session.commit()


def refuser_pret(pret: PretMateriel, approbateur=None, motif_refus: str | None = None) -> None:
    pret.statut = "refusee"
    pret.approuve_par_user_id = getattr(approbateur, "id", None)
    pret.date_decision = utcnow()
    pret.motif_refus = (motif_refus or "").strip() or None
    db.session.commit()


def _join_secteur(q, secteur: str | None):
    from app.models import InventaireItem
    if secteur:
        q = q.join(InventaireItem).filter(InventaireItem.secteur == secteur)
    return q


def prets_en_cours(secteur: str | None = None) -> list[PretMateriel]:
    q = PretMateriel.query.filter(
        PretMateriel.statut == "approuvee",
        PretMateriel.date_retour_reel.is_(None),
    )
    q = _join_secteur(q, secteur)
    return q.order_by(PretMateriel.date_retour_prevue.asc().nullslast(),
                      PretMateriel.date_pret.asc()).all()


def prets_en_retard(secteur: str | None = None) -> list[PretMateriel]:
    return [p for p in prets_en_cours(secteur) if p.en_retard]


def prets_en_attente(secteur: str | None = None) -> list[PretMateriel]:
    q = PretMateriel.query.filter(PretMateriel.statut == "demandee")
    q = _join_secteur(q, secteur)
    return q.order_by(PretMateriel.date_pret.asc()).all()


def enregistrer_retour(pret: PretMateriel, jour: date | None = None) -> None:
    pret.date_retour_reel = jour or date.today()
    db.session.commit()
