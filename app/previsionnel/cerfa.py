"""Générateur de budget prévisionnel au format « compte de résultat prévisionnel »
associatif (type CERFA 12156 / modèle CAF-FADO).

Ce module définit la structure canonique du plan comptable (charges 60→69,
produits 70→79 + ressources propres, contributions volontaires 86/87), calcule
les totaux et l'équilibre, et produit :
- un classeur Excel fidèle au modèle (sous-totaux par compte via formules SUM,
  totaux généraux, vérification de l'équilibre) ;
- des lignes prêtes à alimenter une subvention (LigneBudget) ou un budget
  prévisionnel de projet (BudgetPrevisionnelLigne).

Aucune écriture en base ici : logique pure, testable isolément.
"""
from __future__ import annotations

from io import BytesIO


# --- Structure canonique (dérivée du modèle CAF-FADO fourni) -----------------

def _cat(idx: int, code: str, libelle: str) -> dict:
    # clé de champ HTML stable et unique par catégorie
    return {"key": f"cat__{code}__{idx}", "libelle": libelle}


CERFA_CHARGES = [
    {"code": "60", "libelle": "Achat", "categories": [
        _cat(0, "60", "Prestations de services"),
        _cat(1, "60", "Achats matières et fournitures"),
        _cat(2, "60", "Fournitures d'activité et petit équipement"),
        _cat(3, "60", "Autres fournitures (alimentation)"),
    ]},
    {"code": "61", "libelle": "Services extérieurs", "categories": [
        _cat(0, "61", "Locations"),
        _cat(1, "61", "Entretien et réparation"),
        _cat(2, "61", "Assurance"),
        _cat(3, "61", "Documentation"),
        _cat(4, "61", "Logiciels"),
    ]},
    {"code": "62", "libelle": "Autres services extérieurs", "categories": [
        _cat(0, "62", "Rémunérations intermédiaires, honoraires"),
        _cat(1, "62", "Publicité, publications"),
        _cat(2, "62", "Déplacements, missions"),
        _cat(3, "62", "Frais postaux et internet"),
        _cat(4, "62", "Impressions tracts extérieur"),
    ]},
    {"code": "63", "libelle": "Impôts et taxes", "categories": [
        _cat(0, "63", "Impôts et taxes sur rémunérations"),
        _cat(1, "63", "Autres impôts et taxes"),
    ]},
    {"code": "64", "libelle": "Charges de personnel", "categories": [
        _cat(0, "64", "Rémunération des personnels"),
        _cat(1, "64", "Charges sociales"),
        _cat(2, "64", "Autres charges de personnel"),
    ]},
    {"code": "65", "libelle": "Autres charges de gestion courante", "categories": [
        _cat(0, "65", "Autres charges de gestion courante"),
    ]},
    {"code": "66", "libelle": "Charges financières", "categories": [
        _cat(0, "66", "Charges financières"),
    ]},
    {"code": "67", "libelle": "Charges exceptionnelles", "categories": [
        _cat(0, "67", "Charges exceptionnelles"),
    ]},
    {"code": "68", "libelle": "Dotations aux amortissements, provisions et engagements", "categories": [
        _cat(0, "68", "Dotations et provisions et engagements"),
    ]},
    {"code": "69", "libelle": "Charges indirectes liées à l'activité", "categories": [
        _cat(0, "69", "Charges indirectes"),
    ]},
]

