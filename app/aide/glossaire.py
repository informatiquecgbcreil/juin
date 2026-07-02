"""Glossaire métier : le dico du social pour les nouveaux salariés.

Chaque terme est défini en français courant, avec si besoin une note
« Dans l'application » qui fait le lien entre le mot du métier et
l'endroit où on le retrouve dans le logiciel. C'est aussi le document
de référence du vocabulaire : quand un écran hésite entre deux mots
(séance/session…), c'est le terme du glossaire qui fait foi.

Règles d'écriture :
- public : quelqu'un qui débute dans un centre social ET dans le logiciel ;
- une définition = 1 à 3 phrases, zéro jargon non expliqué ;
- les sigles sont toujours développés.
"""

GLOSSAIRE: list[dict] = [
    {
        "categorie": "Les personnes",
        "icone": "👥",
        "termes": [
            {
                "terme": "Participant",
                "definition": "Toute personne qui prend part à une activité du centre, quel que soit son âge. Une fiche participant = une personne réelle, qu'on retrouve d'année en année.",
                "dans_app": "Menu Participants. C'est la fiche centrale : présences, passeport, parcours y sont rattachés.",
            },
            {
                "terme": "Usager / bénéficiaire",
                "definition": "Autres mots pour « participant », employés par certains financeurs ou administrations. C'est la même chose.",
                "dans_app": "L'application dit toujours « participant ».",
            },
            {
                "terme": "Habitant",
                "definition": "Personne qui vit dans un quartier du territoire, qu'elle fréquente le centre ou non. Le centre social travaille pour les habitants, pas seulement pour ses inscrits.",
                "dans_app": "Module Quartiers et carte des habitants.",
            },
            {
                "terme": "Bénévole",
                "definition": "Personne qui donne du temps gratuitement pour faire vivre le centre (animation, accompagnement, conseil d'administration…). Leur temps a une valeur reconnue par les financeurs.",
                "dans_app": "Case « bénévole » sur la fiche participant, page Bénévolat pour les heures et leur valorisation.",
            },
            {
                "terme": "Salarié",
                "definition": "Membre de l'équipe payé par la structure. On le compte en personnes et en ETP (voir ce mot).",
                "dans_app": "Module RH, réservé à la direction.",
            },
        ],
    },
    {
        "categorie": "L'activité au quotidien",
        "icone": "📅",
        "termes": [
            {
                "terme": "Secteur",
                "definition": "Grande famille d'activités du centre : Jeunesse, Familles, Insertion, Numérique… Chaque atelier, projet ou dépense appartient à un secteur, et beaucoup de personnes de l'équipe ne voient que le leur.",
                "dans_app": "Le secteur est demandé à la création de presque tout. Votre « portée » (en haut de page) indique le vôtre.",
            },
            {
                "terme": "Atelier",
                "definition": "Activité régulière ou ponctuelle proposée aux habitants : accompagnement scolaire, cours de français, café des parents… Un atelier contient des séances.",
                "dans_app": "Menu Présences : la liste des ateliers est le point de départ pour faire l'appel.",
            },
            {
                "terme": "Séance",
                "definition": "Un rendez-vous daté d'un atelier : l'accompagnement scolaire du mardi 14 mars, c'est une séance. C'est à la séance qu'on note les présents. (On disait parfois « session » : c'est le même mot.)",
                "dans_app": "Dans la page d'un atelier. Une séance peut être « événementielle » (voir Événement).",
            },
            {
                "terme": "Présence",
                "definition": "Le fait qu'une personne était à une séance. C'est LA donnée de base : les statistiques, les bilans et les financements reposent dessus. Pas de présence notée = activité invisible.",
                "dans_app": "Se coche sur la feuille d'émargement d'une séance, ou via le kiosque.",
            },
            {
                "terme": "Émargement / faire l'appel",
                "definition": "Noter qui est présent à une séance. « Émarger », c'est signer ou cocher sa présence.",
                "dans_app": "Bouton principal de chaque séance. Le guide « Je fais l'appel d'une séance » vous accompagne.",
            },
            {
                "terme": "Kiosque",
                "definition": "Écran (souvent une tablette à l'entrée) où les gens pointent eux-mêmes leur arrivée avec un code affiché par l'animateur. Évite de faire l'appel à la main.",
                "dans_app": "Bouton « Kiosque » sur la page d'émargement d'une séance ; il génère un code et un lien.",
            },
            {
                "terme": "Événement (séance événementielle)",
                "definition": "Temps fort ponctuel : fête de quartier, sortie familiale, repas partagé. Compté à part dans les bilans nationaux (SENACS), car différent d'un atelier régulier.",
                "dans_app": "Case « événement » sur la séance.",
            },
            {
                "terme": "Capacité",
                "definition": "Nombre de places d'une séance ou d'un atelier. Sert à mesurer le taux de remplissage.",
            },
        ],
    },
    {
        "categorie": "Le suivi des parcours",
        "icone": "🎓",
        "termes": [
            {
                "terme": "Passeport (de compétences)",
                "definition": "La page qui rassemble tout le parcours d'apprentissage d'un participant : compétences acquises, évaluations, notes des animateurs, participation.",
                "dans_app": "Bouton « Passeport » sur la fiche d'un participant.",
            },
            {
                "terme": "Compétence",
                "definition": "Savoir-faire concret qu'une personne développe au centre : « écrire un mail », « prendre la parole en groupe »… On évalue sa progression, pas une note scolaire.",
                "dans_app": "Module Apprentissages ; les compétences s'évaluent depuis l'émargement ou le passeport.",
            },
            {
                "terme": "Référentiel",
                "definition": "La liste organisée des compétences qu'on suit. C'est le « catalogue » commun à toute la structure.",
                "dans_app": "Apprentissages → Référentiels (modifiable par les personnes habilitées).",
            },
            {
                "terme": "Module pédagogique",
                "definition": "Paquet de compétences travaillées ensemble pendant un cycle de séances (ex. module « premiers pas ordinateur »).",
                "dans_app": "Se rattache aux séances pour proposer les bonnes compétences à évaluer.",
            },
            {
                "terme": "Insertion",
                "definition": "Accompagnement individuel vers l'emploi, la formation, les droits ou les papiers. Suit des informations sensibles (titre de séjour, diplômes) réservées aux personnes habilitées.",
                "dans_app": "Module Insertion, visible uniquement avec les droits correspondants.",
            },
            {
                "terme": "CIR (Contrat d'intégration républicaine)",
                "definition": "Contrat signé entre l'État et une personne étrangère nouvellement arrivée : formation civique et cours de français. Une info utile au suivi insertion.",
            },
            {
                "terme": "Orientation",
                "definition": "Le fait d'envoyer une personne vers un partenaire (assistante sociale, mission locale, association…) et de suivre ce qu'il en advient.",
                "dans_app": "Depuis la fiche participant ou le module Partenaires ; les orientations à relancer remontent dans « À traiter ».",
            },
            {
                "terme": "Droit à l'image / consentement",
                "definition": "Autorisation écrite qu'une personne donne (ou refuse) pour être photographiée ou filmée. Obligatoire avant toute diffusion. Se demande dès l'accueil.",
                "dans_app": "Sur la fiche participant. L'export RGPD de la fiche est possible à la demande de la personne.",
            },
            {
                "terme": "RGPD",
                "definition": "Règlement général sur la protection des données : la loi européenne qui encadre ce qu'on enregistre sur les gens. En pratique : ne saisir que l'utile, et pouvoir montrer/effacer les données d'une personne si elle le demande.",
            },
        ],
    },
    {
        "categorie": "Éducation populaire & pouvoir d'agir",
        "icone": "✊",
        "termes": [
            {
                "terme": "Éducation populaire",
                "definition": "L'idée fondatrice des centres sociaux : chacun peut apprendre, transmettre et agir toute sa vie, en dehors de l'école, à partir de ce qu'il vit. On apprend ensemble, en faisant, et les savoirs de chacun comptent — pas seulement les diplômes.",
                "dans_app": "C'est l'esprit du module Apprentissages : on y évalue des progrès réels, pas des notes scolaires.",
            },
            {
                "terme": "Développement du pouvoir d'agir (DPA)",
                "definition": "Accompagner les personnes pour qu'elles reprennent prise sur leur vie et leur territoire : passer de « on fait pour eux » à « ils font eux-mêmes, avec nous ». On parle aussi d'« empowerment ». Concrètement : partir des envies des habitants, pas de nos programmes.",
                "dans_app": "L'échelle de Hart mesure exactement ça : la place réelle laissée aux habitants dans les décisions.",
            },
            {
                "terme": "Participation des habitants",
                "definition": "Le principe selon lequel les habitants ne sont pas des « publics » à qui on offre des services, mais des acteurs qui construisent le centre avec l'équipe : donner son avis, animer, décider, siéger au conseil d'administration.",
                "dans_app": "Onglet Participation du passeport (parcours individuel) et page Échelle de Hart (vue collective).",
            },
            {
                "terme": "Échelle de Hart",
                "definition": "Outil (imaginé par Roger Hart) qui décrit 8 marches de participation, de la simple présence décorative jusqu'à la co-décision. Monter l'escalier = laisser de plus en plus de vraie prise aux habitants. Ce n'est pas une note : c'est un repère pour se questionner.",
                "dans_app": "Représentée en escalier dans le passeport et en vue collective. C'est une évaluation humaine, jamais un calcul automatique.",
            },
            {
                "terme": "Aller-vers",
                "definition": "Ne pas attendre que les gens poussent la porte du centre : sortir, être présent en pied d'immeuble, sur le marché, à la sortie de l'école, pour toucher ceux qui ne viendraient jamais d'eux-mêmes.",
            },
            {
                "terme": "Co-construction",
                "definition": "Monter un projet AVEC les personnes concernées, du diagnostic à l'évaluation — pas seulement leur demander leur avis à la fin. Plus exigeant, plus lent, mais les actions co-construites tiennent dans le temps.",
            },
            {
                "terme": "Diagnostic partagé",
                "definition": "Photographie des besoins et des ressources d'un territoire, faite AVEC les habitants et les partenaires (et pas seulement à partir de statistiques). C'est la première étape du projet social.",
                "dans_app": "Les données quartiers, présences et questionnaires fournissent la matière chiffrée du diagnostic.",
            },
            {
                "terme": "Pair-aidance",
                "definition": "L'entraide entre personnes qui vivent ou ont vécu la même situation : un parent qui en accompagne un autre, un ancien apprenant qui aide un débutant. Le centre la favorise car elle crée de la confiance qu'aucun professionnel ne peut décréter.",
            },
            {
                "terme": "Lien social",
                "definition": "Ce qui relie les gens entre eux : se connaître, se rendre service, se sentir appartenir à un endroit. C'est la matière première du centre social — beaucoup d'actions n'ont pas d'autre but, et c'est déjà énorme.",
            },
            {
                "terme": "Mixité sociale",
                "definition": "Faire se rencontrer des personnes qui ne se croiseraient pas autrement : générations, quartiers, milieux, origines. Un repas partagé qui mélange vraiment, c'est de la mixité réussie.",
            },
            {
                "terme": "Médiation sociale",
                "definition": "Faciliter le dialogue là où il s'est rompu : entre voisins, entre familles et institutions (école, bailleur, CAF…). Le médiateur ne juge pas, il rétablit le lien.",
            },
            {
                "terme": "Animation globale",
                "definition": "Le socle du centre social financé par la CAF : une fonction d'accueil, d'écoute et de coordination qui bénéficie à tout le territoire, au-delà des activités. C'est ce qui distingue un centre social d'une simple structure d'activités.",
                "dans_app": "La prestation CAF correspondante (AGC) apparaît dans les subventions.",
            },
            {
                "terme": "Projet social",
                "definition": "LE document fondateur du centre : tous les 4 ans environ, il décrit le territoire (diagnostic), les priorités et les moyens. C'est sur lui que la CAF accorde l'agrément. Idéalement écrit avec les habitants.",
                "dans_app": "Les bilans et statistiques de l'application servent à l'écrire et à l'évaluer.",
            },
            {
                "terme": "Référent familles / ACF",
                "definition": "Le ou la professionnelle qui coordonne tout ce qui touche aux familles et à la parentalité, dans le cadre de l'Animation collective familles (ACF), financée par la CAF en complément de l'animation globale.",
            },
            {
                "terme": "Comité d'habitants / comité d'usagers",
                "definition": "Groupe d'habitants qui participe aux décisions du centre : programmation, aménagement, budget d'une action… Une des formes concrètes de la participation, entre le simple avis et le conseil d'administration.",
            },
            {
                "terme": "FPH (Fonds de participation des habitants)",
                "definition": "Petite enveloppe (souvent liée à la politique de la ville) que des habitants attribuent eux-mêmes à des micro-projets d'autres habitants : fête des voisins, sortie collective… Les habitants décident, la structure sécurise.",
            },
            {
                "terme": "FCSF & charte fédérale",
                "definition": "La Fédération des centres sociaux et socioculturels de France, qui relie les centres entre eux. Sa charte fonde l'action sur trois valeurs : dignité humaine, solidarité, démocratie.",
            },
            {
                "terme": "Laïcité",
                "definition": "Principe qui garantit à chacun la liberté de croire ou non, et la neutralité de la structure : le centre accueille tout le monde, sans prosélytisme d'aucune sorte. Au quotidien : on accueille les personnes telles qu'elles sont, et les activités restent ouvertes à tous.",
            },
        ],
    },
    {
        "categorie": "L'argent",
        "icone": "💰",
        "termes": [
            {
                "terme": "Subvention",
                "definition": "Argent versé par un financeur (CAF, ville, département, État…) pour mener une action. Se demande, s'obtient (ou pas), se justifie ensuite par un bilan.",
                "dans_app": "Menu Finances → Enveloppes : chaque subvention avec son demandé / attribué / reçu.",
            },
            {
                "terme": "Financeur",
                "definition": "Celui qui donne l'argent : CAF, commune, agglomération, État, fondation… Chacun a ses dossiers et ses bilans à rendre.",
            },
            {
                "terme": "Enveloppe",
                "definition": "Dans l'application, le suivi d'une subvention : combien demandé, combien attribué, combien déjà dépensé, combien il reste.",
                "dans_app": "Finances → Enveloppes.",
            },
            {
                "terme": "Dépense",
                "definition": "Achat ou facture imputé sur une enveloppe ou un projet : matériel, intervenant, transport… Bien imputer chaque dépense, c'est ce qui rend les bilans financiers justes.",
                "dans_app": "Finances → Dépenses.",
            },
            {
                "terme": "Projet",
                "definition": "Action structurée avec un objectif, un budget (charges et produits) et souvent plusieurs financeurs : « vacances familles », « atelier sociolinguistique »…",
                "dans_app": "Finances → Projets financés. Le guide « Je monte un projet » arrive bientôt.",
            },
            {
                "terme": "AAP (Appel à projets)",
                "definition": "Quand un financeur annonce : « je finance des projets sur tel thème, déposez vos dossiers ». On y répond avec un projet et un budget prévisionnel.",
            },
            {
                "terme": "Prévisionnel",
                "definition": "Budget estimé AVANT de faire : ce qu'on pense dépenser et recevoir. S'oppose au « réalisé », ce qui s'est vraiment passé.",
                "dans_app": "Finances → Prévisionnels & demandes, avec un générateur de budget.",
            },
            {
                "terme": "Charges / produits",
                "definition": "Les deux colonnes d'un budget : les charges = ce que ça coûte, les produits = ce qui finance (subventions, participations des familles…). Un budget équilibré : charges = produits.",
            },
            {
                "terme": "Coût unitaire",
                "definition": "Ce que coûte réellement une unité d'activité : une heure d'atelier, une présence. Utile pour objectiver les demandes de financement.",
                "dans_app": "Page Coût unitaire (Ressources).",
            },
            {
                "terme": "Valorisation du bénévolat",
                "definition": "Traduire les heures données par les bénévoles en euros (heures × taux horaire) pour les faire apparaître dans les budgets et bilans. Les financeurs y sont attentifs : c'est la richesse propre du centre.",
                "dans_app": "Page Bénévolat ; le taux horaire se règle dans les paramètres (direction/finance).",
            },
            {
                "terme": "Don & reçu fiscal (CERFA 11580)",
                "definition": "Don d'argent d'un particulier ou d'une entreprise. En échange, la structure délivre un reçu fiscal officiel (formulaire CERFA n° 11580) qui ouvre droit à une réduction d'impôt.",
                "dans_app": "Page Dons & reçus fiscaux (droits dédiés).",
            },
            {
                "terme": "ETP (Équivalent temps plein)",
                "definition": "Unité pour compter le personnel : une personne à mi-temps = 0,5 ETP. Permet de comparer des équipes aux contrats différents.",
                "dans_app": "Module RH ; repris automatiquement dans le SENACS.",
            },
            {
                "terme": "Masse salariale",
                "definition": "Le total des salaires et charges payés par la structure sur l'année. Première dépense d'un centre social.",
            },
            {
                "terme": "Trésorerie",
                "definition": "L'argent réellement disponible en caisse à un instant donné — à ne pas confondre avec le budget : on peut avoir un budget équilibré et une trésorerie vide si les subventions arrivent en retard.",
            },
        ],
    },
    {
        "categorie": "Les institutions et les bilans",
        "icone": "🏛️",
        "termes": [
            {
                "terme": "CAF (Caisse d'allocations familiales)",
                "definition": "Le financeur principal des centres sociaux. C'est elle qui délivre l'« agrément centre social », renouvelé sur la base d'un projet social et de bilans.",
            },
            {
                "terme": "Agrément / contrat de projet",
                "definition": "L'agrément est la reconnaissance officielle « centre social » par la CAF, accordée pour plusieurs années sur la base du contrat de projet : le document qui fixe les objectifs du centre pour la période.",
            },
            {
                "terme": "Bilan",
                "definition": "Le compte-rendu (chiffres + récit) qu'on rend à un financeur ou à ses instances : combien de personnes, quelles activités, quel argent utilisé, quels effets. Les bilans se préparent toute l'année : ils reposent sur les présences et dépenses saisies au quotidien.",
                "dans_app": "Menu Bilans. Le guide « Je prépare un bilan pour un financeur » vous accompagne.",
            },
            {
                "terme": "SENACS",
                "definition": "Système national d'échanges des centres sociaux : le questionnaire annuel que remplissent tous les centres (publics, activités, équipe, budget). Alimente l'observatoire national.",
                "dans_app": "L'application pré-remplit le SENACS à partir de vos données (Bilans).",
            },
            {
                "terme": "QPV (Quartier prioritaire de la politique de la ville)",
                "definition": "Quartier officiellement reconnu comme prioritaire par l'État. Beaucoup de financements ciblent les habitants des QPV : d'où l'importance de bien renseigner le quartier sur les fiches.",
                "dans_app": "Module Quartiers ; le quartier se choisit sur la fiche participant.",
            },
            {
                "terme": "CA / AG",
                "definition": "Conseil d'administration (les habitants et partenaires qui pilotent l'association) et assemblée générale (la réunion annuelle de tous les adhérents). On leur présente chiffres et bilans.",
                "dans_app": "Le bouton Imprimer / PDF du tableau de bord sort une synthèse présentable en CA.",
            },
            {
                "terme": "Questionnaire d'impact",
                "definition": "Questionnaire posé aux participants (avant/après une action, ou satisfaction) pour mesurer les effets réels au-delà des chiffres de fréquentation.",
                "dans_app": "Module Questionnaires.",
            },
            {
                "terme": "Indicateur",
                "definition": "Un chiffre qu'on suit dans le temps pour piloter : nombre de participants uniques, taux de présence, part d'habitants QPV… Un bon indicateur répond à une question qu'on se pose vraiment.",
            },
            {
                "terme": "Partenaire",
                "definition": "Structure avec qui le centre travaille : école, mission locale, CCAS, association… On oriente des personnes vers eux et on monte des actions ensemble.",
                "dans_app": "Module Partenaires, avec annuaire et carte.",
            },
            {
                "terme": "Politique de la ville / contrat de ville",
                "definition": "L'ensemble des moyens que l'État et les collectivités consacrent aux quartiers prioritaires (QPV). Le contrat de ville est le document local qui organise ces moyens — beaucoup d'appels à projets en découlent.",
            },
            {
                "terme": "CLAS (Contrat local d'accompagnement à la scolarité)",
                "definition": "Le dispositif qui finance l'accompagnement scolaire : aide aux devoirs, ouverture culturelle ET accompagnement des parents dans leur rôle. Un bilan spécifique est à rendre chaque année.",
                "dans_app": "Les présences des ateliers d'accompagnement scolaire alimentent directement ce bilan.",
            },
            {
                "terme": "REAAP (Réseau d'écoute, d'appui et d'accompagnement des parents)",
                "definition": "Le dispositif qui finance les actions de soutien à la parentalité : cafés des parents, groupes de parole, sorties familles. Porté par la CAF.",
            },
            {
                "terme": "ASL (Atelier sociolinguistique)",
                "definition": "Apprentissage du français à partir des situations de la vie quotidienne (école, santé, démarches) — on apprend la langue ET les codes pour être autonome. Différent d'un cours de français classique.",
            },
            {
                "terme": "Adulte-relais",
                "definition": "Poste de médiation sociale financé par l'État, réservé aux habitants des quartiers prioritaires. Beaucoup de médiateurs des centres sociaux sont sur ce type de contrat.",
            },
        ],
    },
    {
        "categorie": "Les mots de l'application",
        "icone": "🖥️",
        "termes": [
            {
                "terme": "Rôle & permissions",
                "definition": "Votre rôle (animateur, responsable de secteur, direction…) détermine ce que vous voyez et pouvez modifier. Si une page vous est refusée, c'est une question de droits, pas une panne.",
                "dans_app": "Votre rôle et votre portée s'affichent en haut de chaque page. La direction règle les droits dans Admin.",
            },
            {
                "terme": "Mode simple / expert",
                "definition": "Deux niveaux d'affichage : le mode simple montre l'essentiel du quotidien, le mode expert montre tout (graphiques, pilotage, réglages).",
                "dans_app": "Boutons Simple / Expert en haut à droite. Chacun choisit pour soi.",
            },
            {
                "terme": "Poste de travail (« Ma journée »)",
                "definition": "Le bloc d'accueil qui propose vos 3 à 5 actions du jour selon votre rôle, avec les compteurs du jour (séances, rappels).",
                "dans_app": "Page d'accueil, juste sous le titre.",
            },
            {
                "terme": "Guide pas à pas",
                "definition": "Un fil conducteur qui vous emmène sur les bonnes pages dans le bon ordre, avec une explication à chaque étape. On peut le quitter et le reprendre librement.",
                "dans_app": "Page Guides (lien sur l'accueil).",
            },
            {
                "terme": "À traiter (centre de suivi)",
                "definition": "La page qui rassemble tout ce qui attend une action : rappels, orientations à relancer, indicateurs à renseigner.",
                "dans_app": "Menu « À traiter ».",
            },
            {
                "terme": "Corbeille",
                "definition": "Rien ne se supprime directement : ateliers et séances passent d'abord à la corbeille, d'où on peut les restaurer. La suppression définitive est réservée aux rôles autorisés.",
            },
            {
                "terme": "Sauvegarde",
                "definition": "Copie de sécurité de toutes les données, pour pouvoir tout retrouver en cas de panne. À vérifier régulièrement — c'est le filet de sécurité de la structure.",
                "dans_app": "Admin → Sauvegardes (direction / admin technique).",
            },
        ],
    },
]


def glossaire_termes_plats() -> list[dict]:
    """Tous les termes à plat (pour tests et recherche)."""
    plats = []
    for cat in GLOSSAIRE:
        for t in cat["termes"]:
            plats.append({**t, "categorie": cat["categorie"]})
    return plats
