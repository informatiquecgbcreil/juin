"""Le portail se fond dans les stats pédagogiques (niveau effectif = max manuel/portail)."""
import datetime as dt
import uuid


def _competence():
    from app.extensions import db
    from app.models import Competence, Referentiel

    suf = uuid.uuid4().hex[:6]
    ref = Referentiel(nom=f"Ref {suf}")
    db.session.add(ref)
    db.session.flush()
    code = f"P-{suf}"
    c = Competence(referentiel_id=ref.id, code=code, nom="Comp")
    db.session.add(c)
    db.session.commit()
    return c.id, code


def test_niveaux_portail_par_paire(app):
    from app.extensions import db
    from app.models import Participant, PortailAttempt, PortailCompetenceMap
    from app.pedagogie.services import niveaux_portail_par_paire

    with app.app_context():
        cid, _ = _competence()
        p = Participant(nom="N", prenom="P", type_public="H")
        db.session.add(p)
        db.session.flush()
        pid = p.id
        db.session.add(PortailCompetenceMap(activity="ExA", competence_id=cid, seuil_pct=80, actif=True))
        db.session.add(PortailAttempt(attempt_id="x1", external_id=str(pid), participant_id=pid,
                                      activity="ExA", pct=90, score=90, max_score=100,
                                      finished_at=dt.datetime(2026, 6, 20, 10, 0)))
        db.session.commit()

        res = niveaux_portail_par_paire({cid})
        assert res.get((pid, cid)) == 3  # 1/1 réussi → N3


def test_participant_timeline_enrichi(app):
    from app.extensions import db
    from app.models import Participant, PortailAttempt, PortailCompetenceMap
    from app.pedagogie.services import participant_timeline

    with app.app_context():
        cid, _ = _competence()
        p = Participant(nom="Tl", prenom="P", type_public="H")
        db.session.add(p)
        db.session.flush()
        pid = p.id
        db.session.add(PortailCompetenceMap(activity="ExT", competence_id=cid, seuil_pct=80, actif=True))
        db.session.add(PortailAttempt(attempt_id="t1", external_id=str(pid), participant_id=pid,
                                      activity="ExT", pct=85, score=85, max_score=100,
                                      finished_at=dt.datetime(2026, 6, 20, 10, 0)))
        db.session.commit()

        _participant, _events, current_levels = participant_timeline(pid)
        assert current_levels.get(cid) == 3  # enrichi par le portail, sans évaluation manuelle


def test_bilan_rows_inclut_portail(app):
    from app.extensions import db
    from app.models import Participant, PortailAttempt, PortailCompetenceMap
    from app.statsimpact.pedagogie import _build_bilan_rows

    with app.app_context():
        cid, code = _competence()
        p = Participant(nom="Bil", prenom="P", type_public="H")
        db.session.add(p)
        db.session.flush()
        db.session.add(PortailCompetenceMap(activity="ExB", competence_id=cid, seuil_pct=80, actif=True))
        db.session.add(PortailAttempt(attempt_id="b1", external_id=str(p.id), participant_id=p.id,
                                      activity="ExB", pct=95, score=95, max_score=100,
                                      finished_at=dt.datetime(2026, 6, 20, 10, 0)))
        db.session.commit()

        rows = _build_bilan_rows(p)
        assert any(code in r["competence"] for r in rows)
        assert any(r["atelier"] == "Portail" for r in rows)