CERFA_PRODUITS = [
    {"code": "70", "libelle": "Vente de produits finis, de marchandises, prestation de services", "categories": [
        _cat(0, "70", "Ventes"),
    ]},
    {"code": "73", "libelle": "Dotations et produits de tarification", "categories": [
        _cat(0, "73", "Tarifications"),
    ]},
    {"code": "74", "libelle": "Subventions d'exploitation", "categories": [
        _cat(0, "74", "Politique de la Ville / P147"),
        _cat(1, "74", "Fonjep"),
        _cat(2, "74", "DRAC"),
        _cat(3, "74", "ARS"),
        _cat(4, "74", "Région"),
        _cat(5, "74", "Hauts-de-France"),
        _cat(6, "74", "Département"),
        _cat(7, "74", "OISE"),
        _cat(8, "74", "Intercommunalité : EPCI"),
        _cat(9, "74", "DRAJES (Jeunesse Éducation Populaire)"),
        _cat(10, "74", "Fonds propres"),
        _cat(11, "74", "Commune"),
        _cat(12, "74", "CREIL"),
        _cat(13, "74", "Organismes sociaux : CAF OISE"),
        _cat(14, "74", "REAAP"),
        _cat(15, "74", "Fonds européens"),
        _cat(16, "74", "Recherche de financement"),
        _cat(17, "74", "ASP / emplois aidés"),
        _cat(18, "74", "Creil ACSO"),
        _cat(19, "74", "Aides privées (Caisse d'épargne)"),
    ]},
    {"code": "75", "libelle": "Autres produits de gestion courante", "categories": [
        _cat(0, "75", "Dont cotisations, dons manuels ou legs"),
    ]},
    {"code": "76", "libelle": "Produits financiers", "categories": [
        _cat(0, "76", "Produits financiers"),
    ]},
    {"code": "77", "libelle": "Produits exceptionnels", "categories": [
        _cat(0, "77", "Produits exceptionnels"),
    ]},
    {"code": "78", "libelle": "Report ressources non utilisées d'opérations antérieures", "categories": [
        _cat(0, "78", "Reports des années antérieures"),
    ]},
    {"code": "79", "libelle": "Transfert de charges", "categories": [
        _cat(0, "79", "Transfert de charges"),
    ]},
    {"code": "RP", "libelle": "Ressources propres", "categories": [
        _cat(0, "RP", "Ressources propres"),
    ]},
]

CERFA_CONTRIB_EMPLOIS = [
    {"code": "86", "libelle": "Emplois des contributions volontaires en nature", "categories": [
        _cat(0, "86", "860 - Secours en nature"),
        _cat(1, "86", "861 - Mise à disposition gratuite de biens et services"),
        _cat(2, "86", "862 - Prestations"),
        _cat(3, "86", "864 - Personnel bénévole"),
    ]},
]

CERFA_CONTRIB_RESSOURCES = [
    {"code": "87", "libelle": "Contributions volontaires en nature", "categories": [
        _cat(0, "87", "870 - Bénévolat"),
        _cat(1, "87", "871 - Prestations en nature"),
        _cat(2, "87", "875 - Dons en nature"),
    ]},
]


def all_category_keys() -> list[str]:
    keys = []
    for block in (CERFA_CHARGES, CERFA_PRODUITS, CERFA_CONTRIB_EMPLOIS, CERFA_CONTRIB_RESSOURCES):
        for compte in block:
            for cat in compte["categories"]:
                keys.append(cat["key"])
    return keys


# --- Parsing / calculs -------------------------------------------------------

def parse_amount(value) -> float:
    """Tolère les espaces, la virgule décimale et une somme simple « a+b+c »."""
    raw = str(value or "").replace(" ", "").replace(" ", "").replace(",", ".")
    if not raw:
        return 0.0
    try:
        return round(float(raw), 2)
    except Exception:
        pass
    # somme simple de nombres (ex. « 220+144+270 »), sans eval arbitraire
    if all(c in "0123456789.+" for c in raw):
        total = 0.0
        ok = False
        for part in raw.split("+"):
            if not part:
                continue
            try:
                total += float(part)
                ok = True
            except Exception:
                return 0.0
        if ok:
            return round(total, 2)
    return 0.0


def values_from_form(form) -> dict[str, float]:
    """Extrait {clé_catégorie: montant} depuis un formulaire (request.form)."""
    values = {}
    for key in all_category_keys():
        values[key] = parse_amount(form.get(key))
    return values


def _compte_total(compte: dict, values: dict[str, float]) -> float:
    return round(sum(values.get(c["key"], 0.0) for c in compte["categories"]), 2)


