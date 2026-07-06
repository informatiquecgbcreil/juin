"""Flux calendrier iCal (abonnement Google Agenda / Apple / Outlook)."""
import datetime as dt
import uuid

import pytest


def _login_role(app, email, role_code, secteur=None):
    from app.extensions import db
    from app.models import Role, User
    with app.app_context():
        u = User.query.filter_by(email=email).first()
        if u is None:
            u = User(email=email, nom=email.split("@")[0], secteur_assigne=secteur)
            u.set_password("pw-test-123")
            u.roles.append(Role.query.filter_by(code=role_code).first())
            db.session.add(u)
            db.session.commit()
    c = app.test_client()
    c.post("/", data={"email": email, "password": "pw-test-123"})
    return c


def _seance(app, *, secteur, nom, jour_offset=3, heure_debut="14:00", heure_fin="16:00", statut="realisee"):
    from app.extensions import db
    from app.models import AtelierActivite, SessionActivite
    with app.app_context():
        at = AtelierActivite(nom=nom, secteur=secteur, type_atelier="COLLECTIF")
        db.session.add(at)
        db.session.flush()
        s = SessionActivite(atelier_id=at.id, secteur=secteur, session_type="COLLECTIF",
                            date_session=dt.date.today() + dt.timedelta(days=jour_offset),
                            heure_debut=heure_debut, heure_fin=heure_fin, statut=statut)
        db.session.add(s)
        db.session.commit()
        return s.id


def _user_avec_token(app, email="agenda-user@example.org", secteur="Jeunesse", role="responsable_secteur"):
    from app.extensions import db
    from app.models import Role, User
    from app.services.calendrier import token_ou_creer
    with app.app_context():
        u = User.query.filter_by(email=email).first()
        if u is None:
            u = User(email=email, nom="AgendaUser", secteur_assigne=secteur)
            u.set_password("pw-test-123")
            u.roles.append(Role.query.filter_by(code=role).first())
            db.session.add(u)
            db.session.commit()
        token = token_ou_creer(u)
        return token


def test_flux_ics_public_par_jeton(app, client):
    suf = uuid.uuid4().hex[:6]
    sect = f"Jeun{suf}"
    _seance(app, secteur=sect, nom=f"Cours{suf}")
    token = _user_avec_token(app, email=f"a-{suf}@ex.org", secteur=sect)

    r = client.get(f"/calendrier/{token}.ics")
    assert r.status_code == 200
    assert r.mimetype == "text/calendar"
    body = r.get_data(as_text=True)
    assert "BEGIN:VCALENDAR" in body and "END:VCALENDAR" in body
    assert "BEGIN:VEVENT" in body
    assert f"Cours{suf}" in body
    # UID stable + horaire
    assert "UID:seance-" in body
    assert "DTSTART;TZID=Europe/Paris:" in body


def test_jeton_inconnu_404(app, client):
    assert client.get("/calendrier/nimportequoi.ics").status_code == 404


def test_flux_borne_au_secteur(app, client):
    suf = uuid.uuid4().hex[:6]
    mien, autre = f"Mien{suf}", f"Autre{suf}"
    _seance(app, secteur=mien, nom=f"Dedans{suf}")
    _seance(app, secteur=autre, nom=f"Dehors{suf}")
    token = _user_avec_token(app, email=f"borne-{suf}@ex.org", secteur=mien, role="responsable_secteur")

    body = client.get(f"/calendrier/{token}.ics").get_data(as_text=True)
    assert f"Dedans{suf}" in body
    assert f"Dehors{suf}" not in body


def test_aucun_nom_de_participant_dans_le_flux(app, client):
    from app.extensions import db
    from app.models import Participant, PresenceActivite
    suf = uuid.uuid4().hex[:6]
    sect = f"Priv{suf}"
    sid = _seance(app, secteur=sect, nom=f"Atelier{suf}")
    with app.app_context():
        p = Participant(nom=f"SecretNom{suf}", prenom="Confidentiel")
        db.session.add(p)
        db.session.flush()
        db.session.add(PresenceActivite(session_id=sid, participant_id=p.id))
        db.session.commit()
    token = _user_avec_token(app, email=f"priv-{suf}@ex.org", secteur=sect)

    body = client.get(f"/calendrier/{token}.ics").get_data(as_text=True)
    assert f"SecretNom{suf}" not in body
    assert "Confidentiel" not in body


