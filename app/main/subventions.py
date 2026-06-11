import csv
from io import StringIO
from datetime import date


from flask import (
    render_template, request, redirect, url_for, flash, abort,
    current_app, Response, jsonify
)
from flask_login import login_required, current_user
from app.rbac import require_perm, can

from app.extensions import db
from app.models import (
    Subvention,
    LigneBudget,
    Depense,
    Projet,
    SubventionProjet,
)
from app.previsionnel.referentiel import BudgetCategorieReferentiel, BudgetCompteReferentiel


from app.main.common import bp, can_see_secteur
from app.utils.delete_guard import commit_delete

def _parse_money(value, default=0.0) -> float:
    raw = str(value or "").replace(" ", "").replace(",", ".")
    try:
        return float(raw) if raw else float(default)
    except Exception:
        return float(default)


def _ref_scope_query(query, model, secteur: str | None):
    if secteur:
        return query.filter((model.secteur.is_(None)) | (model.secteur == secteur))
    return query


def _budget_categories_ref_for_secteur(secteur: str | None = None, nature: str | None = None, active_only: bool = True):
    q = BudgetCategorieReferentiel.query.join(BudgetCompteReferentiel)
    q = _ref_scope_query(q, BudgetCategorieReferentiel, secteur)
    if secteur:
        q = q.filter((BudgetCompteReferentiel.secteur.is_(None)) | (BudgetCompteReferentiel.secteur == secteur))
    if nature in ("charge", "produit"):
        q = q.filter(BudgetCategorieReferentiel.nature == nature)
    if active_only:
        q = q.filter(BudgetCategorieReferentiel.actif.is_(True), BudgetCompteReferentiel.actif.is_(True))
    return q.order_by(
        BudgetCompteReferentiel.nature.asc(),
        BudgetCompteReferentiel.ordre.asc(),
        BudgetCompteReferentiel.code.asc(),
        BudgetCategorieReferentiel.ordre.asc(),
        BudgetCategorieReferentiel.libelle.asc(),
    ).all()


def _budget_category_allowed(cat: BudgetCategorieReferentiel, secteur: str | None, nature: str | None = None) -> bool:
    if not cat or not getattr(cat, "compte", None):
        return False
    if nature in ("charge", "produit") and cat.nature != nature:
        return False
    if cat.secteur and secteur and cat.secteur != secteur:
        return False
    if cat.compte.secteur and secteur and cat.compte.secteur != secteur:
        return False
    return bool(cat.actif and cat.compte.actif)


def _budget_category_compte_label(cat: BudgetCategorieReferentiel) -> str:
    if not cat or not getattr(cat, "compte", None):
        return ""
    return f"{cat.compte.code} - {cat.compte.libelle}".strip(" -")


def _compute_prorata(lignes, montant_cible: float):
    """
    Calcule une répartition pro-rata sur montant_base.
    Ne modifie pas la DB : retourne un dict {ligne_id: montant_theorique}
    Ajuste la dernière ligne pour tomber pile au centime.
    """
    lignes = list(lignes)
    out = {}
    if not lignes:
        return out

    total_base = sum(float(l.montant_base or 0) for l in lignes)
    if total_base <= 0:
        for l in lignes:
            out[l.id] = 0.0
        return out

    ratio = float(montant_cible or 0) / total_base

    cumul = 0.0
    for i, l in enumerate(lignes):
        base = float(l.montant_base or 0)
        part = round(base * ratio, 2)
        if i == len(lignes) - 1:
            part = round(float(montant_cible or 0) - cumul, 2)
        out[l.id] = float(part)
        cumul += float(part)

    return out




