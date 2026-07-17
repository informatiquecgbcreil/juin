"""Recherche globale — couverture des types ajoutés (P2 ergonomie) :
salles, matériel d'inventaire, instances, mandats, réunions.

Les types historiques (participants, projets…) sont couverts indirectement
par leurs modules ; ici on vérifie que les nouveaux apparaissent, avec le
bon lien, et que les filtres ``type:`` fonctionnent.
"""
import uuid
from datetime import date

import pytest


@pytest.fixture()
def donnees(app):
    suf = uuid.uuid4().hex[:6]
    with app.app_context():
        from app.extensions import db
        from app.models import (
            InstanceGouvernance,
            InventaireItem,
            Mandat,
            Reunion,
            Salle,
        )

        salle = Salle(nom=f"Salleverte {suf}", capacite=25, est_externe=True,
                      adresse="2 rue des Tests", contact="Mairie")
        item = InventaireItem(secteur=f"Sec{suf}", id_interne=f"REC-{suf}",
                              designation=f"Sono portable {suf}", quantite=1)
        inst = InstanceGouvernance(nom=f"Conseil {suf}", type_instance="ca")
        db.session.add_all([salle, item, inst])
        db.session.flush()
        mandat = Mandat(instance_id=inst.id, nom=f"Presidente {suf}", fonction="president")
        reunion = Reunion(instance_id=inst.id, titre=f"Pleniere {suf}",
                          date_reunion=date.today())
        db.session.add_all([mandat, reunion])
        db.session.commit()
        return {"suf": suf, "instance_id": inst.id, "item_id": item.id,
                "reunion_id": reunion.id}


def _chercher(admin_client, q):
    r = admin_client.get(f"/api/global-search?q={q}")
    assert r.status_code == 200
    return r.get_json()["results"]


def test_salle_trouvee(admin_client, donnees):
    resultats = _chercher(admin_client, f"Salleverte {donnees['suf']}")
    salles = [x for x in resultats if x["type"] == "Salle"]
    assert salles, resultats
    assert "Externe" in salles[0]["meta"]


def test_materiel_trouve_avec_lien_fiche(admin_client, donnees):
    resultats = _chercher(admin_client, f"Sono {donnees['suf']}")
    materiels = [x for x in resultats if x["type"] == "Matériel"]
    assert materiels, resultats
    assert f"/{donnees['item_id']}" in materiels[0]["url"]


def test_instance_mandat_reunion_trouves(admin_client, donnees):
    suf = donnees["suf"]
    types = {x["type"] for x in _chercher(admin_client, f"Conseil {suf}")}
    assert "Instance" in types

    mandats = [x for x in _chercher(admin_client, f"Presidente {suf}") if x["type"] == "Mandat"]
    assert mandats
    assert "Président·e" in mandats[0]["meta"]

    reunions = [x for x in _chercher(admin_client, f"Pleniere {suf}") if x["type"] == "Réunion"]
    assert reunions
    assert f"/{donnees['reunion_id']}" in reunions[0]["url"]


def test_filtre_type_salle(admin_client, donnees):
    resultats = _chercher(admin_client, f"type:salle {donnees['suf']}")
    assert resultats
    assert all(x["type"] == "Salle" for x in resultats)


def test_recherche_anonyme_refusee(client):
    assert client.get("/api/global-search?q=test").status_code in (302, 401, 403)
