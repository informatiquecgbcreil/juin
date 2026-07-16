"""Étape 3 — Planning interne : salles, réservations, prêts de matériel.

- réservation refusée si chevauchement sur la même salle le même jour ;
- créneaux qui ne se chevauchent pas : OK ;
- vue semaine agrège séances + réservations sur lundi→dimanche ;
- prêt : création, retard détecté, retour enregistré ;
- pages protégées ; permissions RBAC attribuées.
"""
import uuid
from datetime import date, timedelta

import pytest


@pytest.fixture()
def contexte(app):
    """Une salle, un atelier avec une séance cette semaine, un item d'inventaire."""
    suf = uuid.uuid4().hex[:6]
    with app.app_context():
        from app.extensions import db
        from app.models import AtelierActivite, InventaireItem, Salle, SessionActivite

        salle = Salle(nom=f"Grande salle {suf}", capacite=20, couleur="#2563eb")
        atelier = AtelierActivite(nom=f"Atelier {suf}", secteur=f"Sec{suf}")
        db.session.add_all([salle, atelier])
        db.session.flush()

        # Séance mercredi de cette semaine.
        lundi = date.today() - timedelta(days=date.today().weekday())
        mercredi = lundi + timedelta(days=2)
        seance = SessionActivite(
            atelier_id=atelier.id, secteur=f"Sec{suf}", session_type="COLLECTIF",
            date_session=mercredi, heure_debut="10:00", heure_fin="12:00", statut="realisee",
        )
        item = InventaireItem(
            secteur=f"Sec{suf}", id_interne=f"INV-{suf}", designation=f"Vidéoprojecteur {suf}",
            quantite=1,
        )
        db.session.add_all([seance, item])
        db.session.commit()
        return {"suf": suf, "salle_id": salle.id, "atelier_id": atelier.id,
                "item_id": item.id, "mercredi": mercredi, "lundi": lundi}


# ---------------------------------------------------------------------------
# Réservations & conflits
# ---------------------------------------------------------------------------

def test_conflit_reservation_refuse(app, contexte):
    with app.app_context():
        from app.extensions import db
        from app.models import Salle
        from app.services.planning import ReservationInvalide, creer_reservation

        salle = db.session.get(Salle, contexte["salle_id"])
        jour = contexte["mercredi"]
        creer_reservation(salle=salle, titre="Réunion", jour=jour,
                          heure_debut="14:00", heure_fin="16:00")

        # Chevauchement (15:00-17:00 croise 14:00-16:00) -> refusé.
        with pytest.raises(ReservationInvalide, match="déjà réservée"):
            creer_reservation(salle=salle, titre="Autre", jour=jour,
                              heure_debut="15:00", heure_fin="17:00")

        # Créneau accolé (16:00-18:00) -> autorisé (bornes [début, fin[).
        r = creer_reservation(salle=salle, titre="Accolée", jour=jour,
                              heure_debut="16:00", heure_fin="18:00")
        assert r.id is not None


def test_reservation_heures_incoherentes(app, contexte):
    with app.app_context():
        from app.extensions import db
        from app.models import Salle
        from app.services.planning import ReservationInvalide, creer_reservation

        salle = db.session.get(Salle, contexte["salle_id"])
        with pytest.raises(ReservationInvalide, match="après l'heure de début"):
            creer_reservation(salle=salle, titre="X", jour=contexte["mercredi"],
                              heure_debut="16:00", heure_fin="14:00")


def test_autre_jour_pas_de_conflit(app, contexte):
    with app.app_context():
        from app.extensions import db
        from app.models import Salle
        from app.services.planning import conflits_reservation, creer_reservation

        salle = db.session.get(Salle, contexte["salle_id"])
        creer_reservation(salle=salle, titre="Lundi", jour=contexte["lundi"],
                          heure_debut="14:00", heure_fin="16:00")
        # Même créneau, autre jour -> aucun conflit.
        assert conflits_reservation(salle.id, contexte["mercredi"], "14:00", "16:00") == []


# ---------------------------------------------------------------------------
# Vue semaine
# ---------------------------------------------------------------------------

