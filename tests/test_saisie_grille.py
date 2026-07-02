"""Saisie en grille + émargements en attente (poste d'accueil).

- la grille coche/décoche des présences en masse, mois par mois ;
- les présences signées ou à statut particulier sont protégées ;
- une séance et une personne peuvent s'ajouter depuis la grille ;
- la page « en attente » liste les séances passées sans présence,
  et la relance pose un rappel (sans doublon).
"""
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


@pytest.fixture()
def atelier_grille(app):
    """Un atelier avec 2 séances le mois dernier et 2 participants habitués."""
    with app.app_context():
        from app.extensions import db
        from app.models import AtelierActivite, Participant, PresenceActivite, SessionActivite
        suf = uuid.uuid4().hex[:6]
        secteur = f"GR{suf}"
        at = AtelierActivite(nom=f"Grille{suf}", secteur=secteur, type_atelier="COLLECTIF")
        db.session.add(at)
        db.session.flush()
        # Mois dernier, pour être « passé » quel que soit le jour du test.
        base = (dt.date.today().replace(day=1) - dt.timedelta(days=1)).replace(day=10)
        s1 = SessionActivite(atelier_id=at.id, secteur=secteur, session_type="COLLECTIF", date_session=base)
        s2 = SessionActivite(atelier_id=at.id, secteur=secteur, session_type="COLLECTIF", date_session=base + dt.timedelta(days=7))
        p1 = Participant(nom=f"Grillea{suf}", prenom="Awa")
        p2 = Participant(nom=f"Grilleb{suf}", prenom="Bilal")
        db.session.add_all([s1, s2, p1, p2])
        db.session.flush()
        # p1 déjà présent sur s1 (l'habitué) ; s2 reste vide.
        db.session.add(PresenceActivite(session_id=s1.id, participant_id=p1.id))
        db.session.commit()
        return {"atelier_id": at.id, "secteur": secteur, "mois": f"{base.year:04d}-{base.month:02d}",
                "s1": s1.id, "s2": s2.id, "p1": p1.id, "p2": p2.id, "suf": suf}


def test_grille_affiche_participants_et_seances(app, atelier_grille, admin_client):
    r = admin_client.get(f"/activite/saisie-grille?atelier_id={atelier_grille['atelier_id']}&mois={atelier_grille['mois']}")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert f"Grillea{atelier_grille['suf']}" in body
    assert f"cell_{atelier_grille['p1']}_{atelier_grille['s1']}" in body


def test_grille_enregistre_ajouts_et_retraits(app, atelier_grille, admin_client):
    from app.models import PresenceActivite
    g = atelier_grille
    paires = f"{g['p1']}:{g['s1']} {g['p1']}:{g['s2']} {g['p2']}:{g['s1']} {g['p2']}:{g['s2']}"
    # p1 décoché de s1 (retrait), p2 coché sur s1 et s2 (ajouts)
    r = admin_client.post(f"/activite/saisie-grille?atelier_id={g['atelier_id']}&mois={g['mois']}",
                          data={"atelier_id": g["atelier_id"], "mois": g["mois"], "paires": paires,
                                f"cell_{g['p2']}_{g['s1']}": "1", f"cell_{g['p2']}_{g['s2']}": "1"})
    assert r.status_code == 302
    with app.app_context():
        assert PresenceActivite.query.filter_by(session_id=g["s1"], participant_id=g["p1"]).count() == 0
        assert PresenceActivite.query.filter_by(participant_id=g["p2"]).count() == 2


def test_grille_protege_les_presences_signees(app, atelier_grille, admin_client):
    from app.extensions import db
    from app.models import PresenceActivite
    g = atelier_grille
    with app.app_context():
        pres = PresenceActivite(session_id=g["s2"], participant_id=g["p1"],
                                signature_path="signatures/x.png")
        db.session.add(pres)
        db.session.commit()
    # Tentative de décochage : la présence signée doit survivre.
    admin_client.post(f"/activite/saisie-grille?atelier_id={g['atelier_id']}&mois={g['mois']}",
                      data={"atelier_id": g["atelier_id"], "mois": g["mois"],
                            "paires": f"{g['p1']}:{g['s2']}"})
    with app.app_context():
        assert PresenceActivite.query.filter_by(session_id=g["s2"], participant_id=g["p1"]).count() == 1
    # Et la grille l'affiche verrouillée, pas en case à cocher.
    body = admin_client.get(f"/activite/saisie-grille?atelier_id={g['atelier_id']}&mois={g['mois']}").get_data(as_text=True)
    assert "🔒" in body


