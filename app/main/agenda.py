"""Mon agenda : abonnement iCal des séances (Google Agenda, Apple, Outlook).

Deux routes :
- ``/calendrier/<token>.ics`` : le flux lui-même, PUBLIC (résolu par jeton
  secret, sans connexion) pour que Google puisse le relire périodiquement.
  Exposé aussi à travers le tunnel « hors les murs » (voir la façade
  kiosque) pour être joignable depuis internet ;
- ``/mon-agenda`` : la page personnelle qui donne le lien à copier, la
  marche à suivre, et le bouton pour régénérer (révoquer) le lien.
"""
from flask import Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.main.common import bp
from app.models import User
from app.rbac import require_perm
from app.services.calendrier import generer_ics, regenerer_token, token_ou_creer
from app.services.public_urls import kiosk_public_base_url


@bp.route("/calendrier/<token>.ics")
def calendrier_ics(token: str):
    """Flux iCal public (par jeton secret). Aucune connexion requise :
    c'est Google/Apple qui relit l'URL, pas un humain connecté."""
    token = (token or "").strip()
    user = User.query.filter_by(calendar_token=token).first() if token else None
    if user is None or not user.actif:
        abort(404)
    ics = generer_ics(user, base_url=kiosk_public_base_url(),
                      nom_calendrier=f"Séances — {user.nom}")
    return Response(ics, mimetype="text/calendar; charset=utf-8", headers={
        "Content-Disposition": "inline; filename=seances.ics",
        "Cache-Control": "no-cache",
    })


@bp.route("/mon-agenda")
@login_required
@require_perm("emargement:view")
def mon_agenda():
    token = token_ou_creer(current_user)
    base = kiosk_public_base_url().rstrip("/")
    url_https = f"{base}{url_for('main.calendrier_ics', token=token)}"
    # webcal:// : la plupart des agendas l'ouvrent en « abonnement » direct.
    url_webcal = url_https.replace("https://", "webcal://").replace("http://", "webcal://")
    return render_template("mon_agenda.html", url_https=url_https, url_webcal=url_webcal)


@bp.post("/mon-agenda/regenerer")
@login_required
@require_perm("emargement:view")
def mon_agenda_regenerer():
    regenerer_token(current_user)
    flash("Nouveau lien généré : l'ancien ne fonctionne plus. Mets à jour ton agenda avec le nouveau lien.", "success")
    return redirect(url_for("main.mon_agenda"))