def test_semaine_agrege_seances_et_reservations(app, contexte):
    with app.app_context():
        from app.extensions import db
        from app.models import Salle
        from app.services.planning import creer_reservation, semaine_equipe

        secteur = f"Sec{contexte['suf']}"
        salle = db.session.get(Salle, contexte["salle_id"])
        creer_reservation(salle=salle, titre=f"Réu {contexte['suf']}", jour=contexte["mercredi"],
                          heure_debut="14:00", heure_fin="16:00", secteur=secteur)

        # Filtrage sur le secteur unique du contexte : la vue ne contient que
        # les données de ce test (la base de test est partagée).
        data = semaine_equipe(contexte["mercredi"], secteur=secteur)
        assert data["lundi"] == contexte["lundi"]
        assert len(data["jours"]) == 7

        mercredi = next(j for j in data["jours"] if j["date"] == contexte["mercredi"])
        types = {(e["type"], e["titre"]) for e in mercredi["elements"]}
        assert ("seance", f"Atelier {contexte['suf']}") in types
        assert ("reservation", f"Réu {contexte['suf']}") in types
        assert mercredi["nb_seances"] == 1
        # Les salles partagées (secteur nul) restent visibles quel que soit le
        # filtre : au moins la réservation de ce test est présente.
        assert mercredi["nb_reservations"] >= 1
        # Tri par heure : la séance (10:00) avant la réservation (14:00).
        titres_ordonnes = [e["titre"] for e in mercredi["elements"]]
        assert titres_ordonnes.index(f"Atelier {contexte['suf']}") < titres_ordonnes.index(f"Réu {contexte['suf']}")


# ---------------------------------------------------------------------------
# Prêts de matériel
# ---------------------------------------------------------------------------

def test_pret_retard_et_retour(app, contexte):
    with app.app_context():
        from app.extensions import db
        from app.models import PretMateriel
        from app.services.planning import enregistrer_retour, prets_en_cours, prets_en_retard

        # Prêt dont le retour prévu est déjà passé.
        pret = PretMateriel(
            item_id=contexte["item_id"], emprunteur="Partenaire X", quantite=1,
            date_pret=date.today() - timedelta(days=10),
            date_retour_prevue=date.today() - timedelta(days=3),
        )
        db.session.add(pret)
        db.session.commit()
        pid = pret.id

        assert pret.en_retard is True
        assert pret.statut_label == "En retard"
        assert any(p.id == pid for p in prets_en_cours())
        assert any(p.id == pid for p in prets_en_retard())

        enregistrer_retour(pret)
        pret = db.session.get(PretMateriel, pid)
        assert pret.est_rendu is True
        assert pret.en_retard is False
        assert not any(p.id == pid for p in prets_en_cours())


# ---------------------------------------------------------------------------
# Pages & permissions
# ---------------------------------------------------------------------------

def test_page_semaine(admin_client, contexte):
    r = admin_client.get(f"/planning/?jour={contexte['mercredi'].isoformat()}")
    assert r.status_code == 200
    page = r.get_data(as_text=True)
    assert "Planning de l'équipe" in page
    assert f"Atelier {contexte['suf']}" in page


def test_reservation_via_formulaire(admin_client, app, contexte):
    r = admin_client.post("/planning/reservations/creer", data={
        "salle_id": contexte["salle_id"],
        "titre": f"Réunion {contexte['suf']}",
        "date_reservation": contexte["mercredi"].isoformat(),
        "heure_debut": "09:00", "heure_fin": "10:00",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert "réservée le" in r.get_data(as_text=True)

    # Deuxième réservation en conflit -> message d'avertissement.
    r = admin_client.post("/planning/reservations/creer", data={
        "salle_id": contexte["salle_id"],
        "titre": "Conflit",
        "date_reservation": contexte["mercredi"].isoformat(),
        "heure_debut": "09:30", "heure_fin": "10:30",
    }, follow_redirects=True)
    assert "déjà réservée" in r.get_data(as_text=True)


def test_page_prets_et_creation(admin_client, app, contexte):
    r = admin_client.get("/planning/prets")
    assert r.status_code == 200
    assert "Prêts de matériel" in r.get_data(as_text=True)

    r = admin_client.post("/planning/prets/creer", data={
        "item_id": contexte["item_id"],
        "emprunteur": f"Ludo {contexte['suf']}",
        "quantite": "1",
        "date_pret": date.today().isoformat(),
    }, follow_redirects=True)
    assert r.status_code == 200
    assert "enregistré ✅" in r.get_data(as_text=True)

    with app.app_context():
        from app.models import PretMateriel
        assert PretMateriel.query.filter(
            PretMateriel.emprunteur == f"Ludo {contexte['suf']}").count() == 1


def test_refus_anonymes(client):
    assert client.get("/planning/").status_code in (302, 401, 403)
    assert client.get("/planning/prets").status_code in (302, 401, 403)
    assert client.post("/planning/reservations/creer", data={}).status_code in (302, 401, 403)


def test_permissions_rbac(app):
    with app.app_context():
        from app.models import Permission, Role

        assert Permission.query.filter_by(code="planning:view").first() is not None
        assert Permission.query.filter_by(code="planning:edit").first() is not None
        direction = Role.query.filter_by(code="direction").first()
        codes = {p.code for p in direction.permissions}
        assert {"planning:view", "planning:edit"} <= codes
