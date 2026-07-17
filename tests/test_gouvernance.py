"""Étape 4 — Vie associative : instances, mandats, réunions, quorum, alertes.

- instance + mandats (échéance, échu) ;
- réunion + émargement + quorum (présents + pouvoirs vs quorum requis) ;
- mandats à échéance et alertes « À traiter » (une seule fois) ;
- comptage best-effort des adhérents à jour (base d'un quorum d'AG) ;
- convocation & feuille d'émargement Word ;
- pages protégées et permissions RBAC.
"""
import uuid
from datetime import date, timedelta

import pytest


@pytest.fixture()
def instance_ctx(app):
    suf = uuid.uuid4().hex[:6]
    with app.app_context():
        from app.extensions import db
        from app.models import InstanceGouvernance

        inst = InstanceGouvernance(nom=f"CA {suf}", type_instance="ca")
        db.session.add(inst)
        db.session.commit()
        return {"suf": suf, "instance_id": inst.id}


# ---------------------------------------------------------------------------
# Modèles : mandats & échéances
# ---------------------------------------------------------------------------

def test_mandat_echeance_et_echu(app, instance_ctx):
    with app.app_context():
        from app.extensions import db
        from app.models import Mandat

        proche = Mandat(instance_id=instance_ctx["instance_id"], nom="A. Proche",
                        fonction="president", date_fin=date.today() + timedelta(days=15))
        echu = Mandat(instance_id=instance_ctx["instance_id"], nom="B. Echu",
                      fonction="tresorier", date_fin=date.today() - timedelta(days=5))
        loin = Mandat(instance_id=instance_ctx["instance_id"], nom="C. Loin",
                      fonction="membre", date_fin=date.today() + timedelta(days=300))
        db.session.add_all([proche, echu, loin])
        db.session.commit()

        assert proche.echeance_proche is True and proche.est_echu is False
        assert echu.est_echu is True
        assert loin.echeance_proche is False and loin.est_echu is False


def test_mandats_a_echeance_liste(app, instance_ctx):
    with app.app_context():
        from app.extensions import db
        from app.models import Mandat
        from app.services.gouvernance import mandats_a_echeance

        m = Mandat(instance_id=instance_ctx["instance_id"], nom=f"Echeance {instance_ctx['suf']}",
                   fonction="secretaire", date_fin=date.today() + timedelta(days=20))
        db.session.add(m)
        db.session.commit()
        assert any(x.id == m.id for x in mandats_a_echeance())


# ---------------------------------------------------------------------------
# Quorum
# ---------------------------------------------------------------------------

def test_quorum_calcule(app, instance_ctx):
    with app.app_context():
        from app.extensions import db
        from app.models import Reunion
        from app.services.gouvernance import enregistrer_presence

        reunion = Reunion(instance_id=instance_ctx["instance_id"], titre="AG test",
                          type_reunion="ag_ordinaire", date_reunion=date.today(),
                          base_electeurs=10, quorum_requis=4)
        db.session.add(reunion)
        db.session.commit()

        assert reunion.quorum_atteint is False  # 0 présent
        enregistrer_presence(reunion, "P1", "present")
        enregistrer_presence(reunion, "P2", "present")
        enregistrer_presence(reunion, "R1", "pouvoir", represente_par="P1")
        enregistrer_presence(reunion, "E1", "excuse")
        db.session.refresh(reunion)

        assert reunion.nb_presents == 2
        assert reunion.nb_pouvoirs == 1
        assert reunion.nb_excuses == 1
        assert reunion.total_votes == 3          # présents + pouvoirs
        assert reunion.quorum_atteint is False   # 3 < 4
        enregistrer_presence(reunion, "P3", "present")
        db.session.refresh(reunion)
        assert reunion.total_votes == 4
        assert reunion.quorum_atteint is True


# ---------------------------------------------------------------------------
# Alertes d'échéance (À traiter)
# ---------------------------------------------------------------------------

def test_alertes_mandats_une_seule_fois(app, instance_ctx):
    with app.app_context():
        from app.extensions import db
        from app.models import Mandat, SuiviRappel
        from app.services.gouvernance import alertes_mandats_du_jour

        m = Mandat(instance_id=instance_ctx["instance_id"], nom=f"Alerte {instance_ctx['suf']}",
                   fonction="president", date_fin=date.today() + timedelta(days=10))
        db.session.add(m)
        db.session.commit()

        def _mes_rappels():
            return (SuiviRappel.query
                    .filter(SuiviRappel.categorie == "gouvernance")
                    .filter(SuiviRappel.titre.like(f"%Alerte {instance_ctx['suf']}%"))
                    .count())

        alertes_mandats_du_jour()
        # Mon mandat a été alerté exactement une fois et horodaté.
        assert _mes_rappels() == 1
        assert db.session.get(Mandat, m.id).alerte_echeance_at is not None
        total = SuiviRappel.query.filter_by(categorie="gouvernance").count()

        # Deuxième passe le même jour -> aucun doublon (ni pour le mien, ni global).
        alertes_mandats_du_jour()
        assert _mes_rappels() == 1
        assert SuiviRappel.query.filter_by(categorie="gouvernance").count() == total


# ---------------------------------------------------------------------------
# Adhérents à jour (base quorum AG)
# ---------------------------------------------------------------------------

