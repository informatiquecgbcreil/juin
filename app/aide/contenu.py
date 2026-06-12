"""Contenu de l'aide intégrée.

Deux structures alimentent toute l'aide de l'application :

- ``AIDE_PAGES`` : aide contextuelle par page. La clé est le nom de
  l'endpoint Flask (ex: "main.dashboard"). Le gabarit ``layout.html``
  affiche automatiquement un bandeau « Comprendre cette page » sur
  chaque page référencée ici — aucun template à modifier.
- ``NOTICE`` : la notice complète (centre d'aide /aide), organisée en
  chapitres. C'est le mode d'emploi de référence, imprimable.

Un test (tests/test_aide.py) garantit que chaque clé de AIDE_PAGES
correspond à une vraie page de l'application : impossible de laisser
l'aide diverger du logiciel sans casser la CI.

Règles d'écriture (public : débutant complet) :
- vouvoiement, phrases courtes, pas de jargon technique ;
- dire d'abord À QUOI SERT la page, puis COMMENT s'en servir ;
- une astuce concrète quand c'est utile.
"""

AIDE_PAGES: dict[str, dict] = {
    # ------------------------------------------------------------------
    # Accueil et navigation
    # ------------------------------------------------------------------
    "main.dashboard": {
        "titre": "Le tableau de bord",
        "resume": "C'est votre page d'accueil : elle rassemble les chiffres clés et vos raccourcis favoris.",
        "etapes": [
            "Consultez les indicateurs pour voir l'activité de la structure d'un coup d'œil.",
            "Utilisez les boutons d'action rapide pour vos tâches courantes.",
            "La barre de recherche en haut retrouve une personne, un projet ou une subvention en quelques lettres.",
        ],
        "astuce": "Le bouton « Personnaliser » vous permet de choisir les indicateurs et raccourcis affichés. Le mode Simple/Expert (en haut à droite) allège ou enrichit l'affichage.",
    },
    "main.dashboard_customize": {
        "titre": "Personnaliser votre tableau de bord",
        "resume": "Choisissez ici ce que VOUS voulez voir en arrivant dans l'application.",
        "etapes": [
            "Cochez les indicateurs et raccourcis qui vous servent au quotidien.",
            "Enregistrez : ce réglage n'affecte que votre compte, pas celui de vos collègues.",
        ],
        "astuce": "Le bouton « Réinitialiser » revient à l'affichage standard si vous êtes perdu.",
    },
    "main.global_search_results": {
        "titre": "La recherche globale",
        "resume": "Une seule barre de recherche pour tout retrouver : personnes, projets, subventions, ateliers, partenaires, quartiers.",
        "etapes": [
            "Tapez un nom (même partiel) : les résultats sont classés par type.",
            "Cliquez sur un résultat pour ouvrir sa fiche.",
        ],
        "astuce": "Vous pouvez préciser le type : « participants dupont » ne cherchera que dans les personnes.",
    },
    "main.suivi_rappels": {
        "titre": "À traiter — vos rappels et alertes",
        "resume": "Cette page rassemble tout ce qui demande votre attention : rappels, orientations en attente, échéances de projets et de budgets.",
        "etapes": [
            "Les éléments sont classés du plus urgent (rouge) au moins urgent.",
            "Cliquez sur un élément pour ouvrir la fiche concernée et agir.",
            "Créez vos propres rappels avec le bouton « Nouveau rappel » : ils apparaîtront ici à l'échéance.",
        ],
        "astuce": "Consultez cette page chaque matin : c'est votre liste de choses à faire.",
    },
    "main.hub_publics": {
        "titre": "L'espace Publics",
        "resume": "Le point d'entrée vers tout ce qui concerne les personnes : participants, orientations, quartiers.",
        "etapes": ["Choisissez une carte pour accéder au module correspondant."],
    },
    "main.hub_activites": {
        "titre": "L'espace Activités",
        "resume": "Le point d'entrée vers les ateliers, les séances, l'émargement et les projets.",
        "etapes": ["Choisissez une carte pour accéder au module correspondant."],
    },
    "main.hub_bilans": {
        "titre": "L'espace Bilans",
        "resume": "Le point d'entrée vers les statistiques, les bilans financiers et le bilan SENACS.",
        "etapes": ["Choisissez une carte pour accéder au module correspondant."],
    },
    "main.hub_ressources": {
        "titre": "L'espace Ressources",
        "resume": "Le point d'entrée vers les partenaires, questionnaires, inventaires et le matériel.",
        "etapes": ["Choisissez une carte pour accéder au module correspondant."],
    },
    "main.documents_exports": {
        "titre": "Documents prêts à transmettre",
        "resume": "Retrouvez ici, par année, les exports et documents imprimables : listes, bilans, fiches.",
        "etapes": [
            "Choisissez l'année en haut de la page.",
            "Cliquez sur un document pour le télécharger ou l'imprimer.",
        ],
    },

    # ------------------------------------------------------------------
    # Participants
    # ------------------------------------------------------------------
    "participants.list_participants": {
        "titre": "L'annuaire des participants",
        "resume": "Toutes les personnes accueillies par la structure, tous secteurs confondus. Une personne = une seule fiche, même si elle fréquente plusieurs secteurs.",
        "etapes": [
            "Recherchez par nom dans la barre de recherche.",
            "Cliquez sur une personne pour ouvrir sa fiche complète.",
            "« Nouveau participant » crée une fiche : vérifiez d'abord que la personne n'existe pas déjà !",
        ],
        "astuce": "Une fiche en double fausse toutes les statistiques. En cas de doute, cherchez d'abord, créez ensuite. La page « Doublons » aide à fusionner les fiches créées en double.",
    },
    "participants.new_participant": {
        "titre": "Créer une fiche participant",
        "resume": "Enregistrez une nouvelle personne. Seuls le nom et le prénom sont obligatoires, mais chaque information compte pour les bilans.",
        "etapes": [
            "Renseignez au minimum nom et prénom.",
            "La date de naissance et le quartier servent aux statistiques officielles (CAF/SENACS) : renseignez-les dès que possible.",
            "Posez la question du droit à l'image et enregistrez la réponse : votre nom et la date seront tracés comme preuve.",
        ],
        "astuce": "Une fiche complète aujourd'hui = un bilan SENACS juste en mars. Les fiches incomplètes sont signalées dans « Qualité des données ».",
    },
    "participants.edit_participant": {
        "titre": "La fiche participant",
        "resume": "Toutes les informations d'une personne : identité, coordonnées, quartier, droit à l'image, parcours.",
        "etapes": [
            "Modifiez les champs puis « Enregistrer ».",
            "La section « Droit à l'image » trace qui a recueilli la réponse et quand : c'est votre preuve RGPD.",
            "« Exporter toutes les données » génère le dossier complet à remettre à la personne si elle le demande (obligation légale, délai d'un mois).",
        ],
        "astuce": "L'anonymisation est définitive : elle efface l'identité mais conserve les chiffres pour les statistiques. À utiliser si la personne demande l'effacement de ses données.",
    },
    "participants.duplicates": {
        "titre": "Fusionner les fiches en double",
        "resume": "Quand une personne a été créée deux fois, cette page permet de fusionner les fiches sans perdre l'historique.",
        "etapes": [
            "Vérifiez que les fiches proposées concernent bien la même personne.",
            "Choisissez la fiche à conserver : les présences et données de l'autre y seront rattachées.",
        ],
        "astuce": "En cas de doute (homonymes !), comparez les dates de naissance avant de fusionner.",
    },

    # ------------------------------------------------------------------
    # Activités / ateliers / émargement
    # ------------------------------------------------------------------
    "activite.index": {
        "titre": "Les ateliers et activités",
        "resume": "La liste des ateliers de votre secteur : ateliers réguliers, accompagnements individuels, événements.",
        "etapes": [
            "Cliquez sur un atelier pour voir ses séances.",
            "« Nouvelle activité » crée un atelier ; vous ajouterez ensuite ses séances.",
            "La corbeille conserve les ateliers supprimés : rien n'est perdu par erreur.",
        ],
        "astuce": "Renseignez les horaires des séances : ils alimentent les « heures face public » du bilan SENACS.",
    },
    "activite.sessions": {
        "titre": "Les séances d'un atelier",
        "resume": "Chaque date d'atelier est une séance. C'est depuis ici que vous faites l'émargement (la liste de présence).",
        "etapes": [
            "« Nouvelle séance » pour ajouter une date.",
            "Cliquez sur « Émargement » pour pointer les présents.",
            "Les séances annulées peuvent être marquées comme telles plutôt que supprimées.",
        ],
    },
    "activite.emargement": {
        "titre": "L'émargement (liste de présence)",
        "resume": "Pointez les personnes présentes à la séance. C'est LA donnée qui alimente toutes vos statistiques de fréquentation.",
        "etapes": [
            "Cochez les présents parmi les inscrits, ou ajoutez une personne via la recherche.",
            "Une personne absente de l'annuaire ? Créez sa fiche d'abord (bouton dédié).",
            "La feuille peut être signée sur écran (tablette) ou imprimée puis archivée.",
        ],
        "astuce": "Un émargement fait le jour même est fiable ; un émargement reconstitué de mémoire en fin de mois ne l'est pas. Les présences comptent pour les bilans CAF.",
    },
    "activite.participants": {
        "titre": "Les participants de votre secteur",
        "resume": "La vue « secteur » de l'annuaire : les personnes qui fréquentent vos activités.",
        "etapes": [
            "Cliquez sur une personne pour modifier sa fiche.",
            "Générez une attestation de participation depuis la fiche.",
        ],
    },
    "activite.attestations": {
        "titre": "Les attestations de participation",
        "resume": "Générez des attestations officielles (présence, participation) en série pour un groupe de personnes.",
        "etapes": [
            "Sélectionnez les personnes concernées.",
            "Choisissez les options du document puis générez : un fichier Word par personne.",
        ],
    },
    "activite.emargement_models": {
        "titre": "Les modèles de feuilles d'émargement",
        "resume": "Personnalisez l'apparence des feuilles d'émargement imprimées (logo, mentions, colonnes).",
        "etapes": [
            "Créez un modèle par type de besoin (atelier régulier, événement…).",
            "Le modèle choisi s'applique au moment d'imprimer une feuille.",
        ],
    },

    # ------------------------------------------------------------------
    # Projets
    # ------------------------------------------------------------------
    "projets.projets_list": {
        "titre": "Les projets",
        "resume": "Un projet = une action structurée avec des objectifs, un budget et des indicateurs (ex : CLAS, FLE, projet jardin).",
        "etapes": [
            "Cliquez sur un projet pour ouvrir son dossier complet.",
            "« Nouveau projet » : donnez un nom et un secteur, vous compléterez ensuite.",
        ],
        "astuce": "Reliez vos ateliers aux projets : les présences alimenteront automatiquement les indicateurs du projet.",
    },
    "projets.projets_edit": {
        "titre": "Le dossier d'un projet",
        "resume": "Tout le projet en un seul endroit : description, actions, journal de bord, indicateurs, budget, bilans.",
        "etapes": [
            "Les onglets du haut naviguent entre les volets du projet.",
            "Le journal de bord garde la mémoire des faits marquants : remplissez-le au fil de l'eau, il nourrira vos bilans.",
            "« Indicateurs » mesure l'avancement ; « Budget » suit les charges et produits.",
        ],
    },
    "projets.finance_home": {
        "titre": "Le pilotage financier",
        "resume": "La vue d'ensemble financière : où en sont les budgets, secteur par secteur.",
        "etapes": [
            "Choisissez votre secteur et l'année.",
            "La vue « simple » va à l'essentiel ; la vue détaillée montre toutes les lignes.",
        ],
    },
    "projets.finance_secteur": {
        "titre": "Le pilotage financier du secteur",
        "resume": "Le tableau de bord financier annuel de votre secteur : subventions, dépenses, restes à consommer.",
        "etapes": [
            "Vérifiez les alertes en haut de page : elles signalent les incohérences à corriger.",
            "L'export Excel produit le dossier financier annuel complet.",
        ],
    },

    # ------------------------------------------------------------------
    # Subventions et dépenses
    # ------------------------------------------------------------------
    "main.subventions_list": {
        "titre": "Les subventions",
        "resume": "Chaque financement reçu (CAF, Ville, État…) est une subvention, découpée en lignes de budget.",
        "etapes": [
            "Cliquez sur une subvention pour ouvrir son pilotage détaillé.",
            "« Nouvelle subvention » : nom, secteur, année et montants.",
        ],
        "astuce": "Le « demandé » est ce que vous avez sollicité, l'« attribué » ce qui est accordé, le « reçu » ce qui est arrivé sur le compte. Les trois peuvent différer !",
    },
    "main.subvention_pilotage": {
        "titre": "Le pilotage d'une subvention",
        "resume": "Suivez ligne par ligne l'utilisation d'un financement : prévu, dépensé, reste à consommer.",
        "etapes": [
            "Créez les lignes de budget correspondant aux postes de votre convention.",
            "Rattachez les dépenses aux lignes : le « consommé » se calcule tout seul.",
            "Le bilan de la subvention (bouton dédié) est votre justificatif pour le financeur.",
        ],
        "astuce": "Une dépense peut être répartie entre plusieurs lignes ou subventions (ventilation au prorata).",
    },
    "budget.depenses_list": {
        "titre": "Les dépenses",
        "resume": "Toutes les dépenses enregistrées, avec leur affectation aux subventions.",
        "etapes": [
            "« Nouvelle dépense » : montant, libellé, justificatif, et affectation à une ou plusieurs lignes de budget.",
            "Une dépense non affectée n'est justifiée auprès d'aucun financeur : la liste les signale.",
        ],
    },
    "budget.depense_new": {
        "titre": "Enregistrer une dépense",
        "resume": "Saisissez la dépense puis affectez-la aux budgets concernés : c'est ce qui permet de justifier l'usage des subventions.",
        "etapes": [
            "Renseignez le montant, la date et le libellé (et la pièce justificative si possible).",
            "Affectez la dépense à une ou plusieurs lignes de subvention.",
        ],
        "astuce": "Saisissez les dépenses au fil de l'eau : un bilan financier se prépare toute l'année, pas la veille de l'échéance.",
    },

    # ------------------------------------------------------------------
    # Bilans et statistiques
    # ------------------------------------------------------------------
    "main.stats": {
        "titre": "Les statistiques",
        "resume": "Les chiffres de fréquentation et d'activité, filtrables par année, secteur et projet.",
        "etapes": [
            "Réglez les filtres en haut puis parcourez les indicateurs.",
            "Ces chiffres viennent des émargements : leur fiabilité dépend du pointage des présences.",
        ],
    },
    "main.stats_bilans": {
        "titre": "Stats & bilans",
        "resume": "La vue de pilotage : indicateurs clés et accès aux différents bilans.",
        "etapes": ["Choisissez l'année et le périmètre, puis ouvrez le bilan souhaité."],
    },
    "main.bilan_global": {
        "titre": "Le bilan financeurs",
        "resume": "La synthèse financière globale de la structure, prête à présenter aux financeurs.",
        "etapes": [
            "Vérifiez l'année sélectionnée.",
            "L'export Excel produit le document à transmettre.",
        ],
    },
    "bilans.dashboard": {
        "titre": "Les bilans",
        "resume": "Le centre des bilans : par secteur, par subvention, bilans narratifs (« lourds ») et SENACS.",
        "etapes": ["Choisissez le type de bilan selon votre destinataire (financeur, CA, CAF)."],
    },
    "bilans.bilan_senacs": {
        "titre": "Le bilan SENACS (CAF)",
        "resume": "L'enquête annuelle nationale des centres sociaux. Cette page pré-calcule les chiffres demandés à partir de vos données.",
        "etapes": [
            "Choisissez l'année des données (campagne SENACS de l'année suivante).",
            "Vérifiez les alertes : fiches sans date de naissance, séances sans durée — corrigez-les pour fiabiliser les chiffres.",
            "Exportez les tableaux de consolidation et reportez-les dans senacs.fr.",
        ],
        "astuce": "Les participants sont automatiquement dédoublonnés entre secteurs : une personne qui fréquente trois ateliers compte une seule fois, comme l'exige l'enquête. Bénévolat, emplois et finances restent à saisir à la main.",
    },
    "main.qualite_donnees_transverse": {
        "titre": "La qualité des données",
        "resume": "Le détecteur de fiches incomplètes ou incohérentes : tout ce qui risque de fausser vos bilans.",
        "etapes": [
            "Parcourez les anomalies par famille (participants, projets, finances…).",
            "Cliquez sur une anomalie pour ouvrir la fiche et la corriger.",
            "Créez un rappel sur une anomalie pour la traiter plus tard.",
        ],
        "astuce": "Dix minutes par semaine sur cette page = des bilans annuels sans mauvaise surprise.",
    },
    "statsimpact.dashboard": {
        "titre": "Stats-impact : le tableau de bord avancé",
        "resume": "Analyses détaillées de la fréquentation : démographie, assiduité, comparaisons entre périodes.",
        "etapes": [
            "Réglez les filtres (période, secteur, ateliers).",
            "Les graphiques se mettent à jour automatiquement.",
        ],
    },
    "statsimpact.exports": {
        "titre": "Stats-impact : les exports",
        "resume": "Les exports Excel détaillés de la fréquentation, dont le classeur « par atelier ».",
        "etapes": [
            "Choisissez la période et le périmètre.",
            "Téléchargez l'export adapté à votre besoin.",
        ],
    },

    # ------------------------------------------------------------------
    # Administration et contrôle
    # ------------------------------------------------------------------
    "admin.users": {
        "titre": "Les comptes utilisateurs",
        "resume": "Créez les comptes de vos collègues et choisissez leur rôle : c'est le rôle qui détermine ce que chacun peut voir et faire.",
        "etapes": [
            "« Créer un compte » : email, mot de passe provisoire, rôle et secteur.",
            "Rôle « responsable_secteur » : accès limité à son secteur. Rôle « direction » : accès global complet. Rôle « admin_tech » : gestion technique sans les données métier.",
            "Un collègue qui part ? Supprimez ou désactivez son compte le jour même.",
        ],
        "astuce": "Donnez à chacun le rôle MINIMUM nécessaire : c'est la meilleure protection des données de vos publics.",
    },
    "main.controle": {
        "titre": "La page Contrôle",
        "resume": "Les outils de vérification et de configuration avancée de l'application.",
        "etapes": [
            "« Purge RGPD » gère l'anonymisation des fiches inactives.",
            "Le référentiel de consommation sert aux estimations d'impact énergétique.",
        ],
    },
    "main.purge_rgpd": {
        "titre": "La purge RGPD",
        "resume": "La loi interdit de garder indéfiniment les données d'une personne qui ne vient plus. Cette page anonymise automatiquement les fiches sans activité depuis 3 ans.",
        "etapes": [
            "Consultez la liste des fiches en attente d'anonymisation.",
            "Une personne listée fréquente encore la structure ? Ouvrez sa fiche et enregistrez-la : elle sort de la liste.",
            "La purge tourne toute seule chaque jour ; le bouton permet de la lancer immédiatement.",
        ],
        "astuce": "L'anonymisation conserve les chiffres (les présences passées comptent toujours dans les statistiques) mais efface définitivement l'identité.",
    },
}


