"""Tests de non-régression : les pages principales répondent en admin.

Couvre notamment toutes les routes du blueprint ``main`` éclaté en
modules (dashboard, hubs, recherche, subventions, stats, bilan global,
suivi rappels, qualité données, contrôle).
"""
import pytest

PAGES = [
    # dashboard
    "/dashboard",
    "/dashboard/personnaliser",
    # hubs et documents
    "/publics",
    "/activites",
    "/bilans-hub",
    "/ressources",
    "/documents",
    # recherche
    "/recherche?q=test",
    "/api/global-search?q=test",
    # subventions
    "/subventions",
    # stats
    "/stats",
    "/stats-bilans",
    # bilan global
    "/bilan",
    # suivi et qualité
    "/suivi-rappels",
    "/qualite-donnees",
    "/qualite-donnees/export.csv",
    # contrôle et diagnostic
    "/controle",
    "/controle/navigation",
    "/setup-start",
    "/rbac-test",
]


@pytest.mark.parametrize("url", PAGES)
def test_page_repond_en_admin(admin_client, url):
    r = admin_client.get(url)
    assert r.status_code == 200, f"GET {url} -> {r.status_code}"


def test_alias_bilan_global_redirige(admin_client):
    r = admin_client.get("/bilan-global")
    assert r.status_code == 302
    assert "/bilan" in r.headers["Location"]


def test_export_bilan_xlsx(admin_client):
    r = admin_client.get("/bilan/export.xlsx")
    assert r.status_code == 200
    assert "spreadsheet" in r.content_type


def test_export_depenses_csv(admin_client):
    r = admin_client.get("/export/depenses.csv")
    assert r.status_code == 200