def test_nombre_adherents_a_jour(app):
    with app.app_context():
        from app.extensions import db
        from app.models import Cotisation, Participant
        from app.services.cotisations import annee_scolaire_courante
        from app.services.gouvernance import nombre_adherents_a_jour

        annee = annee_scolaire_courante()
        avant = nombre_adherents_a_jour(annee)

        p = Participant(nom="Adherent", prenom="Test")
        db.session.add(p)
        db.session.flush()
        # montant_du=0 => soldée => à jour.
        db.session.add(Cotisation(
            annee_scolaire=annee, type_cotisation="adhesion_individuelle",
            participant_id=p.id, montant_du=0, date_reference=date.today(),
        ))
        db.session.commit()

        assert nombre_adherents_a_jour(annee) == avant + 1


# ---------------------------------------------------------------------------
# Documents Word
# ---------------------------------------------------------------------------

def test_convocation_et_emargement_docx(app, instance_ctx):
    with app.app_context():
        from io import BytesIO

        from app.extensions import db
        from app.models import Reunion
        from app.services.gouvernance import (
            construire_convocation_docx,
            construire_emargement_docx,
            enregistrer_presence,
        )

        reunion = Reunion(instance_id=instance_ctx["instance_id"],
                          titre=f"AG {instance_ctx['suf']}", type_reunion="ag_ordinaire",
                          date_reunion=date.today(), heure="18:00", lieu="Grande salle",
                          ordre_du_jour="Rapport moral\nRapport financier", quorum_requis=3)
        db.session.add(reunion)
        db.session.commit()
        enregistrer_presence(reunion, "Membre Un", "present")

        conv = construire_convocation_docx(reunion)
        textes = "\n".join(p.text for p in conv.paragraphs)
        assert f"AG {instance_ctx['suf']}" in textes
        assert "Rapport moral" in textes
        bio = BytesIO(); conv.save(bio); assert bio.tell() > 0

        emarg = construire_emargement_docx(reunion)
        bio2 = BytesIO(); emarg.save(bio2); assert bio2.tell() > 0
        # Le tableau d'émargement contient la personne présente.
        cellules = [c.text for t in emarg.tables for row in t.rows for c in row.cells]
        assert any("Membre Un" == c for c in cellules)


# ---------------------------------------------------------------------------
# Pages & permissions
# ---------------------------------------------------------------------------

def test_dashboard_page(admin_client):
    r = admin_client.get("/gouvernance/")
    assert r.status_code == 200
    assert "Vie associative" in r.get_data(as_text=True)


def test_parcours_complet_via_formulaires(admin_client, app):
    suf = uuid.uuid4().hex[:6]
    # Créer une instance.
    r = admin_client.post("/gouvernance/instances/creer", data={
        "nom": f"Bureau {suf}", "type_instance": "bureau", "description": "test",
    }, follow_redirects=True)
    assert r.status_code == 200

    with app.app_context():
        from app.models import InstanceGouvernance
        inst = InstanceGouvernance.query.filter_by(nom=f"Bureau {suf}").first()
        assert inst is not None
        iid = inst.id

    # Ajouter un mandat.
    admin_client.post(f"/gouvernance/instances/{iid}/mandats/creer", data={
        "nom": "Jean Trésor", "fonction": "tresorier",
        "date_fin": (date.today() + timedelta(days=30)).isoformat(),
    }, follow_redirects=True)

    # Créer une réunion.
    admin_client.post(f"/gouvernance/instances/{iid}/reunions/creer", data={
        "type_reunion": "reunion", "titre": f"CA {suf}",
        "date_reunion": date.today().isoformat(), "quorum_requis": "2",
    }, follow_redirects=True)

    with app.app_context():
        from app.models import Reunion
        reunion = Reunion.query.filter_by(titre=f"CA {suf}").first()
        assert reunion is not None
        rid = reunion.id

    # Émarger + relevé + statut.
    admin_client.post(f"/gouvernance/reunions/{rid}/presence",
                      data={"nom": "Jean Trésor", "etat": "present"}, follow_redirects=True)
    admin_client.post(f"/gouvernance/reunions/{rid}/releve",
                      data={"releve_decisions": "Budget voté."}, follow_redirects=True)

    detail = admin_client.get(f"/gouvernance/reunions/{rid}")
    assert detail.status_code == 200
    assert "Budget voté." in detail.get_data(as_text=True)

    # Documents Word.
    conv = admin_client.get(f"/gouvernance/reunions/{rid}/convocation.docx")
    assert conv.status_code == 200
    assert "wordprocessingml" in conv.headers.get("Content-Type", "")
    emarg = admin_client.get(f"/gouvernance/reunions/{rid}/emargement.docx")
    assert emarg.status_code == 200


def test_refus_anonymes(client):
    assert client.get("/gouvernance/").status_code in (302, 401, 403)
    assert client.post("/gouvernance/instances/creer", data={}).status_code in (302, 401, 403)


def test_permissions_rbac(app):
    with app.app_context():
        from app.models import Permission, Role

        assert Permission.query.filter_by(code="gouvernance:view").first() is not None
        assert Permission.query.filter_by(code="gouvernance:edit").first() is not None
        direction = Role.query.filter_by(code="direction").first()
        codes = {p.code for p in direction.permissions}
        assert {"gouvernance:view", "gouvernance:edit"} <= codes
