from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import func

from app.extensions import db
from app.models import BoussoleParticipation, Participant, PresenceActivite, SessionActivite

PARTICIPATION_STEPS = [
    (1, "Je découvre", "Découverte du lieu, d'une action ou d'un secteur."),
    (2, "Je participe", "Présence à une activité ou un service proposé."),
    (3, "Je m’exprime", "Avis, besoin, envie, critique ou proposition formulée."),
    (4, "Je contribue", "Coup de main, relais, entraide ou aide à l'organisation."),
    (5, "Je co-construis", "Préparation, choix ou adaptation d'une action avec l'équipe."),
    (6, "Je prends des responsabilités", "Rôle reconnu, régulier ou référent dans l'action."),
    (7, "J’initie", "Initiative habitante portée avec l'appui du centre."),
    (8, "Je transmets / représente / transforme", "Transmission, représentation, gouvernance ou transformation du territoire."),
]
STEP_BY_LEVEL = {level: {"level": level, "label": label, "description": desc} for level, label, desc in PARTICIPATION_STEPS}

OBSERVABLE_INDICATORS = [
    ("presence_reguliere", "Présence régulière"),
    ("prise_parole", "Prise de parole"),
    ("besoin_exprime", "Besoin ou envie exprimé"),
    ("idee_proposee", "Idée proposée"),
    ("aide_ponctuelle", "Aide ponctuelle"),
    ("organisation", "Contribution à l’organisation"),
    ("relais_habitants", "Relais auprès d’autres habitants"),
    ("co_animation", "Co-animation"),
    ("decision", "Participation à une décision"),
    ("responsabilite", "Responsabilité prise"),
    ("initiative", "Initiative habitante"),
    ("representation", "Représentation / transmission"),
]
INDICATOR_LABELS = dict(OBSERVABLE_INDICATORS)
SOURCES = {
    "pro": "Observation professionnelle",
    "habitant": "Auto-positionnement habitant",
    "partagee": "Position discutée / partagée",
    "equipe": "Validation en équipe",
}
JALONS = {
    "premiere_venue": "Première venue",
    "5_presences": "Réévaluation après 5 présences",
    "mi_parcours": "Mi-parcours",
    "fin_parcours": "Fin de parcours",
    "ajustement": "Ajustement ponctuel",
}


def normalize_level(value, default=1):
    try:
        level = int(value)
    except (TypeError, ValueError):
        return default
    return min(8, max(1, level))


def indicator_labels(codes):
    return [INDICATOR_LABELS.get(code, code) for code in (codes or [])]


def scoped_participation_query(participant_id=None, secteur=None, start=None, end=None):
    q = BoussoleParticipation.query
    if participant_id:
        q = q.filter(BoussoleParticipation.participant_id == participant_id)
    if secteur:
        q = q.filter(BoussoleParticipation.secteur == secteur)
    if start:
        q = q.filter(BoussoleParticipation.date_observation >= start)
    if end:
        q = q.filter(BoussoleParticipation.date_observation <= end)
    return q


def latest_positions(participant_id=None, secteur=None, start=None, end=None):
    rows = scoped_participation_query(participant_id, secteur, start, end).order_by(
        BoussoleParticipation.participant_id.asc(),
        BoussoleParticipation.secteur.asc(),
        BoussoleParticipation.date_observation.desc(),
        BoussoleParticipation.id.desc(),
    ).all()
    latest = {}
    for row in rows:
        key = (row.participant_id, row.secteur)
        latest.setdefault(key, row)
    return latest


def passport_summary(participant_id):
    latest = latest_positions(participant_id=participant_id)
    timeline = scoped_participation_query(participant_id=participant_id).order_by(
        BoussoleParticipation.date_observation.desc(), BoussoleParticipation.id.desc()
    ).all()
    return latest, timeline


def collective_stats(secteur=None, start=None, end=None):
    latest = latest_positions(secteur=secteur, start=start, end=end)
    counts = Counter(row.niveau for row in latest.values())
    by_sector = defaultdict(Counter)
    for row in latest.values():
        by_sector[row.secteur][row.niveau] += 1
    participants_by_level = defaultdict(list)
    if latest:
        participants = {p.id: p for p in Participant.query.filter(Participant.id.in_({pid for pid, _ in latest})).all()}
        for (pid, _sec), row in latest.items():
            participants_by_level[row.niveau].append({"participant": participants.get(pid), "position": row})
    return {"latest": latest, "counts": counts, "by_sector": by_sector, "participants_by_level": participants_by_level}


def presence_count(participant_id, secteur=None, until=None):
    q = db.session.query(func.count(PresenceActivite.id)).join(SessionActivite, PresenceActivite.session_id == SessionActivite.id).filter(
        PresenceActivite.participant_id == participant_id
    )
    if secteur:
        q = q.filter(SessionActivite.secteur == secteur)
    if until:
        q = q.filter(func.coalesce(SessionActivite.date_session, SessionActivite.rdv_date) <= until)
    return int(q.scalar() or 0)


def evaluation_due(participant_id, secteur):
    count = presence_count(participant_id, secteur=secteur)
    last = scoped_participation_query(participant_id=participant_id, secteur=secteur).order_by(
        BoussoleParticipation.date_observation.desc(), BoussoleParticipation.id.desc()
    ).first()
    if not last:
        return count >= 1, "Première observation à saisir" if count >= 1 else "Aucune présence"
    last_count = last.presence_count_snapshot or 0
    if count - last_count >= 5:
        return True, f"{count - last_count} présence(s) depuis la dernière observation"
    return False, f"{count - last_count}/5 présence(s) depuis la dernière observation"
