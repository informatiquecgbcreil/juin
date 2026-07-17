"""Planning interne v2 — salles (internes/externes), workflow demande →
approbation des réservations et prêts, agenda visuel, notifications.

- une demande de réservation/prêt part en statut ``demandee`` ; un valideur
  (droit ``planning:approve``) l'approuve ou la refuse ;
- seul un créneau *approuvé* bloque un autre créneau (conflit) ;
- le motif de la demande est obligatoire ;
- l'agenda place les éléments qui se chevauchent en colonnes distinctes ;
- notifications : une demande crée un rappel interne « À traiter » ;
- prêt : retard détecté (sur prêt approuvé), retour enregistré ;
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
# Réservations & conflits (seul un créneau APPROUVÉ bloque)
# ---------------------------------------------------------------------------

def test_conflit_sur_reservation_approuvee(app, contexte):
    with app.app_context():
        from app.extensions import db
        from app.models import Salle
        from app.services.planning import ReservationInvalide, demander_reservation

        salle = db.session.get(Salle, contexte["salle_id"])
        jour = contexte["mercredi"]
        demander_reservation(salle=salle, titre="Réunion", jour=jour,
                             heure_debut="14:00", heure_fin="16:00",
                             motif="CA mensuel", auto_approuver=True)

        # Chevauchement (15:00-17:00 croise 14:00-16:00) sur une approuvée -> refusé.
        with pytest.raises(ReservationInvalide, match="déjà réservée"):
            demander_reservation(salle=salle, titre="Autre", jour=jour,
                                 heure_debut="15:00", heure_fin="17:00",
                                 motif="Autre réunion", auto_approuver=True)

        # Créneau accolé (16:00-18:00) -> autorisé (bornes [début, fin[).
        r = demander_reservation(salle=salle, titre="Accolée", jour=jour,
                                 heure_debut="16:00", heure_fin="18:00",
                                 motif="Atelier", auto_approuver=True)
        assert r.id is not None
        assert r.statut == "approuvee"


def test_demande_en_attente_ne_bloque_pas(app, contexte):
    """Une demande non validée ne réserve pas le créneau : une autre demande
    reste possible (c'est le valideur qui arbitre)."""
    with app.app_context():
        from app.extensions import db
        from app.models import Salle
        from app.services.planning import demander_reservation

        salle = db.session.get(Salle, contexte["salle_id"])
        jour = contexte["mercredi"]
        r1 = demander_reservation(salle=salle, titre="Demande A", jour=jour,
                                  heure_debut="14:00", heure_fin="16:00",
                                  motif="Réunion A", auto_approuver=False)
        # Même créneau, autre demande -> acceptée aussi (rien n'est encore approuvé).
        r2 = demander_reservation(salle=salle, titre="Demande B", jour=jour,
                                  heure_debut="14:30", heure_fin="15:30",
                                  motif="Réunion B", auto_approuver=False)
        assert r1.statut == "demandee"
        assert r2.statut == "demandee"


def test_motif_obligatoire(app, contexte):
    with app.app_context():
        from app.extensions import db
        from app.models import Salle
        from app.services.planning import ReservationInvalide, demander_reservation

        salle = db.session.get(Salle, contexte["salle_id"])
        with pytest.raises(ReservationInvalide, match="motif"):
            demander_reservation(salle=salle, titre="Sans motif", jour=contexte["mercredi"],
                                 heure_debut="09:00", heure_fin="10:00", motif="")


def test_reservation_heures_incoherentes(app, contexte):
    with app.app_context():
        from app.extensions import db
        from app.models import Salle
        from app.services.planning import ReservationInvalide, demander_reservation

        salle = db.session.get(Salle, contexte["salle_id"])
        with pytest.raises(ReservationInvalide, match="après l'heure de début"):
            demander_reservation(salle=salle, titre="X", jour=contexte["mercredi"],
                                 heure_debut="16:00", heure_fin="14:00", motif="test")


def test_workflow_approbation(app, contexte):
    with app.app_context():
        from app.extensions import db
        from app.models import Salle
        from app.services.planning import (
            approuver_reservation,
            demander_reservation,
            reservations_en_attente,
        )

        secteur = f"Sec{contexte['suf']}"
        salle = db.session.get(Salle, contexte["salle_id"])
        r = demander_reservation(salle=salle, titre=f"Demande {contexte['suf']}",
                                 jour=contexte["mercredi"], heure_debut="09:00",
                                 heure_fin="10:00", motif="Réunion d'équipe",
                                 secteur=secteur, auto_approuver=False)
        assert r.statut == "demandee"
        assert any(x.id == r.id for x in reservations_en_attente(secteur))

        approuver_reservation(r, approbateur=None)
        assert r.statut == "approuvee"
        assert not any(x.id == r.id for x in reservations_en_attente(secteur))


def test_refus_avec_motif(app, contexte):
    with app.app_context():
        from app.extensions import db
        from app.models import Salle
        from app.services.planning import demander_reservation, refuser_reservation

        salle = db.session.get(Salle, contexte["salle_id"])
        r = demander_reservation(salle=salle, titre="À refuser", jour=contexte["mercredi"],
                                 heure_debut="09:00", heure_fin="10:00",
                                 motif="test", auto_approuver=False)
        refuser_reservation(r, approbateur=None, motif_refus="Salle indisponible")
        assert r.statut == "refusee"
        assert r.motif_refus == "Salle indisponible"


# ---------------------------------------------------------------------------
# Agenda visuel : placement en colonnes des chevauchements
# ---------------------------------------------------------------------------

def test_agencement_colonnes_chevauchement():
    from app.services.planning import _agencer_en_colonnes

    elements = [
        {"titre": "A", "debut_min": 540, "fin_min": 660},   # 09:00-11:00
        {"titre": "B", "debut_min": 600, "fin_min": 720},   # 10:00-12:00 (chevauche A)
        {"titre": "C", "debut_min": 780, "fin_min": 840},   # 13:00-14:00 (isolé)
        {"titre": "Z", "debut_min": 0, "fin_min": 0},       # sans horaire (ignoré)
    ]
    _agencer_en_colonnes(elements)
    par_titre = {e["titre"]: e for e in elements}
    # A et B se chevauchent -> deux colonnes, lanes distinctes.
    assert par_titre["A"]["lanes"] == 2
    assert par_titre["B"]["lanes"] == 2
    assert par_titre["A"]["lane"] != par_titre["B"]["lane"]
    # C est seul sur son créneau -> une seule colonne.
    assert par_titre["C"]["lanes"] == 1
    # Z n'a pas d'horaire -> non agencé.
    assert "lane" not in par_titre["Z"]


# ---------------------------------------------------------------------------
# Vue semaine
# ---------------------------------------------------------------------------

def test_semaine_agrege_seances_et_reservations(app, contexte):
    with app.app_context():
        from app.extensions import db
        from app.models import Salle
        from app.services.planning import demander_reservation, semaine_equipe

        secteur = f"Sec{contexte['suf']}"
        salle = db.session.get(Salle, contexte["salle_id"])
        demander_reservation(salle=salle, titre=f"Réu {contexte['suf']}", jour=contexte["mercredi"],
                             heure_debut="14:00", heure_fin="16:00", motif="CA",
                             secteur=secteur, auto_approuver=True)

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
        # Chaque élément horodaté porte son placement en colonnes (agenda).
        for e in mercredi["elements"]:
            if e["fin_min"] > e["debut_min"]:
                assert e["lanes"] >= 1


# ---------------------------------------------------------------------------
# Prêts de matériel (workflow + retard)
# ---------------------------------------------------------------------------

def test_pret_retard_et_retour(app, contexte):
    with app.app_context():
        from app.extensions import db
        from app.models import PretMateriel
        from app.services.planning import enregistrer_retour, prets_en_cours, prets_en_retard

        # Prêt APPROUVÉ dont le retour prévu est déjà passé.
        pret = PretMateriel(
            item_id=contexte["item_id"], emprunteur="Partenaire X", quantite=1,
            motif="Fête de quartier", statut="approuvee",
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


def test_pret_workflow(app, contexte):
    with app.app_context():
        from app.extensions import db
        from app.models import InventaireItem
        from app.services.planning import (
            approuver_pret,
            demander_pret,
            prets_en_attente,
            prets_en_cours,
        )

        secteur = f"Sec{contexte['suf']}"
        item = db.session.get(InventaireItem, contexte["item_id"])
        p = demander_pret(item=item, emprunteur=f"Asso {contexte['suf']}",
                          motif="Projection en plein air", auto_approuver=False)
        assert p.statut == "demandee"
        assert any(x.id == p.id for x in prets_en_attente(secteur))
        assert not any(x.id == p.id for x in prets_en_cours(secteur))

        approuver_pret(p, approbateur=None)
        assert p.statut == "approuvee"
        assert any(x.id == p.id for x in prets_en_cours(secteur))


def test_pret_motif_obligatoire(app, contexte):
    with app.app_context():
        from app.extensions import db
        from app.models import InventaireItem
        from app.services.planning import ReservationInvalide, demander_pret

        item = db.session.get(InventaireItem, contexte["item_id"])
        with pytest.raises(ReservationInvalide, match="motif"):
            demander_pret(item=item, emprunteur="Sans motif", motif="")


# ---------------------------------------------------------------------------
# Notifications : une demande crée un rappel interne « À traiter »
# ---------------------------------------------------------------------------

def test_notifier_demande_cree_rappel_interne(app, contexte):
    with app.app_context():
        from app.models import SuiviRappel
        from app.services.planning_notifs import notifier_demande

        intitule = f"Réservation-{contexte['suf']}"
        avant = SuiviRappel.query.filter_by(categorie="planning").count()
        notifier_demande(
            type_libelle="Réservation de salle", intitule=intitule,
            demandeur="Testeur", detail="Le 01/01 de 09:00 à 10:00. Motif : test.",
            secteur=f"Sec{contexte['suf']}", lien_url="/planning/",
        )
        apres = SuiviRappel.query.filter_by(categorie="planning").count()
        assert apres == avant + 1
        rappel = (SuiviRappel.query
                  .filter(SuiviRappel.categorie == "planning")
                  .filter(SuiviRappel.titre.like(f"%{intitule}%"))
                  .first())
        assert rappel is not None


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
    # L'admin (rôle direction) a planning:approve -> réservation auto-approuvée.
    r = admin_client.post("/planning/reservations/creer", data={
        "salle_id": contexte["salle_id"],
        "titre": f"Réunion {contexte['suf']}",
        "date_reservation": contexte["mercredi"].isoformat(),
        "heure_debut": "09:00", "heure_fin": "10:00",
        "motif": "Réunion de service",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert "réservée le" in r.get_data(as_text=True)

    # Deuxième réservation en conflit avec l'approuvée -> avertissement.
    r = admin_client.post("/planning/reservations/creer", data={
        "salle_id": contexte["salle_id"],
        "titre": "Conflit",
        "date_reservation": contexte["mercredi"].isoformat(),
        "heure_debut": "09:30", "heure_fin": "10:30",
        "motif": "autre",
    }, follow_redirects=True)
    assert "déjà réservée" in r.get_data(as_text=True)


def test_reservation_formulaire_sans_motif_refuse(admin_client, contexte):
    r = admin_client.post("/planning/reservations/creer", data={
        "salle_id": contexte["salle_id"],
        "titre": "Sans motif",
        "date_reservation": contexte["mercredi"].isoformat(),
        "heure_debut": "11:00", "heure_fin": "12:00",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert "motif" in r.get_data(as_text=True).lower()


def test_salle_externe_via_formulaire(admin_client, app):
    suf = uuid.uuid4().hex[:6]
    r = admin_client.post("/planning/salles", data={
        "nom": f"Gymnase {suf}",
        "est_externe": "1",
        "adresse": "10 rue du Stade, Creil",
        "contact": "Mairie · 03.44...",
    }, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        from app.models import Salle
        salle = Salle.query.filter_by(nom=f"Gymnase {suf}").first()
        assert salle is not None
        assert salle.est_externe is True
        assert salle.adresse == "10 rue du Stade, Creil"
        assert salle.type_label == "Externe"


def test_page_prets_et_creation(admin_client, app, contexte):
    r = admin_client.get("/planning/prets")
    assert r.status_code == 200
    assert "Prêts de matériel" in r.get_data(as_text=True)

    r = admin_client.post("/planning/prets/creer", data={
        "item_id": contexte["item_id"],
        "emprunteur": f"Ludo {contexte['suf']}",
        "quantite": "1",
        "motif": "Animation de rue",
        "date_pret": date.today().isoformat(),
    }, follow_redirects=True)
    assert r.status_code == 200
    assert "enregistré ✅" in r.get_data(as_text=True)

    with app.app_context():
        from app.models import PretMateriel
        pret = PretMateriel.query.filter(
            PretMateriel.emprunteur == f"Ludo {contexte['suf']}").first()
        assert pret is not None
        # L'admin approuve d'office -> le prêt est directement en cours.
        assert pret.statut == "approuvee"


def test_refus_anonymes(client):
    assert client.get("/planning/").status_code in (302, 401, 403)
    assert client.get("/planning/prets").status_code in (302, 401, 403)
    assert client.post("/planning/reservations/creer", data={}).status_code in (302, 401, 403)


def test_permissions_rbac(app):
    with app.app_context():
        from app.models import Permission, Role

        assert Permission.query.filter_by(code="planning:view").first() is not None
        assert Permission.query.filter_by(code="planning:edit").first() is not None
        assert Permission.query.filter_by(code="planning:approve").first() is not None
        direction = Role.query.filter_by(code="direction").first()
        codes = {p.code for p in direction.permissions}
        assert {"planning:view", "planning:edit", "planning:approve"} <= codes


# ---------------------------------------------------------------------------
# Location payante (salles & matériel)
# ---------------------------------------------------------------------------

def test_location_reservation_service(app, contexte):
    with app.app_context():
        from app.extensions import db
        from app.models import Salle
        from app.services.locations import marquer_paye
        from app.services.planning import demander_reservation

        salle = db.session.get(Salle, contexte["salle_id"])
        r = demander_reservation(
            salle=salle, titre=f"Loc {contexte['suf']}", jour=contexte["mercredi"],
            heure_debut="18:00", heure_fin="23:00", motif="Anniversaire",
            secteur=f"Sec{contexte['suf']}", auto_approuver=True,
            est_location=True, locataire="Famille Martin", contact="06 00 00 00 00",
            tarif_montant=120, tarif_unite="forfait", caution_montant=200,
        )
        assert r.est_location is True
        assert r.tarif_montant == 120.0
        assert r.caution_montant == 200.0
        assert r.est_paye is False
        assert r.caution_a_rendre is True

        marquer_paye(r, mode="cheque")
        assert r.est_paye is True
        assert r.paiement_statut == "regle"
        assert r.paiement_mode == "cheque"


def test_location_montant_obligatoire(app, contexte):
    with app.app_context():
        from app.extensions import db
        from app.models import Salle
        from app.services.planning import ReservationInvalide, demander_reservation

        salle = db.session.get(Salle, contexte["salle_id"])
        with pytest.raises(ReservationInvalide, match="montant"):
            demander_reservation(
                salle=salle, titre="Loc sans prix", jour=contexte["mercredi"],
                heure_debut="18:00", heure_fin="19:00", motif="test",
                est_location=True, locataire="X", tarif_montant=0,
            )


def test_location_locataire_obligatoire(app, contexte):
    with app.app_context():
        from app.extensions import db
        from app.models import Salle
        from app.services.planning import ReservationInvalide, demander_reservation

        salle = db.session.get(Salle, contexte["salle_id"])
        with pytest.raises(ReservationInvalide, match="locataire"):
            demander_reservation(
                salle=salle, titre="Loc sans locataire", jour=contexte["mercredi"],
                heure_debut="18:00", heure_fin="19:00", motif="test",
                est_location=True, locataire="", tarif_montant=50,
            )


def test_location_a_encaisser_et_recettes(app, contexte):
    with app.app_context():
        from app.extensions import db
        from app.models import InventaireItem
        from app.services.locations import (
            locations_a_encaisser,
            marquer_paye,
            recettes_encaissees,
        )
        from app.services.planning import demander_pret

        secteur = f"Sec{contexte['suf']}"
        item = db.session.get(InventaireItem, contexte["item_id"])
        p = demander_pret(
            item=item, emprunteur="Asso voisine", motif="Kermesse",
            auto_approuver=True, est_location=True, tarif_montant=80,
            tarif_unite="jour", caution_montant=100,
        )
        # Tant que non réglé -> figure dans « à encaisser ».
        a_enc = locations_a_encaisser(secteur)
        assert any(x.id == p.id for x in a_enc["prets"])

        marquer_paye(p, mode="virement")
        a_enc = locations_a_encaisser(secteur)
        assert not any(x.id == p.id for x in a_enc["prets"])

        # Réglé aujourd'hui -> compte dans les recettes de l'année.
        from datetime import date
        rec = recettes_encaissees(date(date.today().year, 1, 1), date.today(), secteur)
        assert any(x.id == p.id for x in rec["prets"])
        assert rec["total"] >= 80.0


def test_caution_a_rendre_puis_rendue(app, contexte):
    with app.app_context():
        from app.extensions import db
        from app.models import Salle
        from app.services.locations import cautions_a_rendre, marquer_caution_rendue
        from app.services.planning import demander_reservation

        secteur = f"Sec{contexte['suf']}"
        salle = db.session.get(Salle, contexte["salle_id"])
        r = demander_reservation(
            salle=salle, titre="Avec caution", jour=contexte["mercredi"],
            heure_debut="08:00", heure_fin="09:00", motif="test", secteur=secteur,
            auto_approuver=True, est_location=True, locataire="Y", tarif_montant=40,
            caution_montant=150,
        )
        assert any(x.id == r.id for x in cautions_a_rendre(secteur))
        marquer_caution_rendue(r)
        assert not any(x.id == r.id for x in cautions_a_rendre(secteur))


def test_convention_docx(app, contexte):
    with app.app_context():
        from io import BytesIO

        from app.extensions import db
        from app.models import Salle
        from app.services.locations import construire_convention_docx
        from app.services.planning import demander_reservation

        salle = db.session.get(Salle, contexte["salle_id"])
        r = demander_reservation(
            salle=salle, titre="Conv", jour=contexte["mercredi"],
            heure_debut="10:00", heure_fin="12:00", motif="réunion partenaire",
            auto_approuver=True, est_location=True, locataire="Association Y",
            tarif_montant=90, tarif_unite="forfait", caution_montant=100,
        )
        doc = construire_convention_docx(r)
        textes = "\n".join(p.text for p in doc.paragraphs)
        assert "Convention" in "\n".join(h.text for h in doc.paragraphs) or "Convention" in textes
        assert "Association Y" in textes
        assert "90" in textes  # montant

        bio = BytesIO()
        doc.save(bio)
        assert bio.tell() > 0


def test_location_via_formulaire_et_convention(admin_client, app, contexte):
    r = admin_client.post("/planning/reservations/creer", data={
        "salle_id": contexte["salle_id"],
        "titre": f"Location {contexte['suf']}",
        "date_reservation": contexte["mercredi"].isoformat(),
        "heure_debut": "19:00", "heure_fin": "23:00",
        "motif": "Fête privée",
        "est_location": "1",
        "locataire": "M. Dupont",
        "tarif_montant": "150",
        "tarif_unite": "forfait",
        "caution_montant": "300",
    }, follow_redirects=True)
    assert r.status_code == 200

    with app.app_context():
        from app.models import ReservationSalle
        res = ReservationSalle.query.filter_by(titre=f"Location {contexte['suf']}").first()
        assert res is not None
        assert res.est_location is True
        assert res.tarif_montant == 150.0
        assert res.locataire == "M. Dupont"
        rid = res.id

    # La page Locations s'affiche et la convention Word se télécharge.
    assert admin_client.get("/planning/locations").status_code == 200
    conv = admin_client.get(f"/planning/reservations/{rid}/convention")
    assert conv.status_code == 200
    assert "wordprocessingml" in conv.headers.get("Content-Type", "")

    # Marquer réglé.
    pay = admin_client.post(f"/planning/reservations/{rid}/payer",
                            data={"paiement_mode": "cheque"}, follow_redirects=True)
    assert pay.status_code == 200
    with app.app_context():
        from app.extensions import db
        from app.models import ReservationSalle
        assert db.session.get(ReservationSalle, rid).est_paye is True
