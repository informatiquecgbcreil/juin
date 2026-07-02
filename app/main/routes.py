"""Blueprint "main" éclaté en modules par domaine.

Chaque module ci-dessous enregistre ses routes sur le blueprint partagé
défini dans app.main.common. L'import suffit à déclencher l'enregistrement.
"""
from app.main.common import bp  # noqa: F401

from app.main import (  # noqa: F401
    benevoles,
    bilan_global,
    comparaison,
    controle,
    couts,
    dashboard,
    dons,
    guides,
    hart,
    hubs,
    qualite_donnees,
    recherche,
    rh,
    stats,
    subventions,
    suivi_rappels,
    tresorerie,
)
