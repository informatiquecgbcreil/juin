"""Vie associative : instances de gouvernance, mandats, réunions, émargement.

- Tableau de bord : instances, mandats arrivant à échéance, prochaines réunions.
- Une instance (AG / CA / bureau / commission) porte des mandats et des réunions.
- Une réunion suit son ordre du jour, son émargement (présents / pouvoirs /
  excusés), son quorum et son relevé de décisions ; convocation et feuille
  d'émargement s'exportent en Word.

Réservé aux titulaires de ``gouvernance:view`` (lecture) / ``gouvernance:edit``
(gestion). Pas de bornage secteur : la gouvernance est transversale.
"""
from __future__ import annotations

from datetime import date, datetime
from io import BytesIO

from flask import flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import (
    INSTANCE_TYPES,
    INSTANCE_TYPES_LABELS,
    MANDAT_FONCTIONS,
    MANDAT_FONCTIONS_LABELS,
    REUNION_TYPES,
    REUNION_TYPES_LABELS,
    InstanceGouvernance,
    Mandat,
    PresenceReunion,
    Reunion,
)
from app.rbac import require_perm
from app.services.gouvernance import (
    GouvernanceInvalide,
    construire_convocation_docx,
    construire_emargement_docx,
    enregistrer_presence,
    instances_actives,
    mandats_a_echeance,
    nombre_adherents_a_jour,
    prochaines_reunions,
)