def compute_totals(values: dict[str, float]) -> dict:
    """Calcule les sous-totaux par compte et les totaux généraux."""
    totaux_charges = {c["code"]: _compte_total(c, values) for c in CERFA_CHARGES}
    totaux_produits = {c["code"]: _compte_total(c, values) for c in CERFA_PRODUITS}
    total_charges = round(sum(totaux_charges.values()), 2)
    total_produits = round(sum(totaux_produits.values()), 2)

    total_emplois = round(sum(_compte_total(c, values) for c in CERFA_CONTRIB_EMPLOIS), 2)
    total_ressources = round(sum(_compte_total(c, values) for c in CERFA_CONTRIB_RESSOURCES), 2)

    total_general_charges = round(total_charges + total_emplois, 2)
    total_general_produits = round(total_produits + total_ressources, 2)

    return {
        "par_compte_charges": totaux_charges,
        "par_compte_produits": totaux_produits,
        "total_charges": total_charges,
        "total_produits": total_produits,
        "total_emplois": total_emplois,
        "total_ressources": total_ressources,
        "total_general_charges": total_general_charges,
        "total_general_produits": total_general_produits,
        "equilibre": round(total_general_produits - total_general_charges, 2),
    }


def lignes_budget(values: dict[str, float], *, inclure_zero: bool = False) -> list[dict]:
    """Aplati la saisie en lignes {nature, compte, libelle, montant} pour
    alimenter une subvention ou un budget prévisionnel. Les contributions
    volontaires (86/87) sont exclues : elles ne constituent pas des flux
    budgétaires réels."""
    out = []
    for compte in CERFA_CHARGES:
        compte_label = f"{compte['code']} - {compte['libelle']}"
        for cat in compte["categories"]:
            montant = values.get(cat["key"], 0.0)
            if montant or inclure_zero:
                out.append({"nature": "charge", "compte": compte_label,
                            "libelle": cat["libelle"], "montant": round(montant, 2)})
    for compte in CERFA_PRODUITS:
        compte_label = f"{compte['code']} - {compte['libelle']}"
        for cat in compte["categories"]:
            montant = values.get(cat["key"], 0.0)
            if montant or inclure_zero:
                out.append({"nature": "produit", "compte": compte_label,
                            "libelle": cat["libelle"], "montant": round(montant, 2)})
    return out


# --- Export Excel ------------------------------------------------------------

def _safe_text(value) -> str:
    """Neutralise l'injection de formule Excel dans un texte libre."""
    s = "" if value is None else str(value)
    if s and s[0] in ("=", "+", "-", "@"):
        return "'" + s
    return s