def test_grille_ajoute_une_seance(app, atelier_grille, admin_client):
    from app.models import SessionActivite
    g = atelier_grille
    annee, mois = map(int, g["mois"].split("-"))
    nouvelle = dt.date(annee, mois, 25)
    r = admin_client.post(f"/activite/saisie-grille?atelier_id={g['atelier_id']}&mois={g['mois']}",
                          data={"action": "add_session", "atelier_id": g["atelier_id"],
                                "mois": g["mois"], "date_session": nouvelle.isoformat()})
    assert r.status_code == 302
    with app.app_context():
        assert SessionActivite.query.filter_by(atelier_id=g["atelier_id"], date_session=nouvelle).count() == 1


def test_attente_liste_et_relance(app, atelier_grille, admin_client):
    from app.models import SuiviRappel
    g = atelier_grille
    body = admin_client.get("/activite/emargements-attente").get_data(as_text=True)
    # s2 n'a aucune présence : elle doit apparaître, avec son atelier.
    assert f"Grille{g['suf']}" in body
    assert "en retard de" in body

    # Relance → un rappel ouvert, catégorie émargement
    r = admin_client.post("/activite/emargements-attente/relancer", data={"session_id": g["s2"]})
    assert r.status_code == 302
    with app.app_context():
        rappels = SuiviRappel.query.filter(SuiviRappel.categorie == "emargement",
                                           SuiviRappel.titre.contains(f"Grille{g['suf']}")).all()
        assert len(rappels) == 1
    # Pas de doublon si on relance deux fois
    admin_client.post("/activite/emargements-attente/relancer", data={"session_id": g["s2"]})
    with app.app_context():
        assert SuiviRappel.query.filter(SuiviRappel.categorie == "emargement",
                                        SuiviRappel.titre.contains(f"Grille{g['suf']}")).count() == 1


def test_poste_accueil_montre_le_rattrapage(app, atelier_grille):
    """Un rôle « accueil » créé sur mesure voit l'action avec son compteur."""
    with app.app_context():
        from app.extensions import db
        from app.models import Permission, Role
        role = Role.query.filter_by(code="accueil").first()
        if role is None:
            role = Role(code="accueil", label="Accueil")
            db.session.add(role)
            for code in ("dashboard:view", "participants:view", "participants:edit",
                         "emargement:view", "emargement:edit"):
                perm = Permission.query.filter_by(code=code).first()
                if perm:
                    role.permissions.append(perm)
            db.session.commit()

    _login_role(app, "grille-accueil@example.org", "accueil")
    with app.app_context():
        from app.models import User
        from app.services.poste_travail import build_poste_travail
        u = User.query.filter_by(email="grille-accueil@example.org").first()
        with app.test_request_context():
            poste = build_poste_travail(u)
    action = next(a for a in poste["actions"] if a["key"] == "rattraper_emargements")
    assert "à saisir" in (action["badge"] or "")


def test_grille_lecture_seule_ne_peut_pas_enregistrer(app, atelier_grille):
    """admin_tech (emargement:view sans edit) : consultation oui, POST non."""
    g = atelier_grille
    c = _login_role(app, "grille-tech@example.org", "admin_tech")
    assert c.get("/activite/emargements-attente").status_code == 200
    r = c.post(f"/activite/saisie-grille?atelier_id={g['atelier_id']}&mois={g['mois']}",
               data={"atelier_id": g["atelier_id"], "mois": g["mois"], "paires": ""})
    assert r.status_code == 403
    r = c.post("/activite/emargements-attente/relancer", data={"session_id": g["s2"]})
    assert r.status_code == 403
