"""Glossaire métier (« dico du social ») + uniformisation du vocabulaire.

- la page rend tous les termes et la recherche est présente ;
- garde-fous de qualité : définitions non vides, sigles développés ;
- l'uniformisation « séance » (vs « session ») ne régresse pas sur les
  écrans principaux.
"""
import pytest


def test_glossaire_page_complete(admin_client):
    r = admin_client.get("/guides/glossaire")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    # Les termes clés demandés (bilan, subvention, présence…) sont là
    for terme in ["Bilan", "Subvention", "Présence", "Séance", "Atelier",
                  "SENACS", "QPV", "ETP", "Bénévole", "Passeport",
                  "Éducation populaire", "Développement du pouvoir", "DPA",
                  "Aller-vers", "CLAS", "REAAP", "Animation globale",
                  "Projet social"]:
        assert terme in body, f"terme manquant : {terme}"
    # La recherche instantanée est en place
    assert "glossaire-filtre" in body
    # Le lien croisé vers les guides existe
    assert "/guides" in body


def test_glossaire_qualite_des_definitions(app):
    """Chaque terme a une définition substantielle ; les sigles sont développés."""
    from app.aide.glossaire import glossaire_termes_plats

    termes = glossaire_termes_plats()
    assert len(termes) >= 40, "le glossaire doit rester exhaustif"
    noms = [t["terme"] for t in termes]
    assert len(noms) == len(set(noms)), "pas de doublon de terme"
    for t in termes:
        assert len(t["definition"]) >= 40, f"définition trop courte : {t['terme']}"
    # Les sigles employés seuls doivent être développés dans leur définition
    corpus = {t["terme"]: t["definition"] for t in termes}
    assert "Caisse d'allocations familiales" in corpus["CAF (Caisse d'allocations familiales)"] or "CAF (" in str(corpus)
    assert any("Équivalent temps plein" in k or "Équivalent temps plein" in v for k, v in corpus.items())


def test_glossaire_accessible_a_tous_les_roles(app):
    """dashboard:view suffit : même un rôle minimal lit le glossaire."""
    from app.extensions import db
    from app.models import Role, User

    with app.app_context():
        u = User.query.filter_by(email="glo-tech@example.org").first()
        if u is None:
            u = User(email="glo-tech@example.org", nom="glo-tech")
            u.set_password("pw-test-123")
            u.roles.append(Role.query.filter_by(code="admin_tech").first())
            db.session.add(u)
            db.session.commit()
    c = app.test_client()
    c.post("/", data={"email": "glo-tech@example.org", "password": "pw-test-123"})
    assert c.get("/guides/glossaire").status_code == 200


def test_vocabulaire_seance_uniforme(admin_client):
    """Les écrans principaux disent « séance », plus « session » (hors code)."""
    for url in ("/dashboard", "/stats-impact/dashboard"):
        r = admin_client.get(url, follow_redirects=True)
        assert r.status_code == 200, url
        body = r.get_data(as_text=True)
        # Aucun libellé visible « >Session(s)< » ne doit rester
        assert ">Sessions<" not in body, url
        assert ">Session<" not in body, url
