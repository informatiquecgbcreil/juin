"""Navigation — le mode Simple est complet, le mode Expert est rangé.

Garde-fous contre la régression qui a fait perdre l'utilisateur :
- en mode Simple, TOUS les modules livrés restent accessibles (pill Planning
  + panneau « Plus » organisé par rubriques) ;
- en mode Expert, plus de fourre-tout « Ressources » : les pages sont rangées
  dans « Salles & matériel », « Vie du centre » et « Finances → Argent au
  quotidien ».
"""


def _page(client, mode: str) -> str:
    if mode == "expert":
        client.post("/ui-mode", data={"mode": "expert"})
    else:
        client.post("/ui-mode", data={"mode": "simple"})
    r = client.get("/dashboard")
    assert r.status_code == 200
    return r.get_data(as_text=True)


def test_mode_simple_complet(admin_client):
    page = _page(admin_client, "simple")
    # Pill d'accès direct au planning.
    assert "🗓️ Planning" in page
    # Rubriques du panneau « Plus ».
    for rubrique in ("Mes outils", "Salles &amp; matériel", "Vie du centre",
                     "Publics &amp; accompagnement", "Argent au quotidien",
                     "Bilans &amp; enquêtes", "Administration"):
        assert rubrique in page, f"rubrique absente du mode simple : {rubrique}"
    # Les modules récents sont accessibles sans passer en mode expert.
    for lien in ("💶 Locations", "🏛️ Vie associative", "🌱 Transitions",
                 "Rédiger un bilan", "Prêts de matériel", "Inventaire matériel",
                 "Caisse", "Impayés"):
        assert lien in page, f"lien absent du mode simple : {lien}"


def test_mode_expert_range(admin_client):
    page = _page(admin_client, "expert")
    # Nouvelles rubriques à la place du fourre-tout « Ressources ».
    assert ">Ressources</summary>" not in page
    assert "Salles &amp; matériel" in page
    assert "Vie du centre" in page
    # Contenu de « Salles & matériel ».
    for lien in ("🗓️ Planning de la semaine", "Salles &amp; lieux",
                 "Prêts de matériel", "💶 Locations", "Inventaire matériel"):
        assert lien in page, f"lien absent de Salles & matériel : {lien}"
    # L'argent du quotidien vit dans Finances.
    assert "Argent au quotidien" in page
    for lien in ("Caisse", "Dons &amp; reçus fiscaux", "Coût unitaire"):
        assert lien in page, f"lien absent d'Argent au quotidien : {lien}"
    # « Vie du centre » porte la gouvernance et les partenaires.
    assert "🏛️ Vie associative (AG, CA)" in page
    assert "Annuaire partenaires" in page
    # Retour au mode simple pour ne pas polluer les autres tests (préférence partagée).
    admin_client.post("/ui-mode", data={"mode": "simple"})