from . import bp

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _parse_date(brut: str | None, defaut=None):
    try:
        return datetime.strptime((brut or "").strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return defaut


def _int_form(champ: str) -> int | None:
    val = request.form.get(champ, type=int)
    return val if val is not None and val >= 0 else None


def _options() -> dict:
    return {
        "types_instance": [(t, INSTANCE_TYPES_LABELS[t]) for t in INSTANCE_TYPES],
        "fonctions": [(f, MANDAT_FONCTIONS_LABELS[f]) for f in MANDAT_FONCTIONS],
        "types_reunion": [(t, REUNION_TYPES_LABELS[t]) for t in REUNION_TYPES],
    }


def _servir_docx(doc, nom_fichier: str):
    bio = BytesIO()
    doc.save(bio)
    bio.seek(0)
    return send_file(bio, as_attachment=True, download_name=nom_fichier, mimetype=DOCX_MIME)


# ---------------------------------------------------------------------------
# Tableau de bord
# ---------------------------------------------------------------------------

@bp.route("/")
@login_required
@require_perm("gouvernance:view")
def dashboard():
    return render_template(
        "gouvernance/dashboard.html",
        instances=instances_actives(),
        mandats_echeance=mandats_a_echeance(),
        reunions=prochaines_reunions(),
        adherents_a_jour=nombre_adherents_a_jour(),
        **_options(),
    )


# ---------------------------------------------------------------------------
# Instances
# ---------------------------------------------------------------------------

@bp.route("/instances/creer", methods=["POST"])
@login_required
@require_perm("gouvernance:edit")
def instance_creer():
    nom = (request.form.get("nom") or "").strip()
    if not nom:
        flash("Donnez un nom à l'instance.", "danger")
        return redirect(url_for("gouvernance.dashboard"))
    type_instance = (request.form.get("type_instance") or "ca").strip()
    if type_instance not in INSTANCE_TYPES:
        type_instance = "ca"
    inst = InstanceGouvernance(
        nom=nom, type_instance=type_instance,
        description=(request.form.get("description") or "").strip() or None,
    )
    db.session.add(inst)
    db.session.commit()
    flash(f"Instance « {nom} » créée ✅", "success")
    return redirect(url_for("gouvernance.instance_detail", instance_id=inst.id))


@bp.route("/instances/<int:instance_id>")
@login_required
@require_perm("gouvernance:view")
def instance_detail(instance_id: int):
    inst = db.get_or_404(InstanceGouvernance, instance_id)
    mandats = sorted(inst.mandats, key=lambda m: (not m.actif, m.nom.lower()))
    reunions = sorted(inst.reunions, key=lambda r: r.date_reunion, reverse=True)
    return render_template(
        "gouvernance/instance.html",
        instance=inst, mandats=mandats, reunions=reunions,
        adherents_a_jour=nombre_adherents_a_jour(),
        today=date.today(),
        **_options(),
    )


@bp.route("/instances/<int:instance_id>/basculer", methods=["POST"])
@login_required
@require_perm("gouvernance:edit")
def instance_basculer(instance_id: int):
    inst = db.get_or_404(InstanceGouvernance, instance_id)
    inst.actif = not inst.actif
    db.session.commit()
    flash(f"Instance « {inst.nom} » {'réactivée' if inst.actif else 'archivée'}.", "info")
    return redirect(url_for("gouvernance.instance_detail", instance_id=inst.id))


# ---------------------------------------------------------------------------
# Mandats
# ---------------------------------------------------------------------------

@bp.route("/instances/<int:instance_id>/mandats/creer", methods=["POST"])
@login_required
@require_perm("gouvernance:edit")
def mandat_creer(instance_id: int):
    inst = db.get_or_404(InstanceGouvernance, instance_id)
    nom = (request.form.get("nom") or "").strip()
    if not nom:
        flash("Indiquez le nom du mandataire.", "danger")
        return redirect(url_for("gouvernance.instance_detail", instance_id=inst.id))
    fonction = (request.form.get("fonction") or "membre").strip()
    if fonction not in MANDAT_FONCTIONS:
        fonction = "membre"
    db.session.add(Mandat(
        instance_id=inst.id, nom=nom, fonction=fonction,
        email=(request.form.get("email") or "").strip() or None,
        telephone=(request.form.get("telephone") or "").strip() or None,
        date_debut=_parse_date(request.form.get("date_debut")),
        date_fin=_parse_date(request.form.get("date_fin")),
    ))
    db.session.commit()
    flash(f"Mandat de {nom} ajouté ✅", "success")
    return redirect(url_for("gouvernance.instance_detail", instance_id=inst.id))


@bp.route("/mandats/<int:mandat_id>/cloturer", methods=["POST"])
@login_required
@require_perm("gouvernance:edit")
def mandat_cloturer(mandat_id: int):
    mandat = db.get_or_404(Mandat, mandat_id)
    mandat.actif = False
    db.session.commit()
    flash(f"Mandat de {mandat.nom} clôturé.", "info")
    return redirect(url_for("gouvernance.instance_detail", instance_id=mandat.instance_id))


@bp.route("/mandats/<int:mandat_id>/supprimer", methods=["POST"])
@login_required
@require_perm("gouvernance:edit")
def mandat_supprimer(mandat_id: int):
    mandat = db.get_or_404(Mandat, mandat_id)
    instance_id = mandat.instance_id
    db.session.delete(mandat)
    db.session.commit()
    flash("Mandat supprimé.", "info")
    return redirect(url_for("gouvernance.instance_detail", instance_id=instance_id))


# ---------------------------------------------------------------------------
# Réunions
# ---------------------------------------------------------------------------

@bp.route("/instances/<int:instance_id>/reunions/creer", methods=["POST"])
@login_required
@require_perm("gouvernance:edit")
def reunion_creer(instance_id: int):
    inst = db.get_or_404(InstanceGouvernance, instance_id)
    titre = (request.form.get("titre") or "").strip()
    jour = _parse_date(request.form.get("date_reunion"))
    if not titre or jour is None:
        flash("Indiquez au moins un intitulé et une date.", "danger")
        return redirect(url_for("gouvernance.instance_detail", instance_id=inst.id))
    type_reunion = (request.form.get("type_reunion") or "reunion").strip()
    if type_reunion not in REUNION_TYPES:
        type_reunion = "reunion"
    reunion = Reunion(
        instance_id=inst.id, type_reunion=type_reunion, titre=titre, date_reunion=jour,
        heure=(request.form.get("heure") or "").strip() or None,
        lieu=(request.form.get("lieu") or "").strip() or None,
        ordre_du_jour=(request.form.get("ordre_du_jour") or "").strip() or None,
        base_electeurs=_int_form("base_electeurs"),
        quorum_requis=_int_form("quorum_requis"),
        created_by_user_id=getattr(current_user, "id", None),
    )
    db.session.add(reunion)
    db.session.commit()
    flash(f"Réunion « {titre} » créée ✅", "success")
    return redirect(url_for("gouvernance.reunion_detail", reunion_id=reunion.id))


@bp.route("/reunions/<int:reunion_id>")
@login_required
@require_perm("gouvernance:view")
def reunion_detail(reunion_id: int):
    reunion = db.get_or_404(Reunion, reunion_id)
    presences = sorted(reunion.presences, key=lambda p: (p.nom or "").lower())
    return render_template(
        "gouvernance/reunion.html",
        reunion=reunion, presences=presences,
        mandats=reunion.instance.mandats_actifs if reunion.instance else [],
    )


@bp.route("/reunions/<int:reunion_id>/statut", methods=["POST"])
@login_required
@require_perm("gouvernance:edit")
def reunion_statut(reunion_id: int):
    reunion = db.get_or_404(Reunion, reunion_id)
    statut = (request.form.get("statut") or "").strip()
    if statut in ("planifiee", "tenue", "annulee"):
        reunion.statut = statut
        db.session.commit()
        flash("Statut de la réunion mis à jour.", "info")
    return redirect(url_for("gouvernance.reunion_detail", reunion_id=reunion.id))


@bp.route("/reunions/<int:reunion_id>/releve", methods=["POST"])
@login_required
@require_perm("gouvernance:edit")
def reunion_releve(reunion_id: int):
    reunion = db.get_or_404(Reunion, reunion_id)
    reunion.releve_decisions = (request.form.get("releve_decisions") or "").strip() or None
    db.session.commit()
    flash("Relevé de décisions enregistré ✅", "success")
    return redirect(url_for("gouvernance.reunion_detail", reunion_id=reunion.id))


@bp.route("/reunions/<int:reunion_id>/presence", methods=["POST"])
@login_required
@require_perm("gouvernance:edit")
def presence_creer(reunion_id: int):
    reunion = db.get_or_404(Reunion, reunion_id)
    try:
        enregistrer_presence(
            reunion,
            nom=request.form.get("nom"),
            etat=(request.form.get("etat") or "present").strip(),
            represente_par=request.form.get("represente_par"),
        )
    except GouvernanceInvalide as exc:
        flash(str(exc), "warning")
    return redirect(url_for("gouvernance.reunion_detail", reunion_id=reunion.id))


@bp.route("/presences/<int:presence_id>/supprimer", methods=["POST"])
@login_required
@require_perm("gouvernance:edit")
def presence_supprimer(presence_id: int):
    presence = db.get_or_404(PresenceReunion, presence_id)
    reunion_id = presence.reunion_id
    db.session.delete(presence)
    db.session.commit()
    return redirect(url_for("gouvernance.reunion_detail", reunion_id=reunion_id))


@bp.route("/reunions/<int:reunion_id>/convocation.docx")
@login_required
@require_perm("gouvernance:view")
def reunion_convocation(reunion_id: int):
    reunion = db.get_or_404(Reunion, reunion_id)
    return _servir_docx(construire_convocation_docx(reunion), f"convocation_{reunion.id}.docx")


@bp.route("/reunions/<int:reunion_id>/emargement.docx")
@login_required
@require_perm("gouvernance:view")
def reunion_emargement(reunion_id: int):
    reunion = db.get_or_404(Reunion, reunion_id)
    return _servir_docx(construire_emargement_docx(reunion), f"emargement_{reunion.id}.docx")