# --------- List subventions ---------
@bp.route("/subventions")
@login_required
@require_perm("subventions:view")
def subventions_list():
    secteurs = current_app.config.get("SECTEURS", [])

    base_q = Subvention.query.filter_by(est_archive=False)
    if not can("scope:all_secteurs"):
        base_q = base_q.filter(Subvention.secteur == current_user.secteur_assigne)

    years = [
        y for (y,) in base_q.with_entities(Subvention.annee_exercice).distinct().order_by(Subvention.annee_exercice.desc()).all()
        if y is not None
    ]
    try:
        selected_year = int(request.args.get("annee") or (years[0] if years else date.today().year))
    except Exception:
        selected_year = years[0] if years else date.today().year

    subs_q = base_q.filter(Subvention.annee_exercice == selected_year)
    subs = subs_q.order_by(Subvention.annee_exercice.desc(), Subvention.nom.asc()).all()

    default_secteur = current_user.secteur_assigne if not can("scope:all_secteurs") else (secteurs[0] if secteurs else None)
    categories_ref = _budget_categories_ref_for_secteur(default_secteur)
    return render_template(
        "subventions_list.html",
        subs=subs,
        secteurs=secteurs,
        selected_year=selected_year,
        available_years=years,
        categories_ref=categories_ref,
    )


@bp.route("/subvention/nouvelle", methods=["POST"])
@login_required
@require_perm('subventions:edit')
def subvention_create():
    nom = (request.form.get("nom") or "").strip()
    secteur = (request.form.get("secteur") or "").strip()
    annee = int(request.form.get("annee_exercice") or 2025)

    montant_demande = float(request.form.get("montant_demande") or 0)
    montant_attribue = float(request.form.get("montant_attribue") or 0)
    montant_recu = float(request.form.get("montant_recu") or 0)

    if not can("scope:all_secteurs"):
        secteur = current_user.secteur_assigne

    if not nom or not secteur:
        flash("Nom + secteur obligatoires.", "danger")
        return redirect(url_for("main.subventions_list"))

    if not can_see_secteur(secteur):
        abort(403)

    s = Subvention(
        nom=nom,
        secteur=secteur,
        annee_exercice=annee,
        montant_demande=montant_demande,
        montant_attribue=montant_attribue,
        montant_recu=montant_recu,
    )
    db.session.add(s)
    db.session.flush()

    selected_cat_ids = [int(x) for x in request.form.getlist("categorie_ref_id") if str(x).isdigit()]
    if selected_cat_ids:
        cats = BudgetCategorieReferentiel.query.filter(BudgetCategorieReferentiel.id.in_(selected_cat_ids)).all()
        for cat in cats:
            if not _budget_category_allowed(cat, secteur):
                continue
            db.session.add(LigneBudget(
                subvention_id=s.id,
                nature=cat.nature,
                compte=_budget_category_compte_label(cat) or ("74" if cat.nature == "produit" else "60"),
                libelle=cat.libelle,
                montant_base=float(cat.montant_defaut or 0.0),
                montant_reel=0.0,
            ))

    db.session.commit()

    flash("Subvention créée.", "success")
    return redirect(url_for("main.subvention_pilotage", subvention_id=s.id))


