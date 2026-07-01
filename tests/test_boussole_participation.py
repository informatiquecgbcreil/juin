"""Boussole participation : saisie structurée, stats sectorisées et passeport."""
import datetime as dt
import json
import uuid


def _participant(app, nom="Boussole"):
    from app.extensions import db
    from app.models import Participant

    with app.app_context():
        p = Participant(nom=f"{nom}{uuid.uuid4().hex[:6]}", prenom="Habitant", type_public="H")
        db.session.add(p)
        db.session.commit()
        return p.id


def test_saisie_boussole_passeport_champs_structures(admin_client, app):
    from app.extensions import db
    from app.models import BoussoleParticipation

    pid = _participant(app)
    r = admin_client.post(
        f"/pedagogie/participant/{pid}/passeport/participation",
        data={
            "secteur": "Familles",
            "niveau": "4",
            "date_observation": "2026-07-01",
            "jalon": "5_presences",
            "source": "partagee",
            "indicators": ["idee_proposee", "organisation"],
            "remarque": "A aidé à préparer la salle.",
            "temoignage": "Je me sens plus à l'aise.",
        },
        follow_redirects=True,
    )
    page = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Boussole participation" in page
    assert "A aidé à préparer la salle" in page

    with app.app_context():
        row = BoussoleParticipation.query.filter_by(participant_id=pid, secteur="Familles").one()
        assert row.niveau == 4
        assert row.evolution == "initiale"
        assert json.loads(row.indicators_json) == ["idee_proposee", "organisation"]
        assert row.remarque == "A aidé à préparer la salle."


def test_stats_collectives_conservent_une_position_par_secteur(admin_client, app):
    from app.extensions import db
    from app.models import BoussoleParticipation
    from app.services.participation import collective_stats

    pid = _participant(app, "Multi")
    with app.app_context():
        db.session.add(BoussoleParticipation(participant_id=pid, secteur="Familles", niveau=6, date_observation=dt.date(2026, 7, 1)))
        db.session.add(BoussoleParticipation(participant_id=pid, secteur="Numérique", niveau=2, date_observation=dt.date(2026, 7, 1)))
        db.session.commit()
        stats = collective_stats()
        assert stats["counts"][6] >= 1
        assert stats["counts"][2] >= 1
        assert (pid, "Familles") in stats["latest"]
        assert (pid, "Numérique") in stats["latest"]

    page = admin_client.get("/pedagogie/participation").get_data(as_text=True)
    assert "Boussole participation" in page
    assert "Détail par étape" in page
    assert "Familles" in page
    assert "Numérique" in page


def test_boussole_trouvable_ressources_stats_et_bilans(admin_client, app):
    ressources = admin_client.get("/ressources").get_data(as_text=True)
    assert "Boussole participation" in ressources
    assert "/pedagogie/participation" in ressources

    stats = admin_client.get("/stats-bilans").get_data(as_text=True)
    assert "Pouvoir d’agir" in stats
    assert "Ouvrir la boussole" in stats

    bilans = admin_client.get("/bilans/lourds?year=2026").get_data(as_text=True)
    assert "boussole participation" in bilans.lower()
