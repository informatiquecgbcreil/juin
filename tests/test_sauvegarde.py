"""Tests de la sauvegarde intégrée : service réutilisable + page d'administration."""


def test_page_sauvegardes_accessible_admin(admin_client):
    r = admin_client.get("/admin/sauvegardes")
    assert r.status_code == 200
    assert "Sauvegarder maintenant" in r.get_data(as_text=True)


def test_page_sauvegardes_refusee_aux_anonymes(client):
    r = client.get("/admin/sauvegardes")
    assert r.status_code in (302, 401, 403)


def test_service_cree_et_liste_une_sauvegarde(app):
    from app.services.sauvegarde import (
        creer_sauvegarde,
        dossier_sauvegardes,
        lister_sauvegardes,
    )

    with app.app_context():
        info = creer_sauvegarde()
        out_dir = dossier_sauvegardes()
        db_path = out_dir / info["db_fichier"]
        zip_path = out_dir / info["uploads_fichier"]
        try:
            assert db_path.exists(), "le fichier de base doit être créé"
            assert zip_path.exists(), "l'archive des pièces jointes doit être créée"
            noms = {s["nom"] for s in lister_sauvegardes()}
            assert info["db_fichier"] in noms
            assert info["uploads_fichier"] in noms
        finally:
            db_path.unlink(missing_ok=True)
            zip_path.unlink(missing_ok=True)


def test_bouton_cree_une_sauvegarde(admin_client, app):
    from app.services.sauvegarde import dossier_sauvegardes, lister_sauvegardes

    with app.app_context():
        avant = {s["nom"] for s in lister_sauvegardes()}

    r = admin_client.post("/admin/sauvegardes/creer", follow_redirects=True)
    assert r.status_code == 200
    assert "Sauvegarde créée" in r.get_data(as_text=True)

    with app.app_context():
        out_dir = dossier_sauvegardes()
        nouveaux = [s for s in lister_sauvegardes() if s["nom"] not in avant]
        try:
            assert nouveaux, "le bouton doit produire au moins un nouveau fichier"
        finally:
            for s in nouveaux:
                (out_dir / s["nom"]).unlink(missing_ok=True)