# ----------------------------------------------------------------------
# LA NOTICE COMPLÈTE (centre d'aide /aide)
# ----------------------------------------------------------------------
# Chaque chapitre : id (ancre), icone, titre, intro, sections [(titre, [paragraphes])]

NOTICE: list[dict] = [
    {
        "id": "demarrer",
        "icone": "🚀",
        "titre": "Démarrer avec l'application",
        "intro": "Ce qu'il faut savoir pour vos premiers pas.",
        "sections": [
            ("Se connecter", [
                "Ouvrez l'adresse de l'application dans votre navigateur (demandez-la à votre responsable). Saisissez votre email et votre mot de passe.",
                "Mot de passe oublié ? Cliquez sur le lien sous le formulaire : vous recevrez un email de réinitialisation (si la messagerie est configurée). Sinon, demandez à un administrateur.",
                "Après 5 mots de passe erronés, la connexion est bloquée 15 minutes par sécurité : c'est normal, attendez puis réessayez.",
            ]),
            ("Comprendre l'écran", [
                "En haut : le menu de navigation, organisé en espaces (Publics, Activités, Bilans, Ressources) ; la barre de recherche globale ; vos réglages d'affichage.",
                "Le bouton Simple/Expert change la densité de l'information : commencez en Simple, passez en Expert quand vous serez à l'aise.",
                "Le bouton « ? » (en haut à droite) ouvre cette notice à tout moment. Sur la plupart des pages, un bandeau « Comprendre cette page » explique le contexte.",
            ]),
            ("Les trois règles d'or", [
                "1. UNE personne = UNE fiche. Cherchez toujours avant de créer : les doublons faussent tous les bilans.",
                "2. Pointez les présences le jour même : l'émargement est la matière première de toutes vos statistiques.",
                "3. Complétez les fiches (date de naissance, quartier) : le bilan CAF de mars se prépare toute l'année.",
            ]),
        ],
    },
    {
        "id": "participants",
        "icone": "👥",
        "titre": "Les participants",
        "intro": "L'annuaire unique des personnes accueillies, partagé entre tous les secteurs.",
        "sections": [
            ("Créer et modifier une fiche", [
                "Espace Publics → Participants → Nouveau participant. Seuls nom et prénom sont obligatoires, mais chaque champ compte : la date de naissance alimente les tranches d'âge SENACS, le quartier alimente les statistiques de territoire (QPV).",
                "La fiche est partagée entre secteurs : si la personne fréquente déjà un autre secteur, sa fiche existe déjà — utilisez la recherche.",
            ]),
            ("Le droit à l'image (RGPD)", [
                "Demandez à la personne si elle accepte d'apparaître en photo/vidéo, et enregistrez sa réponse dans la section dédiée de sa fiche. La date et votre nom sont tracés automatiquement : c'est la preuve du recueil, exigée en cas de contrôle.",
                "Une personne peut changer d'avis à tout moment : mettez simplement à jour le champ.",
            ]),
            ("Le droit d'accès et l'effacement (RGPD)", [
                "Toute personne peut demander une copie de ses données : bouton « Exporter toutes les données » sur sa fiche. Vous avez un mois pour la remettre.",
                "Toute personne peut demander l'effacement : utilisez « Anonymiser » sur sa fiche. Son identité est effacée définitivement, mais les chiffres de fréquentation restent comptés.",
                "Les fiches sans activité depuis 3 ans sont anonymisées automatiquement (voir Administration → Purge RGPD).",
            ]),
            ("Les doublons", [
                "Si une personne a été créée deux fois, la page Doublons propose la fusion : l'historique des deux fiches est réuni sur celle que vous conservez.",
            ]),
        ],
    },
    {
        "id": "activites",
        "icone": "📅",
        "titre": "Ateliers, séances et émargement",
        "intro": "Le cœur du suivi d'activité : qui participe à quoi, et quand.",
        "sections": [
            ("Organiser un atelier", [
                "Un atelier est une activité (FLE, CLAS, atelier numérique, café couture…). Chaque date de cet atelier est une séance.",
                "Espace Activités → Nouvelle activité : nom, secteur, type (collectif ou individuel). Puis ajoutez les séances avec dates et horaires.",
                "Renseignez les horaires des séances : ils calculent les « heures face public » demandées par la CAF.",
            ]),
            ("Faire l'émargement", [
                "Ouvrez la séance → Émargement. Cochez les présents, ajoutez les nouveaux venus par la recherche.",
                "La feuille peut être signée à l'écran (tablette en mode kiosque) ou imprimée. Les feuilles archivées sont conservées et téléchargeables.",
                "C'est l'émargement qui crée les « participations » comptées dans tous les bilans : sa régularité fait la fiabilité de vos chiffres.",
            ]),
            ("Attestations", [
                "Espace Activités → Attestations : sélectionnez des personnes et générez leurs attestations de participation (documents Word personnalisables).",
            ]),
        ],
    },
    {
        "id": "projets",
        "icone": "🎯",
        "titre": "Les projets",
        "intro": "Structurer une action : objectifs, journal de bord, indicateurs, budget.",
        "sections": [
            ("Créer un projet", [
                "Espace Activités → Projets → Nouveau projet. Un projet rassemble des actions, un budget (charges/produits), des indicateurs de réussite et un journal de bord.",
                "Reliez vos ateliers au projet : les présences alimenteront automatiquement ses indicateurs.",
            ]),
            ("Suivre et rendre compte", [
                "Le journal de bord conserve les faits marquants, réussites et difficultés : remplissez-le au fil de l'eau, c'est la matière de vos bilans narratifs.",
                "La fiche projet imprimable et le bilan d'action servent de support aux comités de pilotage et aux financeurs.",
            ]),
        ],
    },
    {
        "id": "finances",
        "icone": "💶",
        "titre": "Subventions, dépenses et pilotage financier",
        "intro": "Suivre chaque financement et justifier son utilisation.",
        "sections": [
            ("Les subventions", [
                "Une subvention = un financement reçu (CAF, Ville, Département…), pour un secteur et une année. Trois montants la décrivent : demandé (sollicité), attribué (accordé), reçu (versé).",
                "Le pilotage d'une subvention se fait ligne par ligne : créez les lignes de budget correspondant à votre convention (salaires, activités, fonctionnement…).",
            ]),
            ("Les dépenses", [
                "Enregistrez chaque dépense puis affectez-la aux lignes de budget concernées. Une dépense peut être répartie entre plusieurs subventions (ventilation).",
                "Le « consommé » et le « reste à consommer » de chaque ligne se calculent automatiquement.",
            ]),
            ("Les bilans financiers", [
                "Le bilan d'une subvention (depuis sa page de pilotage) justifie l'utilisation du financement auprès du financeur.",
                "Le pilotage financier du secteur donne la vue annuelle complète, avec alertes d'incohérence et export Excel.",
                "Le bilan financeurs global (espace Bilans) présente la synthèse de toute la structure.",
            ]),
        ],
    },
    {
        "id": "bilans",
        "icone": "📊",
        "titre": "Statistiques et bilans",
        "intro": "Des émargements aux bilans officiels.",
        "sections": [
            ("D'où viennent les chiffres ?", [
                "Toutes les statistiques découlent des fiches participants et des émargements. Une fiche incomplète ou une présence non pointée = un chiffre faux.",
                "La page « Qualité des données » liste tout ce qui mérite correction : consultez-la régulièrement.",
            ]),
            ("Le bilan SENACS (CAF)", [
                "Espace Bilans → Bilan SENACS : l'application pré-calcule les publics (participants uniques dédoublonnés entre secteurs, tranches d'âge officielles, quartiers), le tableau actions/séances et la liste des partenaires.",
                "L'export Excel reprend vos tableaux de consolidation : il reste à saisir les chiffres dans senacs.fr, et à compléter à la main ce que l'application ne gère pas (bénévolat, emplois, finances, événementiel).",
            ]),
            ("Stats-impact", [
                "Pour aller plus loin : analyses démographiques, assiduité, comparaisons de périodes, exports détaillés par atelier.",
            ]),
        ],
    },
    {
        "id": "rappels",
        "icone": "🔔",
        "titre": "Rappels et suivi quotidien",
        "intro": "Ne rien laisser passer.",
        "sections": [
            ("La page « À traiter »", [
                "Elle rassemble vos rappels, les orientations en attente, les échéances de projets et de budgets. Consultez-la chaque matin.",
                "Créez un rappel sur n'importe quel sujet avec une échéance : il remontera au bon moment, classé par urgence.",
            ]),
        ],
    },
    {
        "id": "administration",
        "icone": "🔧",
        "titre": "Administration (direction / référent)",
        "intro": "Gérer les comptes, les droits et les obligations légales.",
        "sections": [
            ("Les comptes et les rôles", [
                "Administration → Utilisateurs : créez un compte par collègue, avec le rôle adapté. Le rôle détermine TOUT ce que la personne peut voir et faire.",
                "« responsable_secteur » : son secteur uniquement. « direction » : tout. « admin_tech » : la technique (comptes, réglages) sans les données métier. D'autres rôles affinés existent dans l'écran RBAC.",
                "Règle d'or : le minimum nécessaire à chacun. Un départ ? Supprimez le compte le jour même.",
            ]),
            ("La purge RGPD", [
                "Contrôle → Purge RGPD : les fiches sans activité depuis 3 ans sont anonymisées automatiquement, une fois par jour. La page montre la liste en attente et permet de lancer manuellement.",
                "Chaque anonymisation est tracée dans le journal de l'application.",
            ]),
            ("La sécurité des connexions", [
                "Chaque tentative de connexion est journalisée (conservée 1 an). Après 5 échecs en 15 minutes, le compte est temporairement bloqué : les tentatives de piratage par essais successifs sont neutralisées.",
            ]),
            ("Identité de la structure", [
                "Administration → Instance : nom de la structure, logos, adresse publique, messagerie (SMTP) pour les emails de réinitialisation de mot de passe.",
            ]),
        ],
    },
    {
        "id": "installation",
        "icone": "💾",
        "titre": "Installation, sauvegardes et dépannage",
        "intro": "Pour la personne qui gère le serveur (aucune compétence technique requise).",
        "sections": [
            ("Installer l'application", [
                "Téléchargez le projet (ZIP), ouvrez le dossier « installation », clic droit sur Installer.ps1 → Exécuter avec PowerShell, et répondez aux questions. Le script installe tout : Python, la base de données PostgreSQL, l'application, le démarrage automatique et la sauvegarde quotidienne.",
                "Le guide détaillé pas-à-pas est dans installation/LISEZMOI-INSTALLATION.md.",
            ]),
            ("Mettre à jour", [
                "Téléchargez la nouvelle version et relancez Installer.ps1 : il remplace le programme en conservant vos données, et applique tout seul les évolutions de la base.",
            ]),
            ("Les sauvegardes", [
                "Une sauvegarde tourne chaque nuit à 2h00. Testez une restauration de temps en temps : une sauvegarde jamais testée n'est qu'une promesse.",
            ]),
            ("Quand quelque chose ne va pas", [
                "Une page d'erreur ? Le détail technique est enregistré dans instance/logs/erreurs.log sur le serveur : transmettez ce fichier à votre support, il contient la date, la page et la cause exacte.",
                "L'application ne répond plus ? Redémarrez le service Windows « AppGestion » (ou l'ordinateur). Vos données sont dans PostgreSQL : un redémarrage ne perd rien.",
            ]),
        ],
    },
]
