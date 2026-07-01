"""Générateur de budget prévisionnel (modèle CERFA / CAF-FADO) :
calculs, export Excel, envoi vers subvention / budget prévisionnel."""
import uuid
from io import BytesIO

from flask import url_for


def _sample_values():
    """Jeu de saisie de référence (mêmes ordres de grandeur que le modèle fourni)."""
    return {
        "cat__60__0": 500.0,     # Prestations de services
        "cat__60__2": 1200.0,    # Fournitures d'activité
        "cat__74__12": 3000.0,   # CREIL
        "cat__74__13": 10000.0,  # CAF OISE
        "cat__86__2": 1500.0,    # 862 Prestations (emploi contrib.)
        "cat__87__0": 1500.0,    # 870 Bénévolat (ressource contrib.)
    }


def test_parse_amount():
    from app.previsionnel.cerfa import parse_amount
    assert parse_amount("500") == 500.0
    assert parse_amount("1 200,50") == 1200.5
    assert parse_amount("1 000,50") == 1000.5      # format FR (espace milliers, virgule décimale)
    assert parse_amount("220+144+270") == 634.0
    assert parse_amount("") == 0.0
    assert parse_amount("=DANGER()") == 0.0
    assert parse_amount("100abc") == 0.0           # texte parasite -> 0 (aligné avec le JS)
    assert parse_amount("1,000.50") == 0.0         # format anglo ambigu -> 0
    assert parse_amount("5+3+x") == 0.0
    assert parse_amount(None) == 0.0


def test_compute_totals():
    from app.previsionnel.cerfa import compute_totals
    t = compute_totals(_sample_values())
    assert t["par_compte_charges"]["60"] == 1700.0
    assert t["par_compte_produits"]["74"] == 13000.0
    assert t["total_charges"] == 1700.0
    assert t["total_produits"] == 13000.0
    assert t["total_emplois"] == 1500.0
    assert t["total_ressources"] == 1500.0
    assert t["total_general_charges"] == 3200.0
    assert t["total_general_produits"] == 14500.0
    assert t["equilibre"] == 11300.0


def test_lignes_budget_exclut_zero_et_contributions():
    from app.previsionnel.cerfa import lignes_budget
    lignes = lignes_budget(_sample_values())
    # 2 charges + 2 produits, aucune contribution volontaire (86/87)
    assert len(lignes) == 4
    natures = sorted(l["nature"] for l in lignes)
    assert natures == ["charge", "charge", "produit", "produit"]
    creil = next(l for l in lignes if l["libelle"] == "CREIL")
    assert creil["nature"] == "produit"
    assert creil["compte"].startswith("74 - ")
    assert creil["montant"] == 3000.0
    assert all("86" not in l["compte"] and "87" not in l["compte"] for l in lignes)


def test_safe_text_neutralise_formule():
    from app.previsionnel.cerfa import _safe_text
    assert _safe_text("=1+1").startswith("'")
    assert _safe_text("Normal") == "Normal"


def test_page_generateur_rendue(app, admin_client):
    with app.app_context():
        with app.test_request_context():
            url = url_for("previsionnel.generateur")
    r = admin_client.get(url)
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Générateur de budget prévisionnel" in body
    assert "60 - Achat" in body
    assert "74 - Subventions d" in body   # apostrophe échappée par Jinja
    assert "CONTRIBUTIONS VOLONTAIRES" in body.upper()


def test_export_xlsx(app, admin_client):
    from openpyxl import load_workbook
    with app.app_context():
        with app.test_request_context():
            url = url_for("previsionnel.generateur")
    data = dict(_sample_values())
    data.update({"action": "export_xlsx", "organisme": "Centre Test",
                 "exercice": "2026", "secteur": "Numérique"})
    r = admin_client.post(url, data=data)
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers.get("Content-Type", "")

    wb = load_workbook(BytesIO(r.data))
    ws = wb.active
    all_vals = [c.value for row in ws.iter_rows() for c in row if c.value is not None]
    assert 500.0 in all_vals          # montant saisi
    assert 3000.0 in all_vals
    assert any(isinstance(v, str) and v.startswith("=SUM(") for v in all_vals)  # sous-totaux
    assert any(isinstance(v, str) and "TOTAL DES CHARGES" in v for v in all_vals)
    assert any(isinstance(v, str) and "équilibre" in v.lower() for v in all_vals)


