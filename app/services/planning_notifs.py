"""Notifications du planning : demande, décision, rappel.

Deux canaux, choisis au cadrage — tous deux fonctionnent en HTTP sur le LAN :
- le centre « À traiter » interne (table ``SuiviRappel``), toujours créé :
  c'est la voie fiable, visible dès la connexion ;
- l'e-mail (SMTP/Brevo), best-effort : envoyé si le SMTP est configuré,
  jamais bloquant s'il échoue.

Une « demande » prévient les valideurs (droit ``planning:approve``) ;
une décision (approbation / refus) prévient le demandeur ; un rappel
programmable prévient le demandeur avant l'échéance.
"""
from __future__ import annotations

from flask import current_app, url_for

from app.extensions import db
from app.models import SuiviRappel, User
from app.utils.dates import utcnow


def _lien(endpoint: str, **kwargs) -> str | None:
    try:
        return url_for(endpoint, **kwargs)
    except Exception:
        return None


def _emails_valideurs(secteur: str | None) -> list[str]:
    """E-mails des utilisateurs actifs pouvant approuver (dans le secteur si
    borné, sinon tous les valideurs)."""
    emails: list[str] = []
    for u in User.query.filter(User.actif.is_(True)).all():
        if not u.has_perm("planning:approve"):
            continue
        # Un valideur global voit tout ; un valideur borné à un secteur n'est
        # sollicité que pour les demandes de son secteur (ou sans secteur).
        if not u.has_perm("scope:all_secteurs") and secteur:
            if (getattr(u, "secteur_assigne", "") or "") != secteur:
                continue
        if u.email:
            emails.append(u.email)
    return emails


def _envoyer_email_sans_bloquer(destinataires: list[str], sujet: str, corps: str) -> None:
    if not destinataires:
        return
    try:
        from app.services.notifications import envoyer_email
        for adresse in destinataires:
            envoyer_email(adresse, sujet, corps)
    except Exception:
        current_app.logger.warning("Notification planning : e-mail non envoyé (SMTP ?)", exc_info=True)


def _creer_rappel_interne(*, titre: str, description: str, secteur: str | None,
                          lien_url: str | None, priorite: str = "warn") -> None:
    db.session.add(SuiviRappel(
        titre=titre[:200],
        description=description,
        categorie="planning",
        priorite=priorite,
        secteur=secteur,
        lien_url=lien_url,
    ))


def _app_name() -> str:
    return current_app.config.get("APP_NAME") or "Application"


# ---------------------------------------------------------------------------
# Événements du workflow
# ---------------------------------------------------------------------------

def notifier_demande(*, type_libelle: str, intitule: str, demandeur: str,
                     detail: str, secteur: str | None, lien_url: str | None) -> None:
    """Une demande vient d'être déposée : prévient les valideurs."""
    titre = f"À valider — {type_libelle} : {intitule}"
    corps = (
        f"Nouvelle demande de {type_libelle.lower()} à valider.\n\n"
        f"Objet : {intitule}\n{detail}\n"
        f"Demandé par : {demandeur}\n\n"
        "Ouvrez le planning pour approuver ou refuser."
    )
    _creer_rappel_interne(titre=titre, description=corps, secteur=secteur, lien_url=lien_url)
    db.session.commit()
    _envoyer_email_sans_bloquer(_emails_valideurs(secteur), f"[{_app_name()}] {titre}", corps)


def notifier_decision(*, type_libelle: str, intitule: str, approuvee: bool,
                      motif_refus: str | None, destinataire_user_id: int | None,
                      detail: str, lien_url: str | None) -> None:
    """Décision prise : prévient le demandeur (e-mail + À traiter)."""
    verdict = "approuvée ✅" if approuvee else "refusée"
    titre = f"{type_libelle} {verdict} : {intitule}"
    corps = f"Votre demande de {type_libelle.lower()} « {intitule} » a été {verdict}.\n{detail}\n"
    if not approuvee and motif_refus:
        corps += f"\nMotif du refus : {motif_refus}\n"

    demandeur = db.session.get(User, destinataire_user_id) if destinataire_user_id else None
    secteur = getattr(demandeur, "secteur_assigne", None) if demandeur else None
    _creer_rappel_interne(
        titre=titre, description=corps, secteur=secteur, lien_url=lien_url,
        priorite="info" if approuvee else "warn",
    )
    db.session.commit()
    if demandeur and demandeur.email:
        _envoyer_email_sans_bloquer([demandeur.email], f"[{_app_name()}] {titre}", corps)


