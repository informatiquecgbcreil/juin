"""Flux calendrier iCal (RFC 5545) des séances, pour abonnement Google
Agenda / Apple Calendrier / Outlook.

Sens unique (l'ERP nourrit l'agenda). Le flux ne contient que le strict
nécessaire — nom d'atelier, secteur, horaire — jamais de nom de
participant. Chaque séance a un UID stable : une modification met à jour
l'événement existant au lieu d'en créer un doublon ; une séance annulée
est marquée STATUS:CANCELLED (elle disparaît de l'agenda).
"""
from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta

from app.extensions import db
from app.models import AtelierActivite, SessionActivite

# Fenêtre du flux : assez de passé pour le contexte, large sur l'avenir.
JOURS_PASSE = 30
JOURS_FUTUR = 180


def token_ou_creer(user) -> str:
    """Jeton du flux de la personne (créé et persisté au premier appel)."""
    if not getattr(user, "calendar_token", None):
        user.calendar_token = secrets.token_urlsafe(24)
        db.session.commit()
    return user.calendar_token


def regenerer_token(user) -> str:
    """Change le jeton : l'ancien lien cesse immédiatement de fonctionner."""
    user.calendar_token = secrets.token_urlsafe(24)
    db.session.commit()
    return user.calendar_token


def _secteur_du_flux(user) -> str | None:
    """Secteur filtré pour ce flux (None = tous, pour la portée globale)."""
    has_perm = getattr(user, "has_perm", None)
    if callable(has_perm) and has_perm("scope:all_secteurs"):
        return None
    return (getattr(user, "secteur_assigne", None) or "").strip() or None


def sessions_du_flux(user) -> list[SessionActivite]:
    today = date.today()
    debut, fin = today - timedelta(days=JOURS_PASSE), today + timedelta(days=JOURS_FUTUR)
    eff = db.func.coalesce(SessionActivite.rdv_date, SessionActivite.date_session)
    q = (
        SessionActivite.query
        .join(AtelierActivite, AtelierActivite.id == SessionActivite.atelier_id)
        .filter(
            SessionActivite.is_deleted.is_(False),
            AtelierActivite.is_deleted.is_(False),
            eff >= debut,
            eff <= fin,
        )
    )
    secteur = _secteur_du_flux(user)
    if secteur:
        q = q.filter(SessionActivite.secteur == secteur)
    return q.order_by(eff.asc()).all()


# --------------------------------------------------------------------------
# Formatage iCalendar
# --------------------------------------------------------------------------

def _echapper(texte: str) -> str:
    return (
        (texte or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _plier(ligne: str) -> str:
    """Pliage RFC 5545 : lignes de contenu ≤ 75 octets, suite préfixée d'un
    espace. On plie sur les octets (UTF-8) pour ne jamais dépasser."""
    octets = ligne.encode("utf-8")
    if len(octets) <= 75:
        return ligne
    morceaux, courant = [], b""
    for ch in ligne:
        b = ch.encode("utf-8")
        # 75 pour la 1re ligne, 74 pour les suivantes (l'espace initial compte).
        limite = 75 if not morceaux else 74
        if len(courant) + len(b) > limite:
            morceaux.append(courant.decode("utf-8"))
            courant = b
        else:
            courant += b
    if courant:
        morceaux.append(courant.decode("utf-8"))
    return "\r\n ".join(morceaux)


def _dt_local(d: date, heure: str | None) -> tuple[str, bool]:
    """Renvoie (valeur ICS, is_all_day). Heure 'HH:MM' -> horodaté local ;
    absente -> journée entière."""
    if heure:
        try:
            hh, mm = heure.strip().split(":")[:2]
            return f"{d.strftime('%Y%m%d')}T{int(hh):02d}{int(mm):02d}00", False
        except Exception:
            pass
    return d.strftime("%Y%m%d"), True


def _plus_une_heure(heure: str | None) -> str | None:
    if not heure:
        return None
    try:
        hh, mm = heure.strip().split(":")[:2]
        base = datetime(2000, 1, 1, int(hh), int(mm)) + timedelta(hours=1)
        return base.strftime("%H:%M")
    except Exception:
        return None


def generer_ics(user, *, base_url: str, nom_calendrier: str = "Mes séances") -> str:
    host = (base_url or "").split("//", 1)[-1].split("/", 1)[0] or "erp.local"
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    lignes = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Gestion du Centre//Sceances//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_echapper(nom_calendrier)}",
        "X-WR-TIMEZONE:Europe/Paris",
    ]

    for s in sessions_du_flux(user):
        d = s.rdv_date or s.date_session
        if d is None:
            continue
        heure_debut = s.rdv_debut or s.heure_debut
        heure_fin = s.rdv_fin or s.heure_fin or _plus_une_heure(heure_debut)
        atelier = s.atelier
        titre = atelier.nom if atelier else f"Atelier #{s.atelier_id}"

        deb_val, all_day = _dt_local(d, heure_debut)
        lignes.append("BEGIN:VEVENT")
        lignes.append(f"UID:seance-{s.id}@{host}")
        lignes.append(f"DTSTAMP:{stamp}")
        if all_day:
            lignes.append(f"DTSTART;VALUE=DATE:{deb_val}")
            lignes.append(f"DTEND;VALUE=DATE:{(d + timedelta(days=1)).strftime('%Y%m%d')}")
        else:
            fin_val, _ = _dt_local(d, heure_fin)
            lignes.append(f"DTSTART;TZID=Europe/Paris:{deb_val}")
            lignes.append(f"DTEND;TZID=Europe/Paris:{fin_val}")
        lignes.append(_plier(f"SUMMARY:{_echapper(titre)}"))
        lignes.append(_plier(f"LOCATION:{_echapper((s.secteur or '').strip())}"))
        lignes.append(_plier(f"DESCRIPTION:{_echapper('Séance — secteur ' + (s.secteur or '—'))}"))
        if (s.statut or "").strip().lower() == "annulee":
            lignes.append("STATUS:CANCELLED")
        else:
            lignes.append("STATUS:CONFIRMED")
        lignes.append("END:VEVENT")

    lignes.append("END:VCALENDAR")
    return "\r\n".join(lignes) + "\r\n"
