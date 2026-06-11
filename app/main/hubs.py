from datetime import date


from flask import (
    render_template, request, url_for, abort, current_app
)
from flask_login import login_required, current_user
from app.rbac import can

from app.extensions import db
from app.models import (
    Subvention,
    Projet,
    ProjetAction,
    OrientationAccesDroit,
    Questionnaire,
)


from app.main.common import bp



# ---------------------------------------------------------------------
# P0.3C — Hubs métier
# ---------------------------------------------------------------------

def _hub_forbidden_if_empty(cards):
    if not cards:
        abort(403)


@bp.route("/publics")
@login_required
def hub_publics():
    cards = []

    if can("participants:view") or can("participants:view_all"):
        cards.append({
            "title": "Participants",
            "subtitle": "Retrouver, créer ou mettre à jour une fiche habitant.",
            "primary_label": "Ouvrir les participants",
            "primary_url": url_for("participants.list_participants"),
            "secondary": [
                {"label": "Attestations", "url": url_for("activite.attestations")} if can("participants:view") or can("participants:view_all") else None,
                {"label": "Ajouter une personne", "url": url_for("participants.new_participant")} if can("participants:edit") else None,
                {"label": "Doublons potentiels", "url": url_for("participants.duplicates")} if can("participants:edit") else None,
            ],
            "tag": "Publics",
        })

    if can("insertion:view"):
        cards.append({
            "title": "Insertion",
            "subtitle": "Suivre les parcours, positionnements et données insertion.",
            "primary_label": "Ouvrir insertion",
            "primary_url": url_for("insertion.index"),
            "secondary": [],
            "tag": "Parcours",
        })

    if can("quartiers:view"):
        cards.append({
            "title": "Quartiers",
            "subtitle": "Consulter les quartiers, QPV et informations territoriales.",
            "primary_label": "Ouvrir quartiers",
            "primary_url": url_for("quartiers.index"),
            "secondary": [],
            "tag": "Territoire",
        })

    _hub_forbidden_if_empty(cards)
    return render_template(
        "hub_publics.html",
        title="Publics & parcours",
        intro="Une porte d’entrée pour tout ce qui concerne les habitants, leurs parcours et leur territoire.",
        cards=cards,
    )


@bp.route("/activites")
@login_required
def hub_activites():
    cards = []

    if can("emargement:view"):
        cards.append({
            "title": "Présences / émargement",
            "subtitle": "Faire l’émargement, ouvrir les ateliers et gérer les sessions.",
            "primary_label": "Ouvrir les présences",
            "primary_url": url_for("activite.index"),
            "secondary": [
                {"label": "Attestations", "url": url_for("activite.attestations")} if can("participants:view") or can("participants:view_all") else None,
                {"label": "Modèles d’émargement", "url": url_for("activite.emargement_models")} if can("emargement:edit") else None,
            ],
            "tag": "Quotidien",
        })

    if can("statsimpact:view") or can("stats:view"):
        cards.append({
            "title": "Données ateliers",
            "subtitle": "Suivre les statistiques d’activité, présences et ateliers.",
            "primary_label": "Voir les données",
            "primary_url": url_for("statsimpact.dashboard"),
            "secondary": [],
            "tag": "Analyse",
        })

    if can("pedagogie:view"):
        cards.append({
            "title": "Pédagogie",
            "subtitle": "Référentiels, compétences, modules et suivi pédagogique.",
            "primary_label": "Ouvrir pédagogie",
            "primary_url": url_for("pedagogie.referentiels_list"),
            "secondary": [
                {"label": "Suivi pédagogique", "url": url_for("pedagogie.suivi_pedagogique")},
            ],
            "tag": "Compétences",
        })

    _hub_forbidden_if_empty(cards)
    return render_template(
        "hub_activites.html",
        title="Activités & présences",
        intro="Un hub pour passer des séances aux présences, puis aux données d’activité et au suivi pédagogique.",
        cards=cards,
    )