def test_seance_annulee_marquee_cancelled(app, client):
    suf = uuid.uuid4().hex[:6]
    sect = f"Ann{suf}"
    _seance(app, secteur=sect, nom=f"Annule{suf}", statut="annulee")
    token = _user_avec_token(app, email=f"ann-{suf}@ex.org", secteur=sect)
    body = client.get(f"/calendrier/{token}.ics").get_data(as_text=True)
    assert "STATUS:CANCELLED" in body


def test_seance_sans_heure_est_journee_entiere(app, client):
    suf = uuid.uuid4().hex[:6]
    sect = f"AllDay{suf}"
    _seance(app, secteur=sect, nom=f"JourEntier{suf}", heure_debut=None, heure_fin=None)
    token = _user_avec_token(app, email=f"allday-{suf}@ex.org", secteur=sect)
    body = client.get(f"/calendrier/{token}.ics").get_data(as_text=True)
    assert "DTSTART;VALUE=DATE:" in body


def test_page_mon_agenda_et_regeneration(app):
    from app.extensions import db
    from app.models import User
    c = _login_role(app, "agenda-page@example.org", "responsable_secteur", secteur="Jeunesse")
    r = c.get("/mon-agenda")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "/calendrier/" in body and ".ics" in body
    with app.app_context():
        t1 = User.query.filter_by(email="agenda-page@example.org").first().calendar_token
    assert t1

    # L'ancien lien fonctionne, puis on régénère → il cesse de fonctionner.
    assert c.get(f"/calendrier/{t1}.ics").status_code == 200
    c.post("/mon-agenda/regenerer")
    with app.app_context():
        t2 = User.query.filter_by(email="agenda-page@example.org").first().calendar_token
    assert t2 != t1
    assert c.get(f"/calendrier/{t1}.ics").status_code == 404
    assert c.get(f"/calendrier/{t2}.ics").status_code == 200


def test_facade_laisse_passer_le_flux_mais_bloque_le_reste(app, client):
    suf = uuid.uuid4().hex[:6]
    token = _user_avec_token(app, email=f"fac-{suf}@ex.org", secteur=f"F{suf}")
    app.config["KIOSK_PUBLIC_HOST"] = "public.exemple.fr"
    try:
        # Le flux iCal passe par l'hôte public…
        r = client.get(f"/calendrier/{token}.ics", headers={"Host": "public.exemple.fr"})
        assert r.status_code == 200
        # …mais le dashboard reste bloqué.
        r = client.get("/dashboard", headers={"Host": "public.exemple.fr"})
        assert r.status_code == 403
    finally:
        app.config["KIOSK_PUBLIC_HOST"] = ""


def test_formatage_ics_echappe_et_plie(app):
    """Nom long avec virgule/point-virgule : échappé et plié (lignes ≤ 75 o)."""
    from app.services.calendrier import _echapper, _plier
    assert _echapper("Atelier; cuisine, du soir") == "Atelier\\; cuisine\\, du soir"
    longue = "SUMMARY:" + "Atelier très long " * 8
    plie = _plier(longue)
    for i, ligne in enumerate(plie.split("\r\n")):
        # 1re ligne ≤ 75 octets ; les suivantes commencent par un espace.
        assert len(ligne.encode("utf-8")) <= 75
        if i > 0:
            assert ligne.startswith(" ")


def test_mon_agenda_exige_emargement_view(app):
    """Un rôle sans emargement:view n'accède pas à la page de synchro."""
    from app.extensions import db
    from app.models import Permission, Role
    with app.app_context():
        role = Role.query.filter_by(code="agenda_sans_droit").first()
        if role is None:
            role = Role(code="agenda_sans_droit", label="Sans agenda")
            db.session.add(role)
            perm = Permission.query.filter_by(code="dashboard:view").first()
            if perm:
                role.permissions.append(perm)
            db.session.commit()
    c = _login_role(app, "agenda-refuse@example.org", "agenda_sans_droit")
    assert c.get("/mon-agenda").status_code == 403