def test_export_xlsx_neutralise_injection(app, admin_client):
    """Un nom d'organisme commençant par '=' ne doit pas devenir une formule."""
    from openpyxl import load_workbook
    with app.app_context():
        with app.test_request_context():
            url = url_for("previsionnel.generateur")
    r = admin_client.post(url, data={"action": "export_xlsx", "organisme": "=cmd()",
                                     "exercice": "2026", "secteur": "Numérique", **_sample_values()})
    wb = load_workbook(BytesIO(r.data))
    ws = wb.active
    assert ws["B1"].value == "'=cmd()"   # neutralisé (apostrophe), pas une formule


def test_envoi_vers_subvention(app, admin_client):
    from app.extensions import db
    from app.models import Subvention, LigneBudget

    nom = f"BudgetGen{uuid.uuid4().hex[:6]}"
    with app.app_context():
        with app.test_request_context():
            url = url_for("previsionnel.generateur")
    data = dict(_sample_values())
    data.update({"action": "to_subvention", "organisme": "C", "exercice": "2035",
                 "secteur": "Numérique", "subvention_nom": nom})
    admin_client.post(url, data=data, follow_redirects=True)

    with app.app_context():
        sub = Subvention.query.filter_by(nom=nom).first()
        assert sub is not None
        assert sub.annee_exercice == 2035
        lignes = LigneBudget.query.filter_by(subvention_id=sub.id).all()
        assert len(lignes) == 4     # contributions exclues
        charges = sum(l.montant_base for l in lignes if l.nature == "charge")
        produits = sum(l.montant_base for l in lignes if l.nature == "produit")
        assert charges == 1700.0
        assert produits == 13000.0
        # compte normalisé pour tenir dans VARCHAR(20) (sinon plantage PostgreSQL)
        assert all(len(l.compte) <= 20 for l in lignes)
        assert any(l.compte == "74" for l in lignes)   # code comptable, pas le libellé long


def test_envoi_vers_previsionnel_avec_projet(app, admin_client):
    from app.extensions import db
    from app.models import Projet, BudgetPrevisionnel, BudgetPrevisionnelLigne

    with app.app_context():
        p = Projet(nom=f"ProjGen{uuid.uuid4().hex[:6]}", secteur="Numérique")
        db.session.add(p)
        db.session.commit()
        pid = p.id
        with app.test_request_context():
            url = url_for("previsionnel.generateur")
    data = dict(_sample_values())
    data.update({"action": "to_previsionnel", "organisme": "C", "exercice": "2036",
                 "secteur": "Numérique", "projet_id": str(pid), "subvention_nom": "Budget projet gen"})
    admin_client.post(url, data=data, follow_redirects=True)

    with app.app_context():
        budget = BudgetPrevisionnel.query.filter_by(annee=2036, secteur="Numérique").order_by(
            BudgetPrevisionnel.id.desc()).first()
        assert budget is not None
        assert budget.statut == "brouillon"
        lignes = BudgetPrevisionnelLigne.query.filter_by(budget_id=budget.id).all()
        assert len(lignes) == 4
        assert all(l.projet_id == pid for l in lignes)
        assert all(len(l.compte) <= 20 for l in lignes)   # tient dans VARCHAR(20)


def test_export_xlsx_secteur_caractere_interdit(app, admin_client):
    """Un secteur contenant un caractère interdit d'onglet Excel (/ : etc.)
    ne doit pas faire planter l'export."""
    from openpyxl import load_workbook
    with app.app_context():
        with app.test_request_context():
            url = url_for("previsionnel.generateur")
    r = admin_client.post(url, data={"action": "export_xlsx", "organisme": "C",
                                     "exercice": "2026", "secteur": "A/B:C*?", **_sample_values()})
    assert r.status_code == 200
    wb = load_workbook(BytesIO(r.data))
    assert not any(ch in wb.active.title for ch in r"[]:*?/\\")


def test_envoi_previsionnel_refuse_projet_autre_secteur(app, admin_client):
    from app.extensions import db
    from app.models import Projet

    with app.app_context():
        p = Projet(nom=f"ProjX{uuid.uuid4().hex[:6]}", secteur="Familles")
        db.session.add(p)
        db.session.commit()
        pid = p.id
        with app.test_request_context():
            url = url_for("previsionnel.generateur")
    data = dict(_sample_values())
    data.update({"action": "to_previsionnel", "exercice": "2037",
                 "secteur": "Numérique", "projet_id": str(pid)})
    r = admin_client.post(url, data=data)
    assert r.status_code == 400   # projet Familles vs budget Numérique
