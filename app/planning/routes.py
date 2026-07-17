"""Planning interne — vue semaine, salles & réservations, prêts, workflow.

Portée : la vue semaine et les salles sont partagées (ressources communes) —
tout titulaire de ``planning:view`` voit l'ensemble, filtre secteur optionnel.
Une demande (réservation ou prêt) est validée par un titulaire de
``planning:approve`` ; un demandeur qui a lui-même ce droit est auto-approuvé.
Les prêts touchent l'inventaire : un rôle sans ``scope:all_secteurs`` est
borné aux items de son secteur.
"""
from __future__ import annotations

from datetime import date, datetime
from io import BytesIO

from flask import flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import (
    PAIEMENT_MODES,
    PAIEMENT_MODES_LABELS,
    TARIF_UNITES,
    TARIF_UNITES_LABELS,
    InventaireItem,
    PretMateriel,
    ReservationSalle,
    Salle,
)
from app.rbac import can, require_perm
from app.services.locations import (
    cautions_a_rendre,
    construire_convention_docx,
    locations_a_encaisser,
    marquer_caution_rendue,
    marquer_paye,
    recettes_encaissees,
)
from app.services.planning import (
    ReservationInvalide,
    approuver_pret,
    approuver_reservation,
    demander_pret,
    demander_reservation,
    enregistrer_retour,
    prets_en_attente,
    prets_en_cours,
    prets_en_retard,
    refuser_pret,
    refuser_reservation,
    reservations_en_attente,
    salles_actives,
    semaine_equipe,
)
from app.services.planning_notifs import notifier_decision, notifier_demande

