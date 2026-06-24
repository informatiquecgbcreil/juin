"""Helpers pour construire les URL publiques affichées ou encodées en QR code."""

from __future__ import annotations

from flask import current_app, request


def public_base_url() -> str:
    """Retourne l'URL publique de l'application, sans slash final.

    ``ERP_PUBLIC_BASE_URL`` / ``PUBLIC_BASE_URL`` est prioritaire car les QR codes
    sont souvent scannés depuis un téléphone sur le réseau local : l'hôte de la
    requête admin peut être ``127.0.0.1`` ou ``localhost``, inaccessible depuis le
    mobile. À défaut, on retombe sur l'hôte de la requête courante.
    """
    cfg = (current_app.config.get("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if cfg:
        return cfg
    return request.host_url.rstrip("/")