def notifier_rappel(*, type_libelle: str, intitule: str, echeance, detail: str,
                    destinataire_user_id: int | None, secteur: str | None,
                    lien_url: str | None) -> None:
    titre = f"Rappel — {type_libelle} : {intitule}"
    corps = (
        f"Rappel : {type_libelle.lower()} « {intitule} » prévu(e) le "
        f"{echeance.strftime('%d/%m/%Y') if echeance else '—'}.\n{detail}\n"
    )
    _creer_rappel_interne(titre=titre, description=corps, secteur=secteur, lien_url=lien_url)
    db.session.commit()
    demandeur = db.session.get(User, destinataire_user_id) if destinataire_user_id else None
    if demandeur and demandeur.email:
        _envoyer_email_sans_bloquer([demandeur.email], f"[{_app_name()}] {titre}", corps)


# ---------------------------------------------------------------------------
# Rappels programmés (passe quotidienne)
# ---------------------------------------------------------------------------

def envoyer_rappels_du_jour() -> int:
    """Envoie les rappels dus (échéance dans <= rappel_jours_avant, non déjà
    envoyés) pour les réservations et prêts approuvés. Retourne le nombre."""
    from datetime import date, timedelta

    from app.models import PretMateriel, ReservationSalle

    envoyes = 0
    aujourd_hui = date.today()

    reservations = (
        ReservationSalle.query
        .filter(
            ReservationSalle.statut == "approuvee",
            ReservationSalle.rappel_jours_avant.isnot(None),
            ReservationSalle.rappel_envoye_at.is_(None),
            ReservationSalle.date_reservation >= aujourd_hui,
        )
        .all()
    )
    for r in reservations:
        seuil = r.date_reservation - timedelta(days=int(r.rappel_jours_avant or 0))
        if aujourd_hui >= seuil:
            notifier_rappel(
                type_libelle="Réservation de salle",
                intitule=f"{r.titre} — {r.salle.nom if r.salle else 'salle'}",
                echeance=r.date_reservation,
                detail=f"Créneau {r.heure_debut}–{r.heure_fin}.",
                destinataire_user_id=r.created_by_user_id,
                secteur=r.secteur,
                lien_url=_lien("planning.semaine", jour=r.date_reservation.isoformat()),
            )
            r.rappel_envoye_at = utcnow()
            envoyes += 1

    prets = (
        PretMateriel.query
        .filter(
            PretMateriel.statut == "approuvee",
            PretMateriel.date_retour_reel.is_(None),
            PretMateriel.rappel_jours_avant.isnot(None),
            PretMateriel.rappel_envoye_at.is_(None),
            PretMateriel.date_retour_prevue.isnot(None),
            PretMateriel.date_retour_prevue >= aujourd_hui,
        )
        .all()
    )
    for p in prets:
        seuil = p.date_retour_prevue - timedelta(days=int(p.rappel_jours_avant or 0))
        if aujourd_hui >= seuil:
            notifier_rappel(
                type_libelle="Retour de matériel",
                intitule=f"{p.item.designation if p.item else 'matériel'} — {p.emprunteur}",
                echeance=p.date_retour_prevue,
                detail=f"Prêté le {p.date_pret.strftime('%d/%m/%Y')}.",
                destinataire_user_id=p.created_by_user_id,
                secteur=p.item.secteur if p.item else None,
                lien_url=_lien("planning.prets"),
            )
            p.rappel_envoye_at = utcnow()
            envoyes += 1

    if envoyes:
        db.session.commit()
    return envoyes


def rappels_planning_quotidiens_si_necessaire() -> None:
    """Passe quotidienne (au plus une fois/jour), calquée sur la purge RGPD."""
    from app.models import TachePlanifiee

    try:
        tache = TachePlanifiee.query.filter_by(nom="planning_rappels").first()
        if tache is not None and tache.derniere_execution is not None \
                and tache.derniere_execution.date() >= utcnow().date():
            return
        if tache is None:
            tache = TachePlanifiee(nom="planning_rappels")
            db.session.add(tache)
        tache.derniere_execution = utcnow()
        db.session.commit()
        envoyer_rappels_du_jour()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Échec des rappels de planning quotidiens")
