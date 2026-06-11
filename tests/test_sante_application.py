"""Tests de santé : l'application démarre et expose ses routes."""


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}


def test_endpoints_principaux_enregistres(app):
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    attendus = {
        "auth.login",
        "setup.wizard",
        "main.dashboard",
        "main.subventions_list",
        "main.stats",
        "main.global_search_results",
        "main.suivi_rappels",
        "main.qualite_donnees_transverse",
        "main.bilan_global",
        "main.hub_publics",
        "main.controle",
    }
    manquants = attendus - endpoints
    assert not manquants, f"Endpoints manquants : {manquants}"


def test_pas_de_route_en_double(app):
    regles = [(r.rule, tuple(sorted(r.methods - {"HEAD", "OPTIONS"}))) for r in app.url_map.iter_rules()]
    doublons = {r for r in regles if regles.count(r) > 1}
    assert not doublons, f"Routes en double : {doublons}"