def build_cerfa_workbook(values: dict[str, float], *, organisme: str, exercice, secteur: str | None = None):
    """Construit un classeur openpyxl fidèle au modèle de compte de résultat
    prévisionnel : deux colonnes parallèles (charges / produits), sous-totaux
    par compte en formules, totaux généraux et vérification de l'équilibre."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = Workbook()
    ws = wb.active
    ws.title = (secteur or "Budget")[:31]

    bold = Font(bold=True)
    head_fill = PatternFill(fill_type="solid", fgColor="C6E0B4")
    prod_fill = PatternFill(fill_type="solid", fgColor="BDD7EE")
    total_fill = PatternFill(fill_type="solid", fgColor="FFE699")
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    ws["A1"] = "Nom de l'organisme"
    ws["A1"].font = bold
    ws["B1"] = _safe_text(organisme)
    ws.merge_cells("B1:D1")
    ws["A3"] = "EXERCICE"
    ws["A3"].font = bold
    ws["B3"] = exercice
    if secteur:
        ws["C3"] = "Secteur"
        ws["C3"].font = bold
        ws["D3"] = _safe_text(secteur)

    ws["A5"] = "CHARGES"
    ws["C5"] = "PRODUITS"
    for coord, fill in (("A5", head_fill), ("B5", head_fill), ("C5", prod_fill), ("D5", prod_fill)):
        ws[coord].font = bold
        ws[coord].fill = fill

    start = 6

    def write_block(block, col_lib, col_val, fill, cursor_start):
        """Écrit un bloc (charges ou produits) et renvoie (dernière_ligne, [cellules_sous_totaux])."""
        row = cursor_start
        subtotal_cells = []
        for compte in block:
            # ligne de compte : libellé + formule SUM sur ses catégories
            first_cat_row = row + 1
            last_cat_row = row + len(compte["categories"])
            lib_cell = ws.cell(row=row, column=col_lib, value=f"{compte['code']} - {compte['libelle']}")
            lib_cell.font = bold
            lib_cell.fill = fill
            val_cell = ws.cell(row=row, column=col_val)
            col_letter = val_cell.column_letter
            val_cell.value = f"=SUM({col_letter}{first_cat_row}:{col_letter}{last_cat_row})"
            val_cell.font = bold
            val_cell.fill = fill
            subtotal_cells.append(f"{col_letter}{row}")
            row += 1
            for cat in compte["categories"]:
                ws.cell(row=row, column=col_lib, value=_safe_text(cat["libelle"]))
                mc = ws.cell(row=row, column=col_val, value=round(values.get(cat["key"], 0.0), 2))
                mc.number_format = "#,##0.00"
                row += 1
        return row, subtotal_cells

    end_charges, charge_subtotals = write_block(CERFA_CHARGES, 1, 2, head_fill, start)
    end_produits, produit_subtotals = write_block(CERFA_PRODUITS, 3, 4, prod_fill, start)

    total_row = max(end_charges, end_produits) + 1
    ws.cell(row=total_row, column=1, value="TOTAL DES CHARGES").font = bold
    tc = ws.cell(row=total_row, column=2, value="=" + "+".join(charge_subtotals))
    ws.cell(row=total_row, column=3, value="TOTAL DES PRODUITS").font = bold
    tp = ws.cell(row=total_row, column=4, value="=" + "+".join(produit_subtotals))
    for cell in (tc, tp):
        cell.font = bold
        cell.number_format = "#,##0.00"
    for col in (1, 2, 3, 4):
        ws.cell(row=total_row, column=col).fill = total_fill

    # Contributions volontaires
    contrib_title = total_row + 2
    ws.cell(row=contrib_title, column=1, value="CONTRIBUTIONS VOLONTAIRES EN NATURE").font = bold
    end_emplois, emploi_subtotals = write_block(CERFA_CONTRIB_EMPLOIS, 1, 2, head_fill, contrib_title + 1)
    end_ressources, ressource_subtotals = write_block(CERFA_CONTRIB_RESSOURCES, 3, 4, prod_fill, contrib_title + 1)

    tg_row = max(end_emplois, end_ressources) + 1
    ws.cell(row=tg_row, column=1, value="TOTAL GÉNÉRAL DES CHARGES").font = bold
    tgc = ws.cell(row=tg_row, column=2, value=f"=B{total_row}+" + "+".join(emploi_subtotals))
    ws.cell(row=tg_row, column=3, value="TOTAL GÉNÉRAL DES PRODUITS").font = bold
    tgp = ws.cell(row=tg_row, column=4, value=f"=D{total_row}+" + "+".join(ressource_subtotals))
    for cell in (tgc, tgp):
        cell.font = bold
        cell.number_format = "#,##0.00"
    for col in (1, 2, 3, 4):
        ws.cell(row=tg_row, column=col).fill = total_fill

    eq_row = tg_row + 2
    ws.cell(row=eq_row, column=3, value="Vérification de l'équilibre (produits - charges)").font = bold
    eq = ws.cell(row=eq_row, column=4, value=f"=D{tg_row}-B{tg_row}")
    eq.font = bold
    eq.number_format = "#,##0.00"

    # bordures + largeurs
    for row in ws.iter_rows(min_row=5, max_row=eq_row, min_col=1, max_col=4):
        for cell in row:
            if cell.value is not None:
                cell.border = border
    for col_letter, width in (("A", 42), ("B", 15), ("C", 46), ("D", 15)):
        ws.column_dimensions[col_letter].width = width
    ws.freeze_panes = "A6"

    return wb


def workbook_to_bytes(wb) -> bytes:
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()