@bp.route("/bilans-hub")
@login_required
def hub_bilans():
    cards = []

    if can("dashboard:view"):
        cards.append({
            "title": "Documents prêts",
            "subtitle": "Retrouver les exports, fiches imprimables et rapports à transmettre.",
            "primary_label": "Ouvrir les documents",
            "primary_url": url_for("main.documents_exports"),
            "secondary": [
                {"label": "Qualité transverse", "url": url_for("main.qualite_donnees_transverse")},
            ],
            "tag": "Sorties",
        })

    if can("stats:view"):
        cards.append({
            "title": "Stats & bilans",
            "subtitle": "Consulter les chiffres clés et les indicateurs de pilotage.",
            "primary_label": "Ouvrir stats & bilans",
            "primary_url": url_for("main.stats_bilans"),
            "secondary": [
                {"label": "Bilan global", "url": url_for("main.bilan_global")},
                {"label": "Export bilan XLSX", "url": url_for("main.bilan_global_export_xlsx")},
                {"label": "Qualité transverse", "url": url_for("main.qualite_donnees_transverse")},
            ],
            "tag": "Pilotage",
        })

    if can("bilans:view"):
        cards.append({
            "title": "Bilans lourds",
            "subtitle": "Préparer les bilans annuels, narratifs et exports complets.",
            "primary_label": "Ouvrir bilans lourds",
            "primary_url": url_for("bilans.bilans_lourds", year=date.today().year),
            "secondary": [
                {"label": "Bilan secteur", "url": url_for("bilans.bilan_secteur")},
                {"label": "Bilan subvention", "url": url_for("bilans.bilan_subvention")},
                {"label": "Qualité des données", "url": url_for("bilans.qualite")},
            ],
            "tag": "Annuel",
        })

    if can("dashboard:view"):
        cards.append({
            "title": "Qualité des données",
            "subtitle": "Repérer les fiches, suivis et saisies à corriger dans les modules.",
            "primary_label": "Ouvrir qualité",
            "primary_url": url_for("main.qualite_donnees_transverse"),
            "secondary": [
                {"label": "Centre de suivi", "url": url_for("main.suivi_rappels")},
            ],
            "tag": "Contrôle",
        })

    if can("questionnaires:view"):
        cards.append({
            "title": "Questionnaires d’impact",
            "subtitle": "Consulter les questionnaires et retours qualitatifs.",
            "primary_label": "Ouvrir questionnaires",
            "primary_url": url_for("questionnaires.index"),
            "secondary": [],
            "tag": "Impact",
        })

    _hub_forbidden_if_empty(cards)
    return render_template(
        "hub_bilans.html",
        title="Bilans & exports",
        intro="La zone pour préparer les bilans, vérifier les données et sortir les exports utiles.",
        cards=cards,
    )


def _documents_compact_args(**kwargs) -> dict:
    return {key: value for key, value in kwargs.items() if value not in (None, "")}


def _documents_selected_year() -> int:
    try:
        year = int((request.args.get("year") or "").strip())
    except Exception:
        year = date.today().year
    return max(2000, min(2100, year))


def _documents_scope() -> tuple[int, str | None, list[str]]:
    year = _documents_selected_year()
    secteurs = current_app.config.get("SECTEURS", []) or []
    extra_secteurs = {
        row[0]
        for row in Subvention.query.with_entities(Subvention.secteur)
        .filter(Subvention.secteur.isnot(None))
        .distinct()
        .all()
    }
    extra_secteurs.update({
        row[0]
        for row in Projet.query.with_entities(Projet.secteur)
        .filter(Projet.secteur.isnot(None))
        .distinct()
        .all()
    })
    secteurs = secteurs + [s for s in sorted(extra_secteurs) if s and s not in secteurs]

    selected_secteur = (request.args.get("secteur") or "").strip() or None
    if not can("scope:all_secteurs"):
        selected_secteur = getattr(current_user, "secteur_assigne", None)
        secteurs = [selected_secteur] if selected_secteur else []

    return year, selected_secteur, secteurs


def _documents_subventions(year: int, secteur: str | None) -> list[Subvention]:
    if not (can("subventions:view") or can("bilans:view")):
        return []
    q = Subvention.query.filter(Subvention.est_archive.is_(False), Subvention.annee_exercice == year)
    if secteur:
        q = q.filter(Subvention.secteur == secteur)
    elif not can("scope:all_secteurs"):
        q = q.filter(Subvention.secteur == getattr(current_user, "secteur_assigne", None))
    return q.order_by(Subvention.montant_recu.desc(), Subvention.nom.asc()).limit(8).all()


def _documents_projects(secteur: str | None) -> list[Projet]:
    if not can("projets:view"):
        return []
    q = Projet.query
    if secteur:
        q = q.filter(Projet.secteur == secteur)
    elif not can("scope:all_secteurs"):
        q = q.filter(Projet.secteur == getattr(current_user, "secteur_assigne", None))
    return q.order_by(Projet.nom.asc()).limit(8).all()