# --------- Pilotage subvention ---------
@bp.route("/subvention/<int:subvention_id>/pilotage", methods=["GET", "POST"])
@login_required
@require_perm("subventions:view")
def subvention_pilotage(subvention_id):
    sub = db.get_or_404(Subvention, subvention_id)
    if not can_see_secteur(sub.secteur):
        abort(403)

    if request.method == "POST":
        if not can("subventions:edit"):
            abort(403)
        action = request.form.get("action") or ""

        # --- Montants globaux ---
        if action == "update_montants":
            sub.montant_demande = float(request.form.get("montant_demande") or 0)
            sub.montant_attribue = float(request.form.get("montant_attribue") or 0)
            sub.montant_recu = float(request.form.get("montant_recu") or 0)
            db.session.commit()
            flash("Montants mis à jour.", "success")
            return redirect(url_for("main.subvention_pilotage", subvention_id=sub.id))

        # --- Ajouter une ligne ---
        if action == "add_ligne":
            nature = (request.form.get("nature") or "charge").strip()
            cat_id = int(request.form.get("categorie_ref_id") or 0)
            cat = None
            if cat_id:
                cat = db.get_or_404(BudgetCategorieReferentiel, cat_id)
                if not _budget_category_allowed(cat, sub.secteur):
                    abort(400)
                nature = cat.nature

            compte_default = _budget_category_compte_label(cat) if cat else ("74" if nature == "produit" else "60")
            libelle_default = cat.libelle if cat else ""
            montant_default = float(cat.montant_defaut or 0.0) if cat else 0.0

            compte = (request.form.get("compte") or compte_default).strip()
            libelle = (request.form.get("libelle") or libelle_default).strip()
            montant_base = _parse_money(request.form.get("montant_base"), montant_default)
            montant_reel = _parse_money(request.form.get("montant_reel"), 0.0)

            if not libelle:
                flash("Libellé obligatoire.", "danger")
                return redirect(url_for("main.subvention_pilotage", subvention_id=sub.id))

            l = LigneBudget(
                subvention_id=sub.id,
                nature=nature,
                compte=compte,
                libelle=libelle,
                montant_base=montant_base,
                montant_reel=montant_reel,
            )
            db.session.add(l)
            db.session.commit()
            flash("Ligne ajoutée.", "success")
            return redirect(url_for("main.subvention_pilotage", subvention_id=sub.id))

        # --- Ventilation automatique (écrit dans montant_reel) ---
        if action == "auto_ventilation":
            mode = (request.form.get("mode") or "copy_base").strip()
            target = (request.form.get("target") or "recu").strip()

            if target == "attribue":
                montant_cible = float(sub.montant_attribue or 0)
            else:
                montant_cible = float(sub.montant_recu or 0)

            lignes = list(sub.lignes)
            if not lignes:
                flash("Aucune ligne à ventiler.", "warning")
                return redirect(url_for("main.subvention_pilotage", subvention_id=sub.id))

            if mode == "reset":
                for l in lignes:
                    l.montant_reel = 0.0
                db.session.commit()
                flash("Ventilation réinitialisée (réel = 0).", "warning")
                return redirect(url_for("main.subvention_pilotage", subvention_id=sub.id))

            if mode == "copy_base":
                for l in lignes:
                    l.montant_reel = float(l.montant_base or 0)
                db.session.commit()
                flash("Ventilation : base copiée vers réel.", "success")
                return redirect(url_for("main.subvention_pilotage", subvention_id=sub.id))

            if mode == "prorata_base":
                total_base = sum(float(l.montant_base or 0) for l in lignes)
                if total_base <= 0:
                    flash("Impossible : total des bases = 0.", "danger")
                    return redirect(url_for("main.subvention_pilotage", subvention_id=sub.id))

                theor = _compute_prorata(lignes, montant_cible)
                for l in lignes:
                    l.montant_reel = float(theor.get(l.id, 0.0))
                db.session.commit()
                flash(f"Ventilation pro-rata effectuée sur {montant_cible:.2f}€.", "success")
                return redirect(url_for("main.subvention_pilotage", subvention_id=sub.id))

            abort(400)

        abort(400)

    # --- GET : données pour page ---
    projets_q = Projet.query.filter(Projet.secteur == sub.secteur)
    if not can("scope:all_secteurs"):
        projets_q = projets_q.filter(Projet.secteur == current_user.secteur_assigne)

    projets = projets_q.order_by(Projet.nom.asc()).all()
    linked_ids = set(sp.projet_id for sp in sub.projets)

    lignes = list(sub.lignes)
    total_base = round(sum(float(l.montant_base or 0) for l in lignes), 2)

    theor_recu = _compute_prorata(lignes, float(sub.montant_recu or 0))
    theor_attribue = _compute_prorata(lignes, float(sub.montant_attribue or 0))

    recu = float(sub.montant_recu or 0)
    reel_lignes = float(sub.total_reel_lignes or 0)
    engage = float(sub.total_engage or 0)

    warnings = []
    if recu > 0 and reel_lignes == 0:
        warnings.append("Tu as un montant reçu, mais aucune ventilation en lignes réel : utilise la ventilation auto ou renseigne le réel par ligne.")
    if recu > 0 and reel_lignes > 0 and reel_lignes < recu:
        warnings.append("Ventilation partielle : total lignes réel < montant reçu. Il manque une répartition.")
    if reel_lignes > 0 and engage > reel_lignes:
        warnings.append("Attention : engagé > total lignes réel (dépenses au-dessus de l'enveloppe ventilée).")

    return render_template(
        "budget_pilotage.html",
        sub=sub,
        projets=projets,
        linked_ids=linked_ids,
        total_base=total_base,
        theor_recu=theor_recu,
        theor_attribue=theor_attribue,
        warnings=warnings,
        categories_ref=_budget_categories_ref_for_secteur(sub.secteur),
    )