from . import bp

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _parse_date(brut: str | None, defaut):
    try:
        return datetime.strptime((brut or "").strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return defaut


def _secteur_filtre_optionnel() -> str | None:
    if can("scope:all_secteurs"):
        return (request.args.get("secteur") or "").strip() or None
    return (getattr(current_user, "secteur_assigne", None) or "").strip() or None


def _secteur_borne() -> str | None:
    return None if can("scope:all_secteurs") else (getattr(current_user, "secteur_assigne", None) or "")


def _peut_voir_item(item: InventaireItem) -> bool:
    if can("scope:all_secteurs"):
        return True
    return (getattr(current_user, "secteur_assigne", "") or "") == (item.secteur or "")


def _rappel_jours(champ: str) -> int | None:
    val = request.form.get(champ, type=int)
    return val if val and val > 0 else None


def _montant(champ: str) -> float | None:
    val = request.form.get(champ, type=float)
    return val if val and val > 0 else None


def _location_form() -> dict:
    """Lit les champs de location communs (réservation & prêt)."""
    return {
        "est_location": request.form.get("est_location") == "1",
        "contact": request.form.get("contact"),
        "tarif_montant": _montant("tarif_montant"),
        "tarif_unite": (request.form.get("tarif_unite") or "").strip() or None,
        "caution_montant": _montant("caution_montant"),
        "paiement_mode": (request.form.get("paiement_mode") or "").strip() or None,
    }


def _options_location() -> dict:
    """Listes (valeur, libellé) pour les menus déroulants de location."""
    return {
        "tarif_unites": [(u, TARIF_UNITES_LABELS[u]) for u in TARIF_UNITES],
        "paiement_modes": [(m, PAIEMENT_MODES_LABELS[m]) for m in PAIEMENT_MODES],
    }


def _servir_convention(obj, prefixe: str):
    doc = construire_convention_docx(obj)
    bio = BytesIO()
    doc.save(bio)
    bio.seek(0)
    return send_file(
        bio, as_attachment=True,
        download_name=f"convention_{prefixe}_{obj.id}.docx",
        mimetype=DOCX_MIME,
    )


# ---------------------------------------------------------------------------
# Vue semaine équipe
# ---------------------------------------------------------------------------

@bp.route("/")
@login_required
@require_perm("planning:view")
def semaine():
    from app.secteurs import get_secteur_labels

    jour = _parse_date(request.args.get("jour"), date.today())
    secteur = _secteur_filtre_optionnel()
    data = semaine_equipe(jour, secteur)
    a_valider = reservations_en_attente(_secteur_borne()) if can("planning:approve") else []
    return render_template(
        "planning/semaine.html",
        data=data,
        secteur=secteur,
        secteurs=get_secteur_labels(active_only=True),
        portee_globale=can("scope:all_secteurs"),
        salles=salles_actives(),
        retards=prets_en_retard(_secteur_borne()),
        a_valider=a_valider,
        heure_min=8, heure_max=21,
        today=date.today(),
        **_options_location(),
    )


# ---------------------------------------------------------------------------
# Salles
# ---------------------------------------------------------------------------

@bp.route("/salles", methods=["GET", "POST"])
@login_required
@require_perm("planning:view")
def salles():
    if request.method == "POST":
        require_perm("planning:edit")(lambda: None)()
        nom = (request.form.get("nom") or "").strip()
        if not nom:
            flash("Donnez un nom à la salle.", "danger")
            return redirect(url_for("planning.salles"))
        est_externe = request.form.get("est_externe") == "1"
        db.session.add(Salle(
            nom=nom,
            secteur=(request.form.get("secteur") or "").strip() or None,
            capacite=request.form.get("capacite", type=int),
            localisation=(request.form.get("localisation") or "").strip() or None,
            couleur=(request.form.get("couleur") or "").strip() or None,
            est_externe=est_externe,
            adresse=(request.form.get("adresse") or "").strip() or None if est_externe else None,
            contact=(request.form.get("contact") or "").strip() or None if est_externe else None,
        ))
        db.session.commit()
        flash(f"Salle « {nom} » ajoutée ✅", "success")
        return redirect(url_for("planning.salles"))

    toutes = Salle.query.order_by(Salle.actif.desc(), Salle.est_externe.asc(), Salle.nom.asc()).all()
    return render_template("planning/salles.html", salles=toutes)


@bp.route("/salles/<int:salle_id>/basculer", methods=["POST"])
@login_required
@require_perm("planning:edit")
def salle_basculer(salle_id: int):
    salle = db.get_or_404(Salle, salle_id)
    salle.actif = not salle.actif
    db.session.commit()
    flash(f"Salle « {salle.nom} » {'réactivée' if salle.actif else 'désactivée'}.", "info")
    return redirect(url_for("planning.salles"))


# ---------------------------------------------------------------------------
# Réservations : demande + décisions
# ---------------------------------------------------------------------------

@bp.route("/reservations/creer", methods=["POST"])
@login_required
@require_perm("planning:edit")
def reservation_creer():
    salle = db.session.get(Salle, request.form.get("salle_id", type=int) or 0)
    if salle is None or not salle.actif:
        flash("Choisissez une salle active.", "danger")
        return redirect(url_for("planning.semaine"))

    jour = _parse_date(request.form.get("date_reservation"), date.today())
    auto = can("planning:approve")
    loc = _location_form()
    try:
        reservation = demander_reservation(
            salle=salle,
            titre=request.form.get("titre"),
            jour=jour,
            heure_debut=(request.form.get("heure_debut") or "").strip(),
            heure_fin=(request.form.get("heure_fin") or "").strip(),
            motif=request.form.get("motif"),
            secteur=request.form.get("secteur"),
            description=request.form.get("description"),
            rappel_jours_avant=_rappel_jours("rappel_jours_avant"),
            locataire=request.form.get("locataire"),
            user=current_user,
            auto_approuver=auto,
            **loc,
        )
    except ReservationInvalide as exc:
        flash(str(exc), "warning")
        return redirect(url_for("planning.semaine", jour=jour.isoformat()))

    if reservation.statut == "approuvee":
        flash(f"« {salle.nom} » réservée le {jour.strftime('%d/%m/%Y')} ✅", "success")
    else:
        notifier_demande(
            type_libelle="Réservation de salle",
            intitule=f"{reservation.titre} — {salle.nom}",
            demandeur=getattr(current_user, "nom", None) or getattr(current_user, "email", "?"),
            detail=f"Le {jour.strftime('%d/%m/%Y')} de {reservation.heure_debut} à {reservation.heure_fin}. Motif : {reservation.motif}.",
            secteur=reservation.secteur,
            lien_url=url_for("planning.semaine", jour=jour.isoformat()),
        )
        flash("Demande de réservation envoyée pour validation ✅", "success")
    return redirect(url_for("planning.semaine", jour=jour.isoformat()))


@bp.route("/reservations/<int:reservation_id>/approuver", methods=["POST"])
@login_required
@require_perm("planning:approve")
def reservation_approuver(reservation_id: int):
    reservation = db.get_or_404(ReservationSalle, reservation_id)
    try:
        approuver_reservation(reservation, current_user)
    except ReservationInvalide as exc:
        flash(str(exc), "warning")
        return redirect(url_for("planning.semaine", jour=reservation.date_reservation.isoformat()))
    notifier_decision(
        type_libelle="Réservation de salle", approuvee=True, motif_refus=None,
        destinataire_user_id=reservation.created_by_user_id,
        intitule=f"{reservation.titre} — {reservation.salle.nom if reservation.salle else ''}",
        detail=f"Le {reservation.date_reservation.strftime('%d/%m/%Y')} de {reservation.heure_debut} à {reservation.heure_fin}.",
        lien_url=url_for("planning.semaine", jour=reservation.date_reservation.isoformat()),
    )
    flash("Réservation approuvée ✅", "success")
    return redirect(url_for("planning.semaine", jour=reservation.date_reservation.isoformat()))


@bp.route("/reservations/<int:reservation_id>/refuser", methods=["POST"])
@login_required
@require_perm("planning:approve")
def reservation_refuser(reservation_id: int):
    reservation = db.get_or_404(ReservationSalle, reservation_id)
    motif_refus = request.form.get("motif_refus")
    refuser_reservation(reservation, current_user, motif_refus)
    notifier_decision(
        type_libelle="Réservation de salle", approuvee=False, motif_refus=motif_refus,
        destinataire_user_id=reservation.created_by_user_id,
        intitule=f"{reservation.titre} — {reservation.salle.nom if reservation.salle else ''}",
        detail=f"Le {reservation.date_reservation.strftime('%d/%m/%Y')} de {reservation.heure_debut} à {reservation.heure_fin}.",
        lien_url=url_for("planning.semaine", jour=reservation.date_reservation.isoformat()),
    )
    flash("Demande refusée, le demandeur est prévenu.", "info")
    return redirect(url_for("planning.semaine", jour=reservation.date_reservation.isoformat()))


@bp.route("/reservations/<int:reservation_id>/supprimer", methods=["POST"])
@login_required
@require_perm("planning:edit")
def reservation_supprimer(reservation_id: int):
    reservation = db.get_or_404(ReservationSalle, reservation_id)
    jour = reservation.date_reservation
    db.session.delete(reservation)
    db.session.commit()
    flash("Réservation annulée.", "info")
    return redirect(url_for("planning.semaine", jour=jour.isoformat()))


# ---------------------------------------------------------------------------
# Prêts de matériel
# ---------------------------------------------------------------------------

def _items_visibles():
    q = InventaireItem.query
    if not can("scope:all_secteurs"):
        q = q.filter(InventaireItem.secteur == (getattr(current_user, "secteur_assigne", "") or ""))
    return q.order_by(InventaireItem.designation.asc()).all()


@bp.route("/prets")
@login_required
@require_perm("planning:view")
def prets():
    secteur = _secteur_borne()
    en_cours = prets_en_cours(secteur)
    en_attente = prets_en_attente(secteur) if can("planning:approve") else []
    historique = (
        PretMateriel.query
        .filter(PretMateriel.date_retour_reel.isnot(None))
        .order_by(PretMateriel.date_retour_reel.desc())
        .limit(30)
        .all()
    )
    if secteur:
        historique = [p for p in historique if p.item and p.item.secteur == secteur]
    return render_template(
        "planning/prets.html",
        en_cours=en_cours,
        retards=[p for p in en_cours if p.en_retard],
        en_attente=en_attente,
        historique=historique,
        items=_items_visibles(),
        today=date.today(),
        **_options_location(),
    )


@bp.route("/prets/creer", methods=["POST"])
@login_required
@require_perm("planning:edit")
def pret_creer():
    item = db.session.get(InventaireItem, request.form.get("item_id", type=int) or 0)
    if item is None or not _peut_voir_item(item):
        flash("Choisissez un matériel de votre périmètre.", "danger")
        return redirect(url_for("planning.prets"))

    auto = can("planning:approve")
    loc = _location_form()
    try:
        pret = demander_pret(
            item=item,
            emprunteur=request.form.get("emprunteur"),
            motif=request.form.get("motif"),
            quantite=request.form.get("quantite", type=int) or 1,
            date_pret=_parse_date(request.form.get("date_pret"), date.today()),
            date_retour_prevue=_parse_date(request.form.get("date_retour_prevue"), None) if request.form.get("date_retour_prevue") else None,
            rappel_jours_avant=_rappel_jours("rappel_jours_avant"),
            user=current_user,
            auto_approuver=auto,
            **loc,
        )
    except ReservationInvalide as exc:
        flash(str(exc), "warning")
        return redirect(url_for("planning.prets"))

    if pret.statut == "approuvee":
        flash(f"Prêt de « {item.designation} » à {pret.emprunteur} enregistré ✅", "success")
    else:
        notifier_demande(
            type_libelle="Prêt de matériel",
            intitule=f"{item.designation} — {pret.emprunteur}",
            demandeur=getattr(current_user, "nom", None) or getattr(current_user, "email", "?"),
            detail=f"Prêt du {pret.date_pret.strftime('%d/%m/%Y')}. Motif : {pret.motif}.",
            secteur=item.secteur,
            lien_url=url_for("planning.prets"),
        )
        flash("Demande de prêt envoyée pour validation ✅", "success")
    return redirect(url_for("planning.prets"))


@bp.route("/prets/<int:pret_id>/approuver", methods=["POST"])
@login_required
@require_perm("planning:approve")
def pret_approuver(pret_id: int):
    pret = db.get_or_404(PretMateriel, pret_id)
    approuver_pret(pret, current_user)
    notifier_decision(
        type_libelle="Prêt de matériel", approuvee=True, motif_refus=None,
        destinataire_user_id=pret.created_by_user_id,
        intitule=f"{pret.item.designation if pret.item else 'matériel'} — {pret.emprunteur}",
        detail=f"Prêt du {pret.date_pret.strftime('%d/%m/%Y')}.",
        lien_url=url_for("planning.prets"),
    )
    flash("Prêt approuvé ✅", "success")
    return redirect(url_for("planning.prets"))


@bp.route("/prets/<int:pret_id>/refuser", methods=["POST"])
@login_required
@require_perm("planning:approve")
def pret_refuser(pret_id: int):
    pret = db.get_or_404(PretMateriel, pret_id)
    motif_refus = request.form.get("motif_refus")
    refuser_pret(pret, current_user, motif_refus)
    notifier_decision(
        type_libelle="Prêt de matériel", approuvee=False, motif_refus=motif_refus,
        destinataire_user_id=pret.created_by_user_id,
        intitule=f"{pret.item.designation if pret.item else 'matériel'} — {pret.emprunteur}",
        detail=f"Prêt du {pret.date_pret.strftime('%d/%m/%Y')}.",
        lien_url=url_for("planning.prets"),
    )
    flash("Demande de prêt refusée, le demandeur est prévenu.", "info")
    return redirect(url_for("planning.prets"))


@bp.route("/prets/<int:pret_id>/retour", methods=["POST"])
@login_required
@require_perm("planning:edit")
def pret_retour(pret_id: int):
    pret = db.get_or_404(PretMateriel, pret_id)
    if not _peut_voir_item(pret.item):
        flash("Ce prêt n'est pas dans votre périmètre.", "danger")
        return redirect(url_for("planning.prets"))
    designation = pret.item.designation if pret.item else "matériel"
    enregistrer_retour(pret)
    flash(f"Retour de « {designation} » enregistré ✅", "success")
    return redirect(url_for("planning.prets"))


# ---------------------------------------------------------------------------
# Location payante : paiement, caution, convention, vue d'ensemble
# ---------------------------------------------------------------------------

@bp.route("/locations")
@login_required
@require_perm("planning:view")
def locations():
    secteur = _secteur_borne()
    a_encaisser = locations_a_encaisser(secteur)
    cautions = cautions_a_rendre(secteur)
    debut, fin = date.today().replace(month=1, day=1), date.today()
    recettes = recettes_encaissees(debut, fin, secteur)
    return render_template(
        "planning/locations.html",
        a_encaisser=a_encaisser,
        cautions_resa=[c for c in cautions if isinstance(c, ReservationSalle)],
        cautions_pret=[c for c in cautions if isinstance(c, PretMateriel)],
        recettes=recettes,
        annee=date.today().year,
        **_options_location(),
    )


@bp.route("/reservations/<int:reservation_id>/payer", methods=["POST"])
@login_required
@require_perm("planning:edit")
def reservation_payer(reservation_id: int):
    reservation = db.get_or_404(ReservationSalle, reservation_id)
    marquer_paye(reservation, mode=request.form.get("paiement_mode"))
    flash("Location marquée comme réglée ✅", "success")
    return redirect(request.referrer or url_for("planning.locations"))


@bp.route("/reservations/<int:reservation_id>/caution-rendue", methods=["POST"])
@login_required
@require_perm("planning:edit")
def reservation_caution(reservation_id: int):
    reservation = db.get_or_404(ReservationSalle, reservation_id)
    marquer_caution_rendue(reservation)
    flash("Caution rendue ✅", "success")
    return redirect(request.referrer or url_for("planning.locations"))


@bp.route("/reservations/<int:reservation_id>/convention")
@login_required
@require_perm("planning:view")
def reservation_convention(reservation_id: int):
    reservation = db.get_or_404(ReservationSalle, reservation_id)
    if not reservation.est_location:
        flash("Cette réservation n'est pas une location.", "warning")
        return redirect(url_for("planning.locations"))
    return _servir_convention(reservation, "salle")


@bp.route("/prets/<int:pret_id>/payer", methods=["POST"])
@login_required
@require_perm("planning:edit")
def pret_payer(pret_id: int):
    pret = db.get_or_404(PretMateriel, pret_id)
    marquer_paye(pret, mode=request.form.get("paiement_mode"))
    flash("Location marquée comme réglée ✅", "success")
    return redirect(request.referrer or url_for("planning.locations"))


@bp.route("/prets/<int:pret_id>/caution-rendue", methods=["POST"])
@login_required
@require_perm("planning:edit")
def pret_caution(pret_id: int):
    pret = db.get_or_404(PretMateriel, pret_id)
    marquer_caution_rendue(pret)
    flash("Caution rendue ✅", "success")
    return redirect(request.referrer or url_for("planning.locations"))


@bp.route("/prets/<int:pret_id>/convention")
@login_required
@require_perm("planning:view")
def pret_convention(pret_id: int):
    pret = db.get_or_404(PretMateriel, pret_id)
    if not pret.est_location:
        flash("Ce prêt n'est pas une location.", "warning")
        return redirect(url_for("planning.locations"))
    return _servir_convention(pret, "materiel")