def _documents_actions(year: int, secteur: str | None) -> list[ProjetAction]:
    if not can("projets:view"):
        return []
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    q = ProjetAction.query.join(Projet)
    if secteur:
        q = q.filter(Projet.secteur == secteur)
    elif not can("scope:all_secteurs"):
        q = q.filter(Projet.secteur == getattr(current_user, "secteur_assigne", None))
    q = q.filter(db.or_(
        ProjetAction.date_debut.between(start, end),
        ProjetAction.date_fin.between(start, end),
        db.and_(ProjetAction.date_debut.is_(None), ProjetAction.date_fin.is_(None)),
    ))
    return q.order_by(ProjetAction.date_debut.desc(), ProjetAction.created_at.desc()).limit(8).all()


def _documents_questionnaires(secteur: str | None) -> list[Questionnaire]:
    if not can("questionnaires:view"):
        return []
    q = Questionnaire.query
    if secteur:
        q = q.filter(db.or_(
            Questionnaire.secteurs.any(secteur=secteur),
            ~Questionnaire.secteurs.any(),
        ))
    return q.order_by(Questionnaire.is_active.desc(), Questionnaire.nom.asc()).limit(8).all()


def _documents_orientation_count(year: int, secteur: str | None) -> int:
    if not can("partenaires:view"):
        return 0
    q = OrientationAccesDroit.query.filter(
        OrientationAccesDroit.date_orientation >= date(year, 1, 1),
        OrientationAccesDroit.date_orientation <= date(year, 12, 31),
    )
    if secteur:
        q = q.filter(OrientationAccesDroit.secteur == secteur)
    elif not can("scope:all_secteurs"):
        q = q.filter(OrientationAccesDroit.secteur == getattr(current_user, "secteur_assigne", None))
    return q.count()