@bp.route("/subvention/<int:subvention_id>/delete", methods=["POST"])
@login_required
@require_perm('subventions:delete')
def subvention_delete(subvention_id):
    sub = db.get_or_404(Subvention, subvention_id)
    if not can_see_secteur(sub.secteur):
        abort(403)

    db.session.delete(sub)
    commit_delete(
        f"la subvention « {sub.nom} »",
        "Subvention supprimée.",
        success_category="warning",
        blocked_message=f"Impossible de supprimer la subvention « {sub.nom} » : elle est encore liée à d'autres données.",
    )
    return redirect(url_for("main.subventions_list"))


# --------- Edit / Delete lignes ---------
@bp.route("/ligne/<int:ligne_id>/edit", methods=["POST"])
@login_required
@require_perm("subventions:edit")
def ligne_edit(ligne_id):
    l = db.get_or_404(LigneBudget, ligne_id)
    sub = l.source_sub
    if not can_see_secteur(sub.secteur):
        abort(403)

    cat_id = int(request.form.get("categorie_ref_id") or 0)
    cat = None
    if cat_id:
        cat = db.get_or_404(BudgetCategorieReferentiel, cat_id)
        if not _budget_category_allowed(cat, sub.secteur):
            abort(400)

    l.nature = (request.form.get("nature") or (cat.nature if cat else getattr(l, "nature", "charge"))).strip()
    l.compte = (request.form.get("compte") or (_budget_category_compte_label(cat) if cat else l.compte)).strip()
    l.libelle = (request.form.get("libelle") or (cat.libelle if cat else l.libelle)).strip()
    l.montant_base = _parse_money(request.form.get("montant_base"), l.montant_base or 0)
    l.montant_reel = _parse_money(request.form.get("montant_reel"), l.montant_reel or 0)
    db.session.commit()

    flash("Ligne modifiée.", "success")
    return redirect(url_for("main.subvention_pilotage", subvention_id=sub.id))


@bp.route("/ligne/<int:ligne_id>/delete", methods=["POST"])
@login_required
@require_perm('budget:delete')
def ligne_delete(ligne_id):
    l = db.get_or_404(LigneBudget, ligne_id)
    sub = l.source_sub
    if not can_see_secteur(sub.secteur):
        abort(403)

    db.session.delete(l)
    commit_delete(
        f"la ligne « {l.libelle} »",
        "Ligne supprimée.",
        success_category="warning",
        blocked_message=f"Impossible de supprimer la ligne « {l.libelle} » : elle est encore utilisée ailleurs.",
    )
    return redirect(url_for("main.subvention_pilotage", subvention_id=sub.id))


