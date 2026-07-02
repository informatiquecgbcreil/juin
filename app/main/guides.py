"""Guides pas à pas : liste, démarrage, avancement, sortie.

Le guide actif vit en session ; le bandeau est rendu par le layout sur
toutes les pages (voir templates/_guide_bandeau.html).
"""
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.main.common import bp
from app.rbac import require_perm
from app.services.guides import (
    GUIDES,
    _user_can_any,
    avancer_guide,
    demarrer_guide,
    guide_actif_ctx,
    guides_disponibles,
    quitter_guide,
)


def _retour():
    return redirect(request.form.get("next") or request.referrer or url_for("main.guides_liste"))


@bp.route("/guides")
@login_required
@require_perm("dashboard:view")
def guides_liste():
    return render_template("guides.html", guides=guides_disponibles(current_user))


@bp.post("/guides/<key>/demarrer")
@login_required
@require_perm("dashboard:view")
def guide_demarrer(key: str):
    g = GUIDES.get(key)
    if not g or not _user_can_any(current_user, g.get("perm_any")):
        flash("Ce guide n'est pas disponible avec tes droits.", "danger")
        return redirect(url_for("main.guides_liste"))
    url = demarrer_guide(key)
    flash(f"Guide « {g['titre']} » démarré : suis le bandeau en haut de page.", "success")
    return redirect(url or url_for("main.guides_liste"))


@bp.post("/guides/suivant")
@login_required
def guide_suivant():
    url = avancer_guide(+1)
    if guide_actif_ctx() is None:
        # Dernière étape franchie : le guide est terminé.
        flash("Guide terminé, bravo ! Tu peux le relancer quand tu veux depuis la page Guides.", "success")
        return _retour()
    # Étape suivante : on y va si elle a une page cible, sinon on reste ici.
    return redirect(url) if url else _retour()


@bp.post("/guides/precedent")
@login_required
def guide_precedent():
    url = avancer_guide(-1)
    return redirect(url) if url else _retour()


@bp.post("/guides/quitter")
@login_required
def guide_quitter():
    quitter_guide()
    flash("Guide quitté. Tu peux le reprendre depuis la page Guides.", "info")
    return _retour()