@bp.route("/documents")
@login_required
def documents_exports():
    year, selected_secteur, secteurs = _documents_scope()
    stat_args = _documents_compact_args(
        date_from=date(year, 1, 1).isoformat(),
        date_to=date(year, 12, 31).isoformat(),
        secteur=selected_secteur,
    )
    finance_args = _documents_compact_args(annee=year, secteur=selected_secteur)
    finance_sector_args = _documents_compact_args(year=year, secteur=selected_secteur)
    bilan_args = _documents_compact_args(year=year, secteur=selected_secteur)
    orientation_args = _documents_compact_args(year=year, secteur_filter=selected_secteur)
    quality_args = _documents_compact_args(secteur=selected_secteur)

    groups: list[dict] = []

    def add_group(title: str, intro: str, cards: list[dict]):
        cards = [card for card in cards if card]
        if cards:
            groups.append({"title": title, "intro": intro, "cards": cards})

    if can("statsimpact:view") or can("stats:view"):
        add_group("Présences et stats-impact", "Exports alimentés par les présences d'émargement.", [
            {
                "title": "Exports stats-impact",
                "meta": "Présences, ateliers, démographie",
                "actions": [
                    {"label": "Ouvrir", "url": url_for("statsimpact.exports", **stat_args), "primary": True},
                    {"label": "XLSX complet", "url": url_for("statsimpact.magatomatique_export", **stat_args)},
                    {"label": "XLSX annuel", "url": url_for("statsimpact.magatomatique_export", export_mode="per_atelier", **stat_args)},
                    {"label": "CSV présences", "url": url_for("statsimpact.magatomatique_export_csv", **stat_args)},
                ],
            },
        ])

    if can("bilans:view"):
        add_group("Rapports annuels et financeurs", "Sorties consolidées pour bilan, pilotage et financeurs.", [
            {
                "title": f"Rapport annuel {year}",
                "meta": "DOCX narratif et indicateurs",
                "actions": [
                    {"label": "Préparer", "url": url_for("bilans.bilans_lourds", year=year), "primary": True},
                    {"label": "Export DOCX", "url": url_for("bilans.bilans_lourds_export_docx", year=year)},
                ],
            },
            {
                "title": "Bilan de pilotage",
                "meta": "Synthèse annuelle et alertes",
                "actions": [
                    {"label": "Ouvrir", "url": url_for("bilans.dashboard", **bilan_args), "primary": True},
                    {"label": "Export XLSX", "url": url_for("bilans.dashboard_export_xlsx", year=year)},
                ],
            },
            {
                "title": "Bilan financier global",
                "meta": "Subventions, engagé, reste",
                "actions": [
                    {"label": "Ouvrir", "url": url_for("main.bilan_global", **finance_args), "primary": True},
                    {"label": "Export XLSX", "url": url_for("main.bilan_global_export_xlsx", **finance_args)},
                    {"label": "Dépenses CSV", "url": url_for("main.export_depenses_csv")} if can("depenses:view") else None,
                ],
            },
        ])

    if can("partenaires:view") or can("dashboard:view"):
        add_group("Suivi et accès aux droits", "Exports pour cartographier les demandes, les orientations et les points à reprendre.", [
            {
                "title": f"Orientations accès aux droits {year}",
                "meta": f"{_documents_orientation_count(year, selected_secteur)} orientation(s) dans le périmètre",
                "actions": [
                    {"label": "Ouvrir", "url": url_for("partenaires.orientations", **orientation_args), "primary": True},
                    {"label": "Export XLSX", "url": url_for("partenaires.export_orientations_xlsx", **orientation_args)},
                ],
            } if can("partenaires:view") else None,
            {
                "title": "Qualité des données",
                "meta": "Anomalies et points à transformer en rappels",
                "actions": [
                    {"label": "Ouvrir", "url": url_for("main.qualite_donnees_transverse", **quality_args), "primary": True},
                    {"label": "Export CSV", "url": url_for("main.qualite_donnees_transverse_export_csv", **quality_args)},
                    {"label": "Centre de suivi", "url": url_for("main.suivi_rappels")},
                ],
            } if can("dashboard:view") else None,
        ])

    if can("projets:view"):
        add_group("Projets et actions", "Fiches projet, actions détaillées, budgets et indicateurs.", [
            {
                "title": "Liste des projets",
                "meta": "Accès aux fiches projet",
                "actions": [
                    {"label": "Ouvrir", "url": url_for("projets.projets_list"), "primary": True},
                ],
            },
            {
                "title": "Pilotage financier projet",
                "meta": "Exports annuels par secteur",
                "actions": [
                    {"label": "Ouvrir", "url": url_for("projets.finance_secteur", **finance_sector_args), "primary": True},
                    {"label": "Export XLSX", "url": url_for("projets.finance_secteur_export", **finance_sector_args)},
                ],
            },
        ])

    if can("questionnaires:view"):
        add_group("Questionnaires et retours", "Exports des réponses qualitatives ou d'impact.", [
            {
                "title": "Questionnaires d'impact",
                "meta": "Réponses exportables en CSV",
                "actions": [
                    {"label": "Ouvrir", "url": url_for("questionnaires.index"), "primary": True},
                ],
            },
        ])

    _hub_forbidden_if_empty(groups)
    subventions = _documents_subventions(year, selected_secteur)
    projects = _documents_projects(selected_secteur)
    actions = _documents_actions(year, selected_secteur)
    questionnaires = _documents_questionnaires(selected_secteur)

    return render_template(
        "documents_exports.html",
        year=year,
        selected_secteur=selected_secteur,
        secteurs=secteurs,
        groups=groups,
        subventions=subventions,
        projects=projects,
        actions=actions,
        questionnaires=questionnaires,
        summary={
            "sorties": sum(len(group["cards"]) for group in groups),
            "subventions": len(subventions),
            "projects": len(projects),
            "actions": len(actions),
            "questionnaires": len(questionnaires),
            "orientations": _documents_orientation_count(year, selected_secteur),
        },
    )


@bp.route("/ressources")
@login_required
def hub_ressources():
    cards = []

    if can("inventaire:view"):
        cards.append({
            "title": "Inventaire matériel",
            "subtitle": "Suivre le matériel, les achats et les équipements liés aux dépenses.",
            "primary_label": "Ouvrir inventaire",
            "primary_url": url_for("inventaire_materiel.list_items"),
            "secondary": [
                {"label": "Ajouter du matériel", "url": url_for("inventaire_materiel.new_item")} if can("inventaire:edit") else None,
            ],
            "tag": "Matériel",
        })

    if can("partenaires:view"):
        cards.append({
            "title": "Annuaire partenaires",
            "subtitle": "Retrouver les structures, contacts et interventions partenaires.",
            "primary_label": "Ouvrir partenaires",
            "primary_url": url_for("partenaires.index"),
            "secondary": [
                {"label": "Ajouter un partenaire", "url": url_for("partenaires.create")} if can("partenaires:edit") else None,
            ],
            "tag": "Réseau",
        })

    _hub_forbidden_if_empty(cards)
    return render_template(
        "hub_ressources.html",
        title="Ressources",
        intro="Les ressources utiles autour des projets : matériel, partenaires et outils de soutien.",
        cards=cards,
    )