# --------- Lier / délier subvention à projet ---------
@bp.route("/subvention/<int:subvention_id>/toggle_projet", methods=["POST"])
@login_required
@require_perm("subventions:link")
def subvention_toggle_projet(subvention_id):
    sub = db.get_or_404(Subvention, subvention_id)
    if not can_see_secteur(sub.secteur):
        abort(403)

    projet_id = int(request.form.get("projet_id") or 0)
    projet = db.get_or_404(Projet, projet_id)

    if projet.secteur != sub.secteur:
        abort(400)

    link = SubventionProjet.query.filter_by(projet_id=projet.id, subvention_id=sub.id).first()
    if link:
        db.session.delete(link)
        db.session.commit()
        flash("Subvention retirée du projet.", "warning")
    else:
        link = SubventionProjet(projet_id=projet.id, subvention_id=sub.id)
        db.session.add(link)
        db.session.commit()
        flash("Subvention ajoutée au projet.", "success")

    return redirect(url_for("main.subvention_pilotage", subvention_id=sub.id))


# --------- APIs pour dropdowns dépenses ---------
@bp.route("/api/subvention/<int:subvention_id>/comptes")
@login_required
@require_perm("subventions:view")
def api_comptes(subvention_id):
    sub = db.get_or_404(Subvention, subvention_id)
    if not can_see_secteur(sub.secteur):
        abort(403)

    nature = request.args.get("nature")

    q = LigneBudget.query.filter_by(subvention_id=sub.id)
    if nature:
        q = q.filter(LigneBudget.nature == nature)

    comptes = sorted({l.compte for l in q if l.compte})
    return jsonify({"comptes": comptes})


@bp.route("/api/subvention/<int:subvention_id>/lignes")
@login_required
@require_perm("subventions:view")
def api_lignes(subvention_id):
    sub = db.get_or_404(Subvention, subvention_id)
    if not can_see_secteur(sub.secteur):
        abort(403)

    compte = (request.args.get("compte") or "").strip()
    nature = request.args.get("nature")

    q = LigneBudget.query.filter_by(subvention_id=sub.id)
    if nature:
        q = q.filter(LigneBudget.nature == nature)
    if compte:
        q = q.filter(LigneBudget.compte == compte)

    lignes = q.order_by(LigneBudget.compte.asc(), LigneBudget.libelle.asc()).all()

    out = []
    for l in lignes:
        out.append({
            "id": l.id,
            "compte": l.compte,
            "libelle": l.libelle,
            "montant_reel": float(l.montant_reel or 0),
            "engage": float(l.engage or 0),
            "reste": float(l.reste or 0),
        })

    return jsonify({"lignes": out})



# --------- Exports simples ---------
@bp.route("/export/depenses.csv")
@login_required
@require_perm("depenses:view")
def export_depenses_csv():
    dep_q = Depense.query.join(LigneBudget).join(Subvention)
    if not can("scope:all_secteurs"):
        dep_q = dep_q.filter(Subvention.secteur == current_user.secteur_assigne)

    deps = dep_q.all()

    out = StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(["secteur", "subvention", "annee", "compte", "ligne", "depense", "montant", "date_paiement", "type"])

    for d in deps:
        l = d.budget_source
        s = l.source_sub
        writer.writerow([
            s.secteur,
            s.nom,
            s.annee_exercice,
            l.compte,
            l.libelle,
            d.libelle,
            f"{float(d.montant or 0):.2f}".replace(".", ","),
            d.date_paiement.isoformat() if d.date_paiement else "",
            d.type_depense or ""
        ])

    content = out.getvalue().encode("utf-8-sig")  # Excel friendly
    filename = f"depenses_{date.today().isoformat()}.csv"
    return Response(content, mimetype="text/csv", headers={
        "Content-Disposition": f"attachment; filename={filename}"
    })


