"""Planning interne — vue semaine, salles & réservations, prêts de matériel.

Portée : la vue semaine et les salles sont partagées (ressources communes du
bâtiment) — tout titulaire de ``planning:view`` voit l'ensemble, avec un
filtre secteur optionnel. Les prêts touchent des items d'inventaire : un rôle
sans ``scope:all_secteurs`` est borné aux items de son secteur.
"""
from __future__ import annotations

from datetime import date, datetime

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import InventaireItem, PretMateriel, ReservationSalle, Salle
from app.rbac import can, require_perm
from app.services.planning import (
    ReservationInvalide,
    creer_reservation,
    enregistrer_retour,
    prets_en_cours,
    prets_en_retard,
    salles_actives,
    semaine_equipe,
)

from . import bp


def _parse_date(brut: str | None, defaut: date) -> date:
    try:
        return datetime.strptime((brut or "").strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return defaut


def _secteur_filtre_optionnel() -> str | None:
    """Filtre secteur choisi (portée globale) ou secteur assigné (borné)."""
    if can("scope:all_secteurs"):
        return (request.args.get("secteur") or "").strip() or None
    return (getattr(current_user, "secteur_assigne", None) or "").strip() or None


def _peut_voir_item(item: InventaireItem) -> bool:
    if can("scope:all_secteurs"):
        return True
    return (getattr(current_user, "secteur_assigne", "") or "") == (item.secteur or "")


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
    return render_template(
        "planning/semaine.html",
        data=data,
        secteur=secteur,
        secteurs=get_secteur_labels(active_only=True),
        portee_globale=can("scope:all_secteurs"),
        salles=salles_actives(),
        retards=prets_en_retard(None if can("scope:all_secteurs") else secteur),
        today=date.today(),
    )


# ---------------------------------------------------------------------------
# Salles & réservations
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
        db.session.add(Salle(
            nom=nom,
            secteur=(request.form.get("secteur") or "").strip() or None,
            capacite=request.form.get("capacite", type=int),
            localisation=(request.form.get("localisation") or "").strip() or None,
            couleur=(request.form.get("couleur") or "").strip() or None,
        ))
        db.session.commit()
        flash(f"Salle « {nom} » ajoutée ✅", "success")
        return redirect(url_for("planning.salles"))

    toutes = Salle.query.order_by(Salle.actif.desc(), Salle.nom.asc()).all()
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


@bp.route("/reservations/creer", methods=["POST"])
@login_required
@require_perm("planning:edit")
def reservation_creer():
    salle = db.session.get(Salle, request.form.get("salle_id", type=int) or 0)
    if salle is None or not salle.actif:
        flash("Choisissez une salle active.", "danger")
        return redirect(url_for("planning.semaine"))

    jour = _parse_date(request.form.get("date_reservation"), date.today())
    try:
        creer_reservation(
            salle=salle,
            titre=request.form.get("titre"),
            jour=jour,
            heure_debut=(request.form.get("heure_debut") or "").strip(),
            heure_fin=(request.form.get("heure_fin") or "").strip(),
            secteur=request.form.get("secteur"),
            description=request.form.get("description"),
            user_id=getattr(current_user, "id", None),
        )
        flash(f"« {salle.nom} » réservée le {jour.strftime('%d/%m/%Y')} ✅", "success")
    except ReservationInvalide as exc:
        flash(str(exc), "warning")
    return redirect(url_for("planning.semaine", jour=jour.isoformat()))


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
    secteur = None if can("scope:all_secteurs") else (getattr(current_user, "secteur_assigne", None) or "")
    en_cours = prets_en_cours(secteur)
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
        historique=historique,
        items=_items_visibles(),
        today=date.today(),
    )


@bp.route("/prets/creer", methods=["POST"])
@login_required
@require_perm("planning:edit")
def pret_creer():
    item = db.session.get(InventaireItem, request.form.get("item_id", type=int) or 0)
    emprunteur = (request.form.get("emprunteur") or "").strip()
    if item is None or not _peut_voir_item(item):
        flash("Choisissez un matériel de votre périmètre.", "danger")
        return redirect(url_for("planning.prets"))
    if not emprunteur:
        flash("Indiquez qui emprunte le matériel.", "danger")
        return redirect(url_for("planning.prets"))

    db.session.add(PretMateriel(
        item_id=item.id,
        emprunteur=emprunteur,
        quantite=max(1, request.form.get("quantite", type=int) or 1),
        date_pret=_parse_date(request.form.get("date_pret"), date.today()),
        date_retour_prevue=_parse_date(request.form.get("date_retour_prevue"), None) if request.form.get("date_retour_prevue") else None,
        notes=(request.form.get("notes") or "").strip() or None,
        created_by_user_id=getattr(current_user, "id", None),
    ))
    db.session.commit()
    flash(f"Prêt de « {item.designation} » à {emprunteur} enregistré ✅", "success")
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