@bp.route("/export/subvention/<int:subvention_id>.csv")
@login_required
@require_perm("subventions:view")
def export_subvention_csv(subvention_id):
    s = db.get_or_404(Subvention, subvention_id)
    if not can_see_secteur(s.secteur):
        abort(403)

    out = StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(["subvention", "secteur", "annee", "compte", "ligne", "base", "reel", "engage", "reste"])

    for l in s.lignes:
        writer.writerow([
            s.nom,
            s.secteur,
            s.annee_exercice,
            l.compte,
            l.libelle,
            f"{float(l.montant_base or 0):.2f}".replace(".", ","),
            f"{float(l.montant_reel or 0):.2f}".replace(".", ","),
            f"{float(l.engage or 0):.2f}".replace(".", ","),
            f"{float(l.reste or 0):.2f}".replace(".", ","),
        ])

    content = out.getvalue().encode("utf-8-sig")
    return Response(content, mimetype="text/csv", headers={
        "Content-Disposition": f"attachment; filename=subvention_{s.id}.csv"
    })


# --------- Bilan par subvention ---------
@bp.route("/subvention/<int:subvention_id>/bilan")
@login_required
@require_perm("subventions:view")
def subvention_bilan(subvention_id: int):
    """
    Vue détaillée pour un financeur / subvention.

    Affiche un récapitulatif des montants demandés/attribués/reçus et des lignes de budget,
    avec une représentation graphique proportionnelle par ligne (charges et produits).
    """
    sub = db.get_or_404(Subvention, subvention_id)
    # Vérification des droits : un responsable ne peut consulter que son secteur
    if not can_see_secteur(sub.secteur):
        abort(403)

    # Collecte des lignes de budget
    lignes: list[dict[str, float | str]] = []
    # Calcul du montant maximum utilisé pour la largeur des barres
    max_total = 0.0
    for l in sub.lignes:
        base = float(l.montant_base or 0)
        reel = float(l.montant_reel or 0)
        engage = float(l.engage or 0)
        reste = float(l.reste or 0)
        nature = getattr(l, "nature", "charge")
        total_for_max = reel + engage + reste
        if total_for_max > max_total:
            max_total = total_for_max
        lignes.append({
            "id": l.id,
            "compte": l.compte,
            "libelle": l.libelle,
            "base": base,
            "reel": reel,
            "engage": engage,
            "reste": reste,
            "nature": nature,
        })

    # Calcul des pourcentages pour chaque ligne (évite de surcharger le template)
    if max_total > 0:
        for d in lignes:
            d["p_reel"] = (d["reel"] / max_total) * 100.0 if d["reel"] else 0.0
            d["p_engage"] = (d["engage"] / max_total) * 100.0 if d["engage"] else 0.0
            d["p_reste"] = (d["reste"] / max_total) * 100.0 if d["reste"] else 0.0
    else:
        for d in lignes:
            d["p_reel"] = d["p_engage"] = d["p_reste"] = 0.0

    # Totaux synthétiques (charges et produits séparés)
    totals = {
        "demande": float(sub.montant_demande or 0),
        "attribue": float(sub.montant_attribue or 0),
        "recu": float(sub.montant_recu or 0),
        "base_charges": 0.0,
        "base_produits": 0.0,
        "reel_charges": 0.0,
        "reel_produits": 0.0,
        "engage": 0.0,
        "reste": 0.0,
    }
    for d in lignes:
        if d["nature"] == "produit":
            totals["base_produits"] += d["base"]
            totals["reel_produits"] += d["reel"]
        else:
            totals["base_charges"] += d["base"]
            totals["reel_charges"] += d["reel"]
            totals["engage"] += d["engage"]
            totals["reste"] += d["reste"]

    # Arrondis des totaux
    for k in totals:
        totals[k] = round(float(totals[k] or 0), 2)

    return render_template(
        "subvention_bilan.html",
        sub=sub,
        lignes=lignes,
        totals=totals,
        max_total=max_total,
    )



# ---------------------------------------------------------------------
# RBAC Test (diagnostic)
# ---------------------------------------------------------------------

