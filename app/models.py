
from app.utils.dates import utcnow
from datetime import date
import json
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db

# ---------- USERS ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    nom = db.Column(db.String(120), nullable=False, default="Utilisateur")
    role = db.Column(db.String(40), nullable=False, default="responsable_secteur")
    secteur_assigne = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    # Flask-Login
    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    # RBAC helpers (roles/permissions)
    def has_perm(self, code: str) -> bool:
        codes: set[str] = set()
        for role in getattr(self, "roles", []) or []:
            for p in getattr(role, "permissions", []) or []:
                codes.add(p.code)
        return code in codes

    @property
    def role_codes(self) -> list[str]:
        return sorted([r.code for r in getattr(self, "roles", []) or []])


    def has_role(self, code: str | None) -> bool:
        """True si l'utilisateur possède le rôle RBAC `code`.

        Seuls les rôles RBAC (User.roles -> Role.code) font foi. La colonne
        legacy `User.role` ne donne aucun droit : elle est migrée vers un
        rôle RBAC au démarrage par `bootstrap_rbac`.
        Gère quelques alias historiques (directrice -> direction, etc.).
        """
        if not code:
            return False

        c = (code or "").strip().lower()

        aliases = {
            # historiques
            "directrice": "direction",
            "directeur": "direction",
            "financiere": "finance",
            "financière": "finance",
            "responsable_secteurs": "responsable_secteur",
        }
        c = aliases.get(c, c)

        try:
            for r in (getattr(self, "roles", []) or []):
                rc = (getattr(r, "code", "") or "").strip().lower()
                rc = aliases.get(rc, rc)
                if rc == c:
                    return True
        except Exception:
            pass

        return False


class UserDashboardPreference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    ui_mode = db.Column(db.String(20), nullable=False, default="simple")
    quick_actions_json = db.Column(db.Text, nullable=True)
    widgets_json = db.Column(db.Text, nullable=True)
    customized = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    user = db.relationship("User", backref=db.backref("dashboard_pref", uselist=False, cascade="all, delete-orphan"))


# =========================================================
# RBAC (Roles & Permissions)
# ---------------------------------------------------------
# Objectif: remplacer progressivement la logique "role = string" par
# une vraie gestion fine des permissions.
# Le champ User.role reste (compatibilité), mais on le mappe vers
# un ou plusieurs Roles.

user_roles = db.Table(
    "user_roles",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
    db.Column("role_id", db.Integer, db.ForeignKey("role.id", ondelete="CASCADE"), primary_key=True),
)

role_permissions = db.Table(
    "role_permissions",
    db.Column("role_id", db.Integer, db.ForeignKey("role.id", ondelete="CASCADE"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permission.id", ondelete="CASCADE"), primary_key=True),
)


class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(60), unique=True, nullable=False, index=True)  # ex: "finance", "admin_tech"
    label = db.Column(db.String(120), nullable=False, default="Rôle")

    permissions = db.relationship(
        "Permission",
        secondary=role_permissions,
        lazy="subquery",
        backref=db.backref("roles", lazy=True),
    )

    def __repr__(self) -> str:
        return f"<Role {self.code}>"


class Permission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(120), unique=True, nullable=False, index=True)  # ex: "subventions:edit"
    label = db.Column(db.String(200), nullable=False, default="Permission")
    category = db.Column(db.String(60), nullable=True, index=True)  # ex: "Subventions"

    def __repr__(self) -> str:
        return f"<Perm {self.code}>"




class InstanceSettings(db.Model):
    """Paramètres d'instance modifiables depuis l'admin (1 ligne)."""

    id = db.Column(db.Integer, primary_key=True)
    app_name = db.Column(db.String(120), nullable=True)
    organization_name = db.Column(db.String(180), nullable=True)
    app_logo_path = db.Column(db.String(255), nullable=True)
    organization_logo_path = db.Column(db.String(255), nullable=True)
    public_base_url = db.Column(db.String(255), nullable=True)

    # SMTP (override optionnel des variables d'environnement)
    smtp_host = db.Column(db.String(255), nullable=True)
    smtp_port = db.Column(db.Integer, nullable=True)
    smtp_username = db.Column(db.String(255), nullable=True)
    smtp_password = db.Column(db.String(255), nullable=True)
    smtp_use_tls = db.Column(db.Boolean, nullable=True)
    smtp_sender = db.Column(db.String(255), nullable=True)

    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)


class Secteur(db.Model):
    """Secteur métier (liste administrable).

    ⚠️ Pour limiter le refacto, on conserve *label* comme valeur utilisée
    partout (Subvention.secteur, Projet.secteur, etc.).
    Le champ `code` sert surtout d'identifiant stable/slug.
    """

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False, index=True)
    label = db.Column(db.String(120), unique=True, nullable=False, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    def __repr__(self) -> str:
        return f"<Secteur {self.code} ({'on' if self.is_active else 'off'})>"


# Relation User.roles (déclarée après Role)
User.roles = db.relationship(
    "Role",
    secondary=user_roles,
    lazy="subquery",
    backref=db.backref("users", lazy=True),
)


# ---------- PEDAGOGIE ----------
class Referentiel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)


class Competence(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    referentiel_id = db.Column(db.Integer, db.ForeignKey("referentiel.id"), nullable=False)
    code = db.Column(db.String(40), nullable=False)
    nom = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)

    referentiel = db.relationship("Referentiel", backref=db.backref("competences", cascade="all, delete-orphan"))


projet_competence = db.Table(
    "projet_competence",
    db.Column("projet_id", db.Integer, db.ForeignKey("projet.id"), primary_key=True),
    db.Column("competence_id", db.Integer, db.ForeignKey("competence.id"), primary_key=True),
)


atelier_competence = db.Table(
    "atelier_competence",
    db.Column("atelier_id", db.Integer, db.ForeignKey("atelier_activite.id"), primary_key=True),
    db.Column("competence_id", db.Integer, db.ForeignKey("competence.id"), primary_key=True),
)


session_competence = db.Table(
    "session_competence",
    db.Column("session_id", db.Integer, db.ForeignKey("session_activite.id"), primary_key=True),
    db.Column("competence_id", db.Integer, db.ForeignKey("competence.id"), primary_key=True),
)


objectif_competence = db.Table(
    "objectif_competence",
    db.Column("objectif_id", db.Integer, db.ForeignKey("objectif.id"), primary_key=True),
    db.Column("competence_id", db.Integer, db.ForeignKey("competence.id"), primary_key=True),
)

module_competence = db.Table(
    "module_competence",
    db.Column("module_id", db.Integer, db.ForeignKey("pedagogie_module.id"), primary_key=True),
    db.Column("competence_id", db.Integer, db.ForeignKey("competence.id"), primary_key=True),
)

atelier_module = db.Table(
    "atelier_module",
    db.Column("atelier_id", db.Integer, db.ForeignKey("atelier_activite.id"), primary_key=True),
    db.Column("module_id", db.Integer, db.ForeignKey("pedagogie_module.id"), primary_key=True),
)

session_module = db.Table(
    "session_module",
    db.Column("session_id", db.Integer, db.ForeignKey("session_activite.id"), primary_key=True),
    db.Column("module_id", db.Integer, db.ForeignKey("pedagogie_module.id"), primary_key=True),
)


class PedagogieModule(db.Model):
    __tablename__ = "pedagogie_module"
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(160), nullable=False, unique=True, index=True)
    description = db.Column(db.Text, nullable=True)
    actif = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    competences = db.relationship(
        "Competence",
        secondary=module_competence,
        backref=db.backref("modules", lazy="dynamic"),
    )


class ObjectifCompetenceMap(db.Model):
    __tablename__ = "objectif_competence_map"

    id = db.Column(db.Integer, primary_key=True)
    objectif_id = db.Column(db.Integer, db.ForeignKey("objectif.id", ondelete="CASCADE"), nullable=False, index=True)
    competence_id = db.Column(db.Integer, db.ForeignKey("competence.id", ondelete="CASCADE"), nullable=False, index=True)
    poids = db.Column(db.Float, nullable=False, default=1.0)
    actif = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    objectif = db.relationship("Objectif")
    competence = db.relationship("Competence")

    __table_args__ = (
        db.UniqueConstraint("objectif_id", "competence_id", name="uq_objectif_competence_map"),
    )




class PlanProjetAtelierModule(db.Model):
    __tablename__ = "plan_projet_atelier_module"

    id = db.Column(db.Integer, primary_key=True)
    projet_id = db.Column(db.Integer, db.ForeignKey("projet.id", ondelete="CASCADE"), nullable=False, index=True)
    atelier_id = db.Column(db.Integer, db.ForeignKey("atelier_activite.id", ondelete="CASCADE"), nullable=False, index=True)
    module_id = db.Column(db.Integer, db.ForeignKey("pedagogie_module.id", ondelete="CASCADE"), nullable=False, index=True)
    actif = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    projet = db.relationship("Projet")
    atelier = db.relationship("AtelierActivite")
    module = db.relationship("PedagogieModule")

    __table_args__ = (
        db.UniqueConstraint("projet_id", "atelier_id", "module_id", name="uq_plan_projet_atelier_module"),
    )

class Objectif(db.Model):
    __tablename__ = "objectif"
    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("objectif.id"), nullable=True)
    type = db.Column(db.String(30), nullable=False)  # general | specifique | operationnel
    titre = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    seuil_validation = db.Column(db.Float, nullable=False, default=60.0)

    projet_id = db.Column(db.Integer, db.ForeignKey("projet.id"), nullable=True)
    atelier_id = db.Column(db.Integer, db.ForeignKey("atelier_activite.id"), nullable=True)
    session_id = db.Column(db.Integer, db.ForeignKey("session_activite.id"), nullable=True)
    module_id = db.Column(db.Integer, db.ForeignKey("pedagogie_module.id"), nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow)

    parent = db.relationship("Objectif", remote_side=[id], backref=db.backref("enfants", cascade="all, delete-orphan"))
    projet = db.relationship("Projet")
    atelier = db.relationship("AtelierActivite")
    session = db.relationship("SessionActivite")
    module = db.relationship("PedagogieModule")
    competences = db.relationship(
        "Competence",
        secondary=objectif_competence,
        backref=db.backref("objectifs", lazy="dynamic"),
    )


# ---------- PROJETS ----------
class Projet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False)
    secteur = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=True)

    cr_filename = db.Column(db.String(255), nullable=True)
    cr_original_name = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow)

    subventions = db.relationship("SubventionProjet", back_populates="projet", cascade="all, delete-orphan")
    # AAP / Budget projet (charges/produits/ventilations)
    charges_projet = db.relationship("ChargeProjet", back_populates="projet", cascade="all, delete-orphan")
    produits_projet = db.relationship("ProduitProjet", back_populates="projet", cascade="all, delete-orphan")
    journal_entries = db.relationship("ProjetJournalEntry", back_populates="projet", cascade="all, delete-orphan")
    actions_detaillees = db.relationship("ProjetAction", back_populates="projet", cascade="all, delete-orphan")
    competences = db.relationship(
        "Competence",
        secondary=projet_competence,
        backref=db.backref("projets", lazy="dynamic"),
    )

    @property
    def total_demande(self):
        return round(sum(float(sp.subvention.montant_demande or 0) for sp in self.subventions), 2)

    @property
    def total_attribue(self):
        return round(sum(float(sp.subvention.montant_attribue or 0) for sp in self.subventions), 2)

    @property
    def total_recu(self):
        return round(sum(float(sp.subvention.montant_recu or 0) for sp in self.subventions), 2)

    @property
    def total_reel_lignes(self):
        return round(sum(float(sp.subvention.total_reel_lignes or 0) for sp in self.subventions), 2)

    @property
    def total_engage(self):
        return round(sum(float(sp.subvention.total_engage or 0) for sp in self.subventions), 2)

    @property
    def total_reste(self):
        return round(sum(float(sp.subvention.total_reste or 0) for sp in self.subventions), 2)


    # -----------------------------
    # Budget AAP (par projet)
    # -----------------------------
    @property
    def total_charges_previsionnel(self):
        return round(sum(float(c.montant_previsionnel or 0) for c in self.charges_projet), 2)

    @property
    def total_charges_reel(self):
        return round(sum(float(c.montant_reel or 0) for c in self.charges_projet), 2)

    @property
    def total_produits_demandes(self):
        return round(sum(float(p.montant_demande or 0) for p in self.produits_projet), 2)

    @property
    def total_produits_accordes(self):
        return round(sum(float(p.montant_accorde or 0) for p in self.produits_projet), 2)

    @property
    def total_produits_recus(self):
        return round(sum(float(p.montant_recu or 0) for p in self.produits_projet), 2)

    @property
    def reste_a_financer(self):
        # basé sur l'accordé (et non la demande)
        return round(float(self.total_charges_previsionnel or 0) - float(self.total_produits_accordes or 0), 2)




class ChargeProjet(db.Model):
    __tablename__ = "charge_projet"
    id = db.Column(db.Integer, primary_key=True)
    projet_id = db.Column(db.Integer, db.ForeignKey("projet.id"), nullable=False)

    # bloc = directe / indirecte (comme le tableau AAP)
    bloc = db.Column(db.String(20), nullable=False, default="directe")  # directe | indirecte
    # code plan comptable : 60/61/62/63/64/65/...
    code_plan = db.Column(db.String(20), nullable=False, default="60")

    libelle = db.Column(db.String(255), nullable=False)

    montant_previsionnel = db.Column(db.Float, default=0.0)
    montant_reel = db.Column(db.Float, default=0.0)

    commentaire = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    projet = db.relationship("Projet", back_populates="charges_projet")
    ventilations = db.relationship("VentilationProjet", back_populates="charge", cascade="all, delete-orphan")
    depenses = db.relationship("Depense", back_populates="charge_projet", passive_deletes=True)

    @property
    def ventile(self):
        return round(sum(float(v.montant_ventile or 0) for v in self.ventilations), 2)

    @property
    def reste_a_financer(self):
        return round(float(self.montant_previsionnel or 0) - float(self.ventile or 0), 2)

    @property
    def engage(self):
        # engagement réel via les dépenses rattachées à cette charge
        return round(sum(float(d.montant or 0) for d in self.depenses if not d.est_supprimee), 2)

    @property
    def reste_a_engager(self):
        base = float(self.montant_reel or 0) if float(self.montant_reel or 0) > 0 else float(self.montant_previsionnel or 0)
        return round(base - float(self.engage or 0), 2)


class ProduitProjet(db.Model):
    __tablename__ = "produit_projet"
    id = db.Column(db.Integer, primary_key=True)
    projet_id = db.Column(db.Integer, db.ForeignKey("projet.id"), nullable=False)

    financeur = db.Column(db.String(255), nullable=False)
    categorie = db.Column(db.String(50), nullable=False, default="autre")  # etat/region/departement/commune/caf/europe/prive/autofinancement/...
    statut = db.Column(db.String(30), nullable=False, default="prevu")  # prevu/demande/accorde/partiel/refuse

    montant_demande = db.Column(db.Float, default=0.0)
    montant_accorde = db.Column(db.Float, default=0.0)
    montant_recu = db.Column(db.Float, default=0.0)

    reference_dossier = db.Column(db.String(120), nullable=True)
    commentaire = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    projet = db.relationship("Projet", back_populates="produits_projet")
    ventilations = db.relationship("VentilationProjet", back_populates="produit", cascade="all, delete-orphan")

    @property
    def ventile(self):
        return round(sum(float(v.montant_ventile or 0) for v in self.ventilations), 2)

    @property
    def reste_a_ventiler(self):
        return round(float(self.montant_accorde or 0) - float(self.ventile or 0), 2)


class VentilationProjet(db.Model):
    __tablename__ = "ventilation_projet"
    id = db.Column(db.Integer, primary_key=True)
    charge_id = db.Column(db.Integer, db.ForeignKey("charge_projet.id", ondelete="CASCADE"), nullable=False)
    produit_id = db.Column(db.Integer, db.ForeignKey("produit_projet.id", ondelete="CASCADE"), nullable=False)
    montant_ventile = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=utcnow)

    charge = db.relationship("ChargeProjet", back_populates="ventilations")
    produit = db.relationship("ProduitProjet", back_populates="ventilations")

class BudgetPrevisionnel(db.Model):
    __tablename__ = "budget_previsionnel"
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False)
    annee = db.Column(db.Integer, nullable=False, index=True)
    secteur = db.Column(db.String(80), nullable=False, index=True)
    statut = db.Column(db.String(30), nullable=False, default="brouillon")  # brouillon / valide / archive
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    lignes = db.relationship("BudgetPrevisionnelLigne", back_populates="budget", cascade="all, delete-orphan")
    appels = db.relationship("AppelProjetBudget", back_populates="budget", cascade="all, delete-orphan")

    @property
    def total_charges(self):
        return round(sum(float(l.montant or 0) for l in self.lignes if l.nature == "charge"), 2)

    @property
    def total_produits(self):
        return round(sum(float(l.montant or 0) for l in self.lignes if l.nature == "produit"), 2)

    @property
    def solde(self):
        return round(float(self.total_produits or 0) - float(self.total_charges or 0), 2)


class BudgetPrevisionnelLigne(db.Model):
    __tablename__ = "budget_previsionnel_ligne"
    id = db.Column(db.Integer, primary_key=True)
    budget_id = db.Column(db.Integer, db.ForeignKey("budget_previsionnel.id"), nullable=False, index=True)
    projet_id = db.Column(db.Integer, db.ForeignKey("projet.id"), nullable=True, index=True)

    nature = db.Column(db.String(10), nullable=False, default="charge")  # charge / produit
    compte = db.Column(db.String(20), nullable=False, default="60")
    libelle = db.Column(db.String(255), nullable=False)
    montant = db.Column(db.Float, default=0.0)
    commentaire = db.Column(db.Text, nullable=True)
    ordre = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)

    budget = db.relationship("BudgetPrevisionnel", back_populates="lignes")
    projet = db.relationship("Projet", backref=db.backref("lignes_previsionnelles", lazy="dynamic"))
    lignes_appel = db.relationship("AppelProjetBudgetLigne", back_populates="ligne_budget", cascade="all, delete-orphan")


class AppelProjetBudget(db.Model):
    __tablename__ = "appel_projet_budget"
    id = db.Column(db.Integer, primary_key=True)
    budget_id = db.Column(db.Integer, db.ForeignKey("budget_previsionnel.id"), nullable=False, index=True)
    subvention_id = db.Column(db.Integer, db.ForeignKey("subvention.id"), nullable=True, index=True)
    projet_id = db.Column(db.Integer, db.ForeignKey("projet.id"), nullable=True, index=True)

    nom = db.Column(db.String(200), nullable=False)
    financeur = db.Column(db.String(200), nullable=True)
    statut = db.Column(db.String(30), nullable=False, default="preparation")
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    budget = db.relationship("BudgetPrevisionnel", back_populates="appels")
    subvention = db.relationship("Subvention", backref=db.backref("budgets_appel", lazy="dynamic"))
    projet = db.relationship("Projet", backref=db.backref("budgets_appel", lazy="dynamic"))
    lignes = db.relationship("AppelProjetBudgetLigne", back_populates="appel", cascade="all, delete-orphan")

    @property
    def total_charges(self):
        return round(sum(float(l.montant_retenu or 0) for l in self.lignes if l.ligne_budget and l.ligne_budget.nature == "charge"), 2)

    @property
    def total_produits(self):
        return round(sum(float(l.montant_retenu or 0) for l in self.lignes if l.ligne_budget and l.ligne_budget.nature == "produit"), 2)

    @property
    def solde(self):
        return round(float(self.total_produits or 0) - float(self.total_charges or 0), 2)


class AppelProjetBudgetLigne(db.Model):
    __tablename__ = "appel_projet_budget_ligne"
    id = db.Column(db.Integer, primary_key=True)
    appel_id = db.Column(db.Integer, db.ForeignKey("appel_projet_budget.id"), nullable=False, index=True)
    budget_ligne_id = db.Column(db.Integer, db.ForeignKey("budget_previsionnel_ligne.id"), nullable=False, index=True)
    montant_retenu = db.Column(db.Float, default=0.0)
    pourcentage_retenu = db.Column(db.Float, nullable=True)
    commentaire = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    appel = db.relationship("AppelProjetBudget", back_populates="lignes")
    ligne_budget = db.relationship("BudgetPrevisionnelLigne", back_populates="lignes_appel")

class SubventionProjet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    projet_id = db.Column(db.Integer, db.ForeignKey("projet.id"), nullable=False)
    subvention_id = db.Column(db.Integer, db.ForeignKey("subvention.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    projet = db.relationship("Projet", back_populates="subventions")
    subvention = db.relationship("Subvention", back_populates="projets")

    __table_args__ = (
        db.UniqueConstraint("projet_id", "subvention_id", name="uq_projet_subvention"),
    )



# ---------- LIENS PROJET <-> ATELIERS (activité) ----------
class ProjetAtelier(db.Model):
    __tablename__ = "projet_atelier"
    id = db.Column(db.Integer, primary_key=True)
    projet_id = db.Column(db.Integer, db.ForeignKey("projet.id"), nullable=False, index=True)
    atelier_id = db.Column(db.Integer, db.ForeignKey("atelier_activite.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    projet = db.relationship("Projet", backref=db.backref("ateliers", cascade="all, delete-orphan"))
    atelier = db.relationship("AtelierActivite")

    __table_args__ = (
        db.UniqueConstraint("projet_id", "atelier_id", name="uq_projet_atelier"),
    )


# ---------- INDICATEURS DE PROJET ----------
class ProjetIndicateur(db.Model):
    __tablename__ = "projet_indicateur"
    id = db.Column(db.Integer, primary_key=True)
    projet_id = db.Column(db.Integer, db.ForeignKey("projet.id"), nullable=False, index=True)

    # template (V1)
    code = db.Column(db.String(60), nullable=False)
    label = db.Column(db.String(200), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    params_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    projet = db.relationship("Projet", backref=db.backref("indicateurs", cascade="all, delete-orphan"))

    __table_args__ = (
        db.UniqueConstraint("projet_id", "code", name="uq_projet_indicateur_code"),
    )

    def params(self):
        try:
            return json.loads(self.params_json or "{}")
        except Exception:
            return {}


class ProjetJournalEntry(db.Model):
    __tablename__ = "projet_journal_entry"

    id = db.Column(db.Integer, primary_key=True)
    projet_id = db.Column(db.Integer, db.ForeignKey("projet.id", ondelete="CASCADE"), nullable=False, index=True)
    entry_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    categorie = db.Column(db.String(40), nullable=False, default="fait_marquant", index=True)
    titre = db.Column(db.String(180), nullable=True)
    contenu = db.Column(db.Text, nullable=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    projet = db.relationship("Projet", back_populates="journal_entries")
    user = db.relationship("User")


class ProjetAction(db.Model):
    __tablename__ = "projet_action"

    id = db.Column(db.Integer, primary_key=True)
    projet_id = db.Column(db.Integer, db.ForeignKey("projet.id", ondelete="CASCADE"), nullable=False, index=True)
    titre = db.Column(db.String(200), nullable=False)
    categorie = db.Column(db.String(50), nullable=False, default="atelier", index=True)
    statut = db.Column(db.String(30), nullable=False, default="prevue", index=True)
    referent = db.Column(db.String(160), nullable=True)
    date_debut = db.Column(db.Date, nullable=True, index=True)
    date_fin = db.Column(db.Date, nullable=True, index=True)
    lieu = db.Column(db.String(200), nullable=True)
    public_vise = db.Column(db.Text, nullable=True)
    territoire = db.Column(db.Text, nullable=True)
    objectifs = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=True)
    partenaires_text = db.Column(db.Text, nullable=True)
    bilan_qualitatif = db.Column(db.Text, nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    projet = db.relationship("Projet", back_populates="actions_detaillees")
    user = db.relationship("User")
    atelier_links = db.relationship("ProjetActionAtelier", back_populates="action", cascade="all, delete-orphan")


class ProjetActionAtelier(db.Model):
    __tablename__ = "projet_action_atelier"

    id = db.Column(db.Integer, primary_key=True)
    action_id = db.Column(db.Integer, db.ForeignKey("projet_action.id", ondelete="CASCADE"), nullable=False, index=True)
    atelier_id = db.Column(db.Integer, db.ForeignKey("atelier_activite.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    action = db.relationship("ProjetAction", back_populates="atelier_links")
    atelier = db.relationship("AtelierActivite")

    __table_args__ = (
        db.UniqueConstraint("action_id", "atelier_id", name="uq_projet_action_atelier"),
    )




# ---------- SUBVENTIONS / BUDGET ----------
class Subvention(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False)
    secteur = db.Column(db.String(80), nullable=False)
    annee_exercice = db.Column(db.Integer, nullable=False, default=2025)

    montant_demande = db.Column(db.Float, default=0.0)
    montant_attribue = db.Column(db.Float, default=0.0)
    montant_recu = db.Column(db.Float, default=0.0)

    est_archive = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    lignes = db.relationship("LigneBudget", backref="source_sub", cascade="all, delete-orphan")
    depense_affectations = db.relationship("DepenseAffectation", back_populates="subvention", cascade="all, delete-orphan")
    projets = db.relationship("SubventionProjet", back_populates="subvention", cascade="all, delete-orphan")

    @property
    def total_base_lignes(self):
        # compat: total des CHARGES (lignes nature=charge)
        return round(sum(float(l.montant_base or 0) for l in self.lignes if getattr(l, "nature", "charge") == "charge"), 2)

    @property
    def total_reel_lignes(self):
        # compat: total des CHARGES (lignes nature=charge)
        return round(sum(float(l.montant_reel or 0) for l in self.lignes if getattr(l, "nature", "charge") == "charge"), 2)


    @property
    def total_base_produits(self):
        return round(sum(float(l.montant_base or 0) for l in self.lignes if getattr(l, "nature", "charge") == "produit"), 2)

    @property
    def total_reel_produits(self):
        return round(sum(float(l.montant_reel or 0) for l in self.lignes if getattr(l, "nature", "charge") == "produit"), 2)

    @property
    def solde_base(self):
        # Produits - Charges
        return round(float(self.total_base_produits or 0) - float(self.total_base_lignes or 0), 2)

    @property
    def solde_reel(self):
        # Produits - Charges
        return round(float(self.total_reel_produits or 0) - float(self.total_reel_lignes or 0), 2)
    @property
    def total_engage(self):
        return round(sum(float(l.engage or 0) for l in self.lignes if getattr(l, "nature", "charge") == "charge"), 2)

    @property
    def total_reste(self):
        return round(sum(float(l.reste or 0) for l in self.lignes if getattr(l, "nature", "charge") == "charge"), 2)

    @property
    def total_impute_affectations(self):
        return round(sum(float(a.montant or 0) for a in self.depense_affectations if a.depense and not a.depense.est_supprimee), 2)

    @property
    def reste_imputable(self):
        base = float(self.montant_attribue or self.montant_recu or 0)
        if base <= 0:
            base = float(self.montant_demande or 0)
        return round(base - float(self.total_impute_affectations or 0), 2)


class LigneBudget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subvention_id = db.Column(db.Integer, db.ForeignKey("subvention.id"), nullable=False)

    # nature = charge (compte 6*) ou produit (compte 7*)
    nature = db.Column(db.String(10), nullable=False, default="charge")  # charge | produit

    compte = db.Column(db.String(20), nullable=False, default="60")
    libelle = db.Column(db.String(200), nullable=False)

    montant_base = db.Column(db.Float, default=0.0)
    montant_reel = db.Column(db.Float, default=0.0)

    created_at = db.Column(db.DateTime, default=utcnow)

    depenses = db.relationship("Depense", backref="budget_source", cascade="all, delete-orphan")
    depense_affectations = db.relationship("DepenseAffectation", back_populates="ligne_budget", cascade="all, delete-orphan")

    @property
    def engage(self):
        # engage / reste n'ont de sens que pour les CHARGES
        if getattr(self, "nature", "charge") != "charge":
            return 0.0

        # Nouveau modèle : on additionne les imputations rattachées à cette ligne.
        affecte = sum(
            float(a.montant or 0)
            for a in self.depense_affectations
            if a.depense and not a.depense.est_supprimee
        )

        # Compatibilité : les anciennes dépenses sans affectation explicite comptent encore à 100%.
        legacy = sum(
            float(d.montant or 0)
            for d in self.depenses
            if not d.est_supprimee and not getattr(d, "affectations", [])
        )
        return round(float(affecte or 0) + float(legacy or 0), 2)

    @property
    def reste(self):
        if getattr(self, "nature", "charge") != "charge":
            return 0.0
        return round(float(self.montant_reel or 0) - float(self.engage or 0), 2)


class Depense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ligne_budget_id = db.Column(db.Integer, db.ForeignKey("ligne_budget.id"), nullable=True)
    # Nouveau (AAP/Projets) : rattachement direct à une charge projet
    charge_projet_id = db.Column(db.Integer, db.ForeignKey("charge_projet.id", ondelete="SET NULL"), nullable=True)

    # Provenance facture / inventaire
    facture_ligne_id = db.Column(db.Integer, db.ForeignKey("facture_ligne.id", ondelete="SET NULL"), nullable=True)

    libelle = db.Column(db.String(255), nullable=False)
    montant = db.Column(db.Float, default=0.0)

    # infos finance-friendly (non obligatoires pour l’instant)
    fournisseur = db.Column(db.String(180), nullable=True)
    reference_piece = db.Column(db.String(120), nullable=True)  # n° facture / reçu / référence
    mode_paiement = db.Column(db.String(50), nullable=True)     # CB / Virement / Espèces / Autre

    date_paiement = db.Column(db.Date, nullable=True)
    type_depense = db.Column(db.String(80), default="Fonctionnement")

    # workflow / blindage
    statut = db.Column(db.String(30), nullable=False, default="valide")  # brouillon / valide
    anomalie = db.Column(db.String(255), nullable=True)
    est_supprimee = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=utcnow)

    documents = db.relationship("DepenseDocument", backref="depense", cascade="all, delete-orphan")
    affectations = db.relationship("DepenseAffectation", back_populates="depense", cascade="all, delete-orphan")
    inventaire_items = db.relationship("InventaireItem", backref="depense", passive_deletes=True)
    # relation SQLAlchemy (nécessaire pour back_populates depuis ChargeProjet)
    charge_projet = db.relationship("ChargeProjet", back_populates="depenses")

    @property
    def total_affecte(self):
        return round(sum(float(a.montant or 0) for a in self.affectations), 2)

    @property
    def reste_a_affecter(self):
        return round(float(self.montant or 0) - float(self.total_affecte or 0), 2)

    @property
    def statut_affectation(self):
        reste = float(self.reste_a_affecter or 0)
        if abs(reste) <= 0.01:
            return "ok"
        if reste > 0:
            return "partiel"
        return "depassement"


class DepenseAffectation(db.Model):
    __tablename__ = "depense_affectation"

    id = db.Column(db.Integer, primary_key=True)
    depense_id = db.Column(db.Integer, db.ForeignKey("depense.id", ondelete="CASCADE"), nullable=False, index=True)

    # source_type = subvention / fonds_propres / autre
    source_type = db.Column(db.String(30), nullable=False, default="subvention")
    subvention_id = db.Column(db.Integer, db.ForeignKey("subvention.id", ondelete="SET NULL"), nullable=True, index=True)
    ligne_budget_id = db.Column(db.Integer, db.ForeignKey("ligne_budget.id", ondelete="SET NULL"), nullable=True, index=True)

    libelle_source = db.Column(db.String(200), nullable=True)
    montant = db.Column(db.Float, nullable=False, default=0.0)
    commentaire = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    depense = db.relationship("Depense", back_populates="affectations")
    subvention = db.relationship("Subvention", back_populates="depense_affectations")
    ligne_budget = db.relationship("LigneBudget", back_populates="depense_affectations")

    @property
    def source_label(self):
        if self.source_type == "fonds_propres":
            return self.libelle_source or "Fonds propres"
        if self.subvention:
            return self.subvention.nom
        return self.libelle_source or "Source non renseignée"

    @property
    def ligne_label(self):
        if self.ligne_budget:
            return f"{self.ligne_budget.compte} — {self.ligne_budget.libelle}"
        return "—"


class DepenseDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    depense_id = db.Column(db.Integer, db.ForeignKey("depense.id"), nullable=False)

    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)

    uploaded_at = db.Column(db.DateTime, default=utcnow)


# ---------- FACTURES / INVENTAIRE ----------
class FactureAchat(db.Model):
    __tablename__ = "facture_achat"

    id = db.Column(db.Integer, primary_key=True)
    secteur_principal = db.Column(db.String(80), nullable=False)
    fournisseur = db.Column(db.String(180), nullable=True)
    reference_facture = db.Column(db.String(120), nullable=True)
    date_facture = db.Column(db.Date, nullable=True)

    statut = db.Column(db.String(30), nullable=False, default="brouillon")  # brouillon / valide

    filename = db.Column(db.String(255), nullable=True)
    original_name = db.Column(db.String(255), nullable=True)

    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    lignes = db.relationship("FactureLigne", backref="facture", cascade="all, delete-orphan")

    @property
    def total(self):
        return round(sum(float(l.montant_ligne or 0) for l in self.lignes), 2)


class FactureLigne(db.Model):
    __tablename__ = "facture_ligne"

    id = db.Column(db.Integer, primary_key=True)
    facture_id = db.Column(db.Integer, db.ForeignKey("facture_achat.id"), nullable=False)
    secteur = db.Column(db.String(80), nullable=False)

    financement_type = db.Column(db.String(30), nullable=False, default="subvention")  # subvention / fonds_propres / don / autre
    a_ventiler = db.Column(db.Boolean, default=False)

    libelle = db.Column(db.String(255), nullable=False)
    quantite = db.Column(db.Integer, nullable=False, default=1)
    prix_unitaire = db.Column(db.Float, default=0.0)
    montant_ligne = db.Column(db.Float, default=0.0)

    ligne_budget_id = db.Column(db.Integer, db.ForeignKey("ligne_budget.id"), nullable=True)
    # Nouveau (AAP/Projets) : rattachement direct à une charge projet
    charge_projet_id = db.Column(db.Integer, db.ForeignKey("charge_projet.id", ondelete="SET NULL"), nullable=True)
    subvention_id = db.Column(db.Integer, db.ForeignKey("subvention.id"), nullable=False)

    created_at = db.Column(db.DateTime, default=utcnow)

    depenses = db.relationship("Depense", backref="facture_ligne", passive_deletes=True)
    inventaire_items = db.relationship("InventaireItem", backref="facture_ligne", passive_deletes=True)


class InventaireItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    secteur = db.Column(db.String(80), nullable=False)
    id_interne = db.Column(db.String(64), nullable=False, unique=True)

    categorie = db.Column(db.String(120), nullable=True)
    designation = db.Column(db.String(255), nullable=False)
    marque = db.Column(db.String(120), nullable=True)
    modele = db.Column(db.String(120), nullable=True)

    quantite = db.Column(db.Integer, nullable=False, default=1)
    numero_serie = db.Column(db.String(180), nullable=True)
    etat = db.Column(db.String(50), nullable=False, default="OK")
    localisation = db.Column(db.String(255), nullable=True)

    valeur_unitaire = db.Column(db.Float, nullable=True)
    date_entree = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    facture_ligne_id = db.Column(db.Integer, db.ForeignKey("facture_ligne.id", ondelete="SET NULL"), nullable=True)
    depense_id = db.Column(db.Integer, db.ForeignKey("depense.id", ondelete="SET NULL"), nullable=True)

    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)


# ==========================================================
# ===============  ACTIVITÉ / ÉMARGEMENT  ==================
# ==========================================================

class Quartier(db.Model):
    __tablename__ = "quartier"
    id = db.Column(db.Integer, primary_key=True)
    ville = db.Column(db.String(80), nullable=False, default="Creil")
    nom = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_qpv = db.Column(db.Boolean, default=False)

    __table_args__ = (
        db.UniqueConstraint("ville", "nom", name="uq_quartier_ville_nom"),
    )


class Partenaire(db.Model):
    __tablename__ = "partenaire"
    id = db.Column(db.Integer, primary_key=True)

    nom = db.Column(db.String(180), nullable=False)
    contact_nom = db.Column(db.String(120), nullable=True)
    contact_prenom = db.Column(db.String(120), nullable=True)
    adresse = db.Column(db.String(255), nullable=True)

    email_contact = db.Column(db.String(180), nullable=True)
    email_general = db.Column(db.String(180), nullable=True)
    tel_contact = db.Column(db.String(60), nullable=True)
    tel_general = db.Column(db.String(60), nullable=True)

    description = db.Column(db.Text, nullable=True)
    competences_orientation_json = db.Column(db.Text, nullable=True)
    territoire_couvert = db.Column(db.Text, nullable=True)
    modalites_orientation = db.Column(db.Text, nullable=True)
    niveau_orientation = db.Column(db.String(40), nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    secteurs = db.relationship("PartenaireSecteur", backref="partenaire", cascade="all, delete-orphan")
    interventions = db.relationship(
        "PartenaireIntervention",
        backref="partenaire",
        cascade="all, delete-orphan",
        order_by="desc(PartenaireIntervention.date_intervention)",
    )
    orientations = db.relationship("OrientationAccesDroit", back_populates="partenaire", passive_deletes=True)

    def competences_orientation(self):
        try:
            raw = json.loads(self.competences_orientation_json or "[]")
        except Exception:
            raw = []
        return [str(item).strip() for item in raw if str(item or "").strip()]


class PartenaireSecteur(db.Model):
    __tablename__ = "partenaire_secteur"
    id = db.Column(db.Integer, primary_key=True)
    partenaire_id = db.Column(db.Integer, db.ForeignKey("partenaire.id", ondelete="CASCADE"), nullable=False)
    secteur = db.Column(db.String(80), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("partenaire_id", "secteur", name="uq_partenaire_secteur"),
    )


class PartenaireIntervention(db.Model):
    __tablename__ = "partenaire_intervention"
    id = db.Column(db.Integer, primary_key=True)
    partenaire_id = db.Column(db.Integer, db.ForeignKey("partenaire.id", ondelete="CASCADE"), nullable=False)
    secteur = db.Column(db.String(80), nullable=True)
    date_intervention = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)


class OrientationAccesDroit(db.Model):
    __tablename__ = "orientation_acces_droit"

    id = db.Column(db.Integer, primary_key=True)
    date_orientation = db.Column(db.Date, nullable=False, default=date.today, index=True)
    secteur = db.Column(db.String(80), nullable=True, index=True)
    ville = db.Column(db.String(120), nullable=True, index=True)
    domaine = db.Column(db.String(80), nullable=False, index=True)
    demande = db.Column(db.String(255), nullable=False)
    statut = db.Column(db.String(40), nullable=False, default="oriente", index=True)
    urgence = db.Column(db.String(30), nullable=False, default="normale", index=True)
    suite_prevue = db.Column(db.Date, nullable=True, index=True)
    note = db.Column(db.Text, nullable=True)
    demandeur_libre = db.Column(db.String(180), nullable=True)

    participant_id = db.Column(db.Integer, db.ForeignKey("participant.id", ondelete="SET NULL"), nullable=True, index=True)
    partenaire_id = db.Column(db.Integer, db.ForeignKey("partenaire.id", ondelete="SET NULL"), nullable=True, index=True)
    quartier_id = db.Column(db.Integer, db.ForeignKey("quartier.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    participant = db.relationship("Participant", backref=db.backref("orientations_acces_droit", lazy="dynamic"))
    partenaire = db.relationship("Partenaire", back_populates="orientations")
    quartier = db.relationship("Quartier")
    user = db.relationship("User")


class SuiviRappel(db.Model):
    __tablename__ = "suivi_rappel"

    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    categorie = db.Column(db.String(40), nullable=False, default="general", index=True)
    priorite = db.Column(db.String(20), nullable=False, default="warn", index=True)
    statut = db.Column(db.String(20), nullable=False, default="ouvert", index=True)
    secteur = db.Column(db.String(80), nullable=True, index=True)
    echeance = db.Column(db.Date, nullable=True, index=True)
    lien_url = db.Column(db.String(500), nullable=True)
    is_private = db.Column(db.Boolean, default=False, nullable=False, index=True)

    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True)
    done_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    user = db.relationship("User")


class Questionnaire(db.Model):
    __tablename__ = "questionnaire"
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    secteurs = db.relationship("QuestionnaireSecteur", backref="questionnaire", cascade="all, delete-orphan")
    ateliers = db.relationship("QuestionnaireAtelier", backref="questionnaire", cascade="all, delete-orphan")
    questions = db.relationship("Question", backref="questionnaire", cascade="all, delete-orphan")
    response_groups = db.relationship("QuestionnaireResponseGroup", backref="questionnaire", cascade="all, delete-orphan")


class QuestionnaireSecteur(db.Model):
    __tablename__ = "questionnaire_secteur"
    id = db.Column(db.Integer, primary_key=True)
    questionnaire_id = db.Column(db.Integer, db.ForeignKey("questionnaire.id", ondelete="CASCADE"), nullable=False)
    secteur = db.Column(db.String(80), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("questionnaire_id", "secteur", name="uq_questionnaire_secteur"),
    )


class QuestionnaireAtelier(db.Model):
    __tablename__ = "questionnaire_atelier"
    id = db.Column(db.Integer, primary_key=True)
    questionnaire_id = db.Column(db.Integer, db.ForeignKey("questionnaire.id", ondelete="CASCADE"), nullable=False)
    atelier_id = db.Column(db.Integer, db.ForeignKey("atelier_activite.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("questionnaire_id", "atelier_id", name="uq_questionnaire_atelier"),
    )


class Question(db.Model):
    __tablename__ = "question"
    id = db.Column(db.Integer, primary_key=True)
    questionnaire_id = db.Column(db.Integer, db.ForeignKey("questionnaire.id", ondelete="CASCADE"), nullable=False)
    label = db.Column(db.String(255), nullable=False)
    kind = db.Column(db.String(30), nullable=False, default="text")  # scale/yesno/multi/text
    is_required = db.Column(db.Boolean, default=False)
    position = db.Column(db.Integer, nullable=False, default=0)
    options_json = db.Column(db.Text, nullable=True)

    responses = db.relationship("QuestionResponse", backref="question", cascade="all, delete-orphan")


class QuestionnaireResponseGroup(db.Model):
    __tablename__ = "questionnaire_response_group"
    id = db.Column(db.Integer, primary_key=True)
    questionnaire_id = db.Column(db.Integer, db.ForeignKey("questionnaire.id", ondelete="CASCADE"), nullable=False)
    participant_id = db.Column(db.Integer, db.ForeignKey("participant.id"), nullable=True)
    session_id = db.Column(db.Integer, db.ForeignKey("session_activite.id"), nullable=True)
    atelier_id = db.Column(db.Integer, db.ForeignKey("atelier_activite.id"), nullable=True)
    secteur = db.Column(db.String(80), nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    participant = db.relationship("Participant")
    session = db.relationship("SessionActivite")
    atelier = db.relationship("AtelierActivite")


class QuestionResponse(db.Model):
    __tablename__ = "question_response"
    id = db.Column(db.Integer, primary_key=True)
    response_group_id = db.Column(
        db.Integer,
        db.ForeignKey("questionnaire_response_group.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id = db.Column(db.Integer, db.ForeignKey("question.id", ondelete="CASCADE"), nullable=False)
    value_text = db.Column(db.Text, nullable=True)
    value_number = db.Column(db.Float, nullable=True)
    value_json = db.Column(db.Text, nullable=True)

    response_group = db.relationship("QuestionnaireResponseGroup")


class Participant(db.Model):
    __tablename__ = "participant"
    id = db.Column(db.Integer, primary_key=True)

    nom = db.Column(db.String(120), nullable=False)
    prenom = db.Column(db.String(120), nullable=False)
    adresse = db.Column(db.String(255), nullable=True)
    ville = db.Column(db.String(120), nullable=True)
    email = db.Column(db.String(180), nullable=True)
    telephone = db.Column(db.String(60), nullable=True)
    genre = db.Column(db.String(20), nullable=True)
    date_naissance = db.Column(db.Date, nullable=True)
    # Champs legacy insertion : conservés temporairement pour migration douce.
    # La source cible doit désormais vivre dans les tables dédiées du module insertion.
    pays_origine = db.Column(db.String(120), nullable=True)
    titre_sejour_type = db.Column(db.String(120), nullable=True)
    date_entree_dispositif = db.Column(db.Date, nullable=True)
    date_sortie_dispositif = db.Column(db.Date, nullable=True)
    diplome_obtenu = db.Column(db.String(180), nullable=True)
    cir_obtenu = db.Column(db.Boolean, nullable=True)

    # Type de public (ex: H/S/B/A/P). Par défaut: H
    type_public = db.Column(db.String(2), nullable=False, default="H")

    quartier_id = db.Column(db.Integer, db.ForeignKey("quartier.id"), nullable=True)
    quartier = db.relationship("Quartier")

    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    # Pour permettre la création "en avance" (avant toute présence) tout en respectant
    # le cloisonnement par secteur en rôle responsable_secteur.
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_secteur = db.Column(db.String(80), nullable=True)

    @property
    def is_creil(self):
        return (self.ville or "").strip().lower() == "creil"

    @property
    def is_qpv(self):
        if not self.quartier:
            return False
        if self.quartier.is_qpv:
            return True
        ville = (self.quartier.ville or "").strip().lower()
        nom = (self.quartier.nom or "").strip().lower()
        if "qpv" in nom:
            return True
        if ville == "creil" and ("rouher" in nom or "hauts de creil" in nom):
            return True
        return False

    @property
    def age(self):
        if not self.date_naissance:
            return None
        today = date.today()
        years = today.year - self.date_naissance.year
        if (today.month, today.day) < (self.date_naissance.month, self.date_naissance.day):
            years -= 1
        return years

    @property
    def current_insertion_parcours(self):
        today = date.today()
        rows = sorted(
            list(getattr(self, "insertion_parcours", []) or []),
            key=lambda row: ((row.date_entree or date.min), row.id or 0),
            reverse=True,
        )
        for row in rows:
            start_ok = row.date_entree is None or row.date_entree <= today
            end_ok = row.date_sortie is None or row.date_sortie >= today
            if start_ok and end_ok:
                return row
        return rows[0] if rows else None


    @property
    def current_insertion_positionnement(self):
        rows = sorted(
            list(getattr(self, "insertion_positionnements", []) or []),
            key=lambda row: ((row.date_positionnement or date.min), row.id or 0),
            reverse=True,
        )
        return rows[0] if rows else None


class InsertionDispositifRef(db.Model):
    __tablename__ = "insertion_dispositif_ref"
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(180), nullable=False, unique=True, index=True)
    code = db.Column(db.String(80), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    def __repr__(self) -> str:
        return f"<InsertionDispositifRef {self.label}>"


class InsertionPrescripteurRef(db.Model):
    __tablename__ = "insertion_prescripteur_ref"
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(180), nullable=False, unique=True, index=True)
    code = db.Column(db.String(80), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    def __repr__(self) -> str:
        return f"<InsertionPrescripteurRef {self.label}>"


class InsertionTitreSejourTypeRef(db.Model):
    __tablename__ = "insertion_titre_sejour_type_ref"
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(180), nullable=False, unique=True, index=True)
    code = db.Column(db.String(80), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    def __repr__(self) -> str:
        return f"<InsertionTitreSejourTypeRef {self.label}>"


class InsertionDiplomeRef(db.Model):
    __tablename__ = "insertion_diplome_ref"
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(180), nullable=False, unique=True, index=True)
    code = db.Column(db.String(80), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    def __repr__(self) -> str:
        return f"<InsertionDiplomeRef {self.label}>"


class InsertionNiveauRef(db.Model):
    __tablename__ = "insertion_niveau_ref"
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(180), nullable=False, unique=True, index=True)
    code = db.Column(db.String(80), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    def __repr__(self) -> str:
        return f"<InsertionNiveauRef {self.label}>"


class ParticipantInsertionProfile(db.Model):
    __tablename__ = "participant_insertion_profile"
    participant_id = db.Column(db.Integer, db.ForeignKey("participant.id", ondelete="CASCADE"), primary_key=True)
    pays_origine = db.Column(db.String(120), nullable=True)
    cir_obtenu = db.Column(db.Boolean, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    updated_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    participant = db.relationship(
        "Participant",
        backref=db.backref("insertion_profile", uselist=False, cascade="all, delete-orphan", passive_deletes=True),
    )
    created_by = db.relationship("User", foreign_keys=[created_by_user_id])
    updated_by = db.relationship("User", foreign_keys=[updated_by_user_id])


class ParticipantInsertionParcours(db.Model):
    __tablename__ = "participant_insertion_parcours"
    id = db.Column(db.Integer, primary_key=True)
    participant_id = db.Column(db.Integer, db.ForeignKey("participant.id", ondelete="CASCADE"), nullable=False, index=True)
    dispositif_id = db.Column(db.Integer, db.ForeignKey("insertion_dispositif_ref.id"), nullable=True)
    prescripteur_id = db.Column(db.Integer, db.ForeignKey("insertion_prescripteur_ref.id"), nullable=True)
    titre_sejour_type_id = db.Column(db.Integer, db.ForeignKey("insertion_titre_sejour_type_ref.id"), nullable=True)
    date_debut_titre_sejour = db.Column(db.Date, nullable=True)
    date_expiration_titre_sejour = db.Column(db.Date, nullable=True)
    date_entree = db.Column(db.Date, nullable=True)
    date_sortie = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    legacy_source = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    updated_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    participant = db.relationship(
        "Participant",
        backref=db.backref("insertion_parcours", cascade="all, delete-orphan", passive_deletes=True),
    )
    dispositif = db.relationship("InsertionDispositifRef", backref=db.backref("parcours", lazy=True))
    prescripteur = db.relationship("InsertionPrescripteurRef", backref=db.backref("parcours", lazy=True))
    titre_sejour_type = db.relationship("InsertionTitreSejourTypeRef", backref=db.backref("parcours", lazy=True))
    created_by = db.relationship("User", foreign_keys=[created_by_user_id])
    updated_by = db.relationship("User", foreign_keys=[updated_by_user_id])


class ParticipantInsertionPositionnement(db.Model):
    __tablename__ = "participant_insertion_positionnement"
    id = db.Column(db.Integer, primary_key=True)
    participant_id = db.Column(db.Integer, db.ForeignKey("participant.id", ondelete="CASCADE"), nullable=False, index=True)
    parcours_id = db.Column(db.Integer, db.ForeignKey("participant_insertion_parcours.id", ondelete="SET NULL"), nullable=True, index=True)
    niveau_id = db.Column(db.Integer, db.ForeignKey("insertion_niveau_ref.id"), nullable=True)
    date_positionnement = db.Column(db.Date, nullable=True)
    type_positionnement = db.Column(db.String(32), nullable=False, default="entree")
    commentaire = db.Column(db.Text, nullable=True)
    legacy_source = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    updated_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    participant = db.relationship(
        "Participant",
        backref=db.backref("insertion_positionnements", cascade="all, delete-orphan", passive_deletes=True),
    )
    parcours = db.relationship("ParticipantInsertionParcours", backref=db.backref("positionnements", lazy=True))
    niveau = db.relationship("InsertionNiveauRef", backref=db.backref("positionnements", lazy=True))
    created_by = db.relationship("User", foreign_keys=[created_by_user_id])
    updated_by = db.relationship("User", foreign_keys=[updated_by_user_id])


class ParticipantInsertionCertification(db.Model):
    __tablename__ = "participant_insertion_certification"
    id = db.Column(db.Integer, primary_key=True)
    participant_id = db.Column(db.Integer, db.ForeignKey("participant.id", ondelete="CASCADE"), nullable=False, index=True)
    parcours_id = db.Column(db.Integer, db.ForeignKey("participant_insertion_parcours.id", ondelete="SET NULL"), nullable=True, index=True)
    diplome_id = db.Column(db.Integer, db.ForeignKey("insertion_diplome_ref.id"), nullable=True)
    niveau_id = db.Column(db.Integer, db.ForeignKey("insertion_niveau_ref.id"), nullable=True)
    date_passage = db.Column(db.Date, nullable=True)
    date_obtention = db.Column(db.Date, nullable=True)
    resultat = db.Column(db.String(32), nullable=True)
    commentaire = db.Column(db.Text, nullable=True)
    legacy_source = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    updated_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    participant = db.relationship(
        "Participant",
        backref=db.backref("insertion_certifications", cascade="all, delete-orphan", passive_deletes=True),
    )
    parcours = db.relationship("ParticipantInsertionParcours", backref=db.backref("certifications", lazy=True))
    diplome = db.relationship("InsertionDiplomeRef", backref=db.backref("certifications", lazy=True))
    niveau = db.relationship("InsertionNiveauRef", backref=db.backref("certifications", lazy=True))
    created_by = db.relationship("User", foreign_keys=[created_by_user_id])
    updated_by = db.relationship("User", foreign_keys=[updated_by_user_id])


class AtelierActivite(db.Model):
    __tablename__ = "atelier_activite"
    id = db.Column(db.Integer, primary_key=True)
    secteur = db.Column(db.String(80), nullable=False, index=True)
    nom = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    type_atelier = db.Column(db.String(30), nullable=False, default="COLLECTIF")
    # COLLECTIF: nb places. INDIVIDUEL_MENSUEL: heures dispo / mois.
    capacite_defaut = db.Column(db.Integer, nullable=True)
    heures_dispo_defaut_mois = db.Column(db.Float, nullable=True)
    duree_defaut_minutes = db.Column(db.Integer, nullable=True)

    motifs_json = db.Column(db.Text, nullable=True)  # liste JSON de motifs (dropdown)

    modele_docx_collectif = db.Column(db.String(255), nullable=True)
    modele_docx_individuel = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow)

    # Statut métier + soft-delete
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False, index=True)
    deleted_at = db.Column(db.DateTime, nullable=True)

    # Continuité statistique (ex: atelier renommé d'une année à l'autre)
    continuity_parent_id = db.Column(db.Integer, db.ForeignKey("atelier_activite.id"), nullable=True, index=True)
    continuity_parent = db.relationship(
        "AtelierActivite",
        remote_side=[id],
        foreign_keys=[continuity_parent_id],
        post_update=True,
        backref=db.backref("continuity_children", lazy="dynamic"),
    )

    sessions = db.relationship("SessionActivite", backref="atelier", cascade="all, delete-orphan")
    competences = db.relationship(
        "Competence",
        secondary=atelier_competence,
        backref=db.backref("ateliers", lazy="dynamic"),
    )
    modules = db.relationship(
        "PedagogieModule",
        secondary=atelier_module,
        backref=db.backref("ateliers", lazy="dynamic"),
    )

    def motifs(self):
        try:
            return json.loads(self.motifs_json or "[]")
        except Exception:
            return []


class SessionActivite(db.Model):
    __tablename__ = "session_activite"
    id = db.Column(db.Integer, primary_key=True)
    atelier_id = db.Column(db.Integer, db.ForeignKey("atelier_activite.id"), nullable=False)
    secteur = db.Column(db.String(80), nullable=False, index=True)
    session_type = db.Column(db.String(30), nullable=False, default="COLLECTIF")
    # COLLECTIF
    date_session = db.Column(db.Date, nullable=True, index=True)
    heure_debut = db.Column(db.String(10), nullable=True)
    heure_fin = db.Column(db.String(10), nullable=True)
    capacite = db.Column(db.Integer, nullable=True)
    statut = db.Column(db.String(20), nullable=False, default="realisee")  # realisee / annulee

    # INDIVIDUEL_MENSUEL (rdv)
    rdv_date = db.Column(db.Date, nullable=True, index=True)
    rdv_debut = db.Column(db.String(10), nullable=True)
    rdv_fin = db.Column(db.String(10), nullable=True)
    duree_minutes = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow)
    consommation_config_id = db.Column(
        db.Integer,
        db.ForeignKey("materiel_consommation_config.id"),
        nullable=True,
        index=True,
    )

    # Soft-delete (safe during tests)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False, index=True)
    deleted_at = db.Column(db.DateTime, nullable=True)

    # KIOSQUE (public) : émargement via /kiosk sans exposer l'app complète
    kiosk_open = db.Column(db.Boolean, default=False, index=True)
    kiosk_pin = db.Column(db.String(10), nullable=True, index=True)
    kiosk_token = db.Column(db.String(64), nullable=True, index=True)
    kiosk_opened_at = db.Column(db.DateTime, nullable=True)

    presences = db.relationship("PresenceActivite", backref="session", cascade="all, delete-orphan")
    competences = db.relationship(
        "Competence",
        secondary=session_competence,
        backref=db.backref("sessions", lazy="dynamic"),
    )
    modules = db.relationship(
        "PedagogieModule",
        secondary=session_module,
        backref=db.backref("sessions", lazy="dynamic"),
    )
    materiels = db.relationship("SessionMateriel", backref="session", cascade="all, delete-orphan")
    consommation_config = db.relationship(
        "MaterielConsommationConfig",
        backref="sessions",
        lazy="joined",
    )

    @property
    def date_reference(self):
        return self.rdv_date or self.date_session

    @property
    def duree_heures(self):
        if self.duree_minutes:
            return self.duree_minutes / 60

        if self.heure_debut and self.heure_fin:
            try:
                h1, m1 = map(int, self.heure_debut.split(":"))
                h2, m2 = map(int, self.heure_fin.split(":"))
                return ((h2 * 60 + m2) - (h1 * 60 + m1)) / 60
            except Exception:
                return 1

        return 1


class MaterielType(db.Model):
    __tablename__ = "materiel_type"
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    actif = db.Column(db.Boolean, default=True, nullable=False)
    ordre = db.Column(db.Integer, default=0, nullable=False)


class MaterielConsommationConfig(db.Model):
    __tablename__ = "materiel_consommation_config"
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(120), nullable=False)
    date_debut = db.Column(db.Date, nullable=False, index=True)
    date_fin = db.Column(db.Date, nullable=True, index=True)
    co2_kg_par_kwh = db.Column(db.Float, nullable=False, default=0.06)
    actif = db.Column(db.Boolean, default=True, nullable=False, index=True)
    notes = db.Column(db.Text, nullable=True)
    lignes = db.relationship("MaterielConsommationLigne", backref="config", cascade="all, delete-orphan")


class MaterielConsommationLigne(db.Model):
    __tablename__ = "materiel_consommation_ligne"
    id = db.Column(db.Integer, primary_key=True)
    config_id = db.Column(db.Integer, db.ForeignKey("materiel_consommation_config.id"), nullable=False, index=True)
    materiel_id = db.Column(db.Integer, db.ForeignKey("materiel_type.id"), nullable=False, index=True)
    watts = db.Column(db.Float, nullable=False, default=0.0)
    materiel = db.relationship("MaterielType")


class SessionMateriel(db.Model):
    __tablename__ = "session_materiel"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("session_activite.id"), nullable=False, index=True)
    materiel_id = db.Column(db.Integer, db.ForeignKey("materiel_type.id"), nullable=False, index=True)
    quantite = db.Column(db.Integer, nullable=False, default=1)
    materiel = db.relationship("MaterielType")


class SessionScheduleEditLog(db.Model):
    __tablename__ = "session_schedule_edit_log"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("session_activite.id", ondelete="CASCADE"), nullable=False, index=True)
    atelier_id = db.Column(db.Integer, db.ForeignKey("atelier_activite.id", ondelete="SET NULL"), nullable=True, index=True)
    secteur = db.Column(db.String(80), nullable=True, index=True)

    old_date = db.Column(db.Date, nullable=True)
    old_start = db.Column(db.String(10), nullable=True)
    old_end = db.Column(db.String(10), nullable=True)

    new_date = db.Column(db.Date, nullable=True)
    new_start = db.Column(db.String(10), nullable=True)
    new_end = db.Column(db.String(10), nullable=True)

    reason = db.Column(db.Text, nullable=False)
    edited_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    edited_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    session = db.relationship("SessionActivite")
    atelier = db.relationship("AtelierActivite")
    editor = db.relationship("User")

class AtelierCapaciteMois(db.Model):
    __tablename__ = "atelier_capacite_mois"
    id = db.Column(db.Integer, primary_key=True)
    atelier_id = db.Column(db.Integer, db.ForeignKey("atelier_activite.id"), nullable=False)
    annee = db.Column(db.Integer, nullable=False)
    mois = db.Column(db.Integer, nullable=False)
    heures_dispo = db.Column(db.Float, nullable=False, default=0.0)
    locked = db.Column(db.Boolean, default=False)

    __table_args__ = (
        db.UniqueConstraint("atelier_id", "annee", "mois", name="uq_atelier_capacite_mois"),
    )


class PresenceActivite(db.Model):
    __tablename__ = "presence_activite"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("session_activite.id"), nullable=False)
    participant_id = db.Column(db.Integer, db.ForeignKey("participant.id"), nullable=False)
    participant = db.relationship("Participant")
    consommations_materiel = db.relationship(
        "PresenceMaterielConsommation",
        backref="presence",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Motif (liste + autre)
    motif = db.Column(db.String(180), nullable=True)
    motif_autre = db.Column(db.String(255), nullable=True)

    # signature: stockée en fichier (temp), ici juste le chemin
    signature_path = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow)

    __table_args__ = (
        db.UniqueConstraint("session_id", "participant_id", name="uq_presence_session_participant"),
    )


class PresenceMaterielConsommation(db.Model):
    """Consommation individuelle figée pour une présence.

    Le référentiel matériel peut évoluer dans le temps. Les watts, la durée,
    les kWh et le CO2 sont donc copiés au moment du calcul pour que les
    anciennes feuilles d'émargement ne changent pas rétroactivement.
    """

    __tablename__ = "presence_materiel_consommation"

    id = db.Column(db.Integer, primary_key=True)
    presence_id = db.Column(db.Integer, db.ForeignKey("presence_activite.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = db.Column(db.Integer, db.ForeignKey("session_activite.id", ondelete="CASCADE"), nullable=False, index=True)
    participant_id = db.Column(db.Integer, db.ForeignKey("participant.id", ondelete="CASCADE"), nullable=False, index=True)
    materiel_id = db.Column(db.Integer, db.ForeignKey("materiel_type.id", ondelete="SET NULL"), nullable=True, index=True)

    quantite = db.Column(db.Integer, nullable=False, default=1)
    materiel_nom_snapshot = db.Column(db.String(120), nullable=True)
    watts_snapshot = db.Column(db.Float, nullable=False, default=0.0)
    duree_minutes_snapshot = db.Column(db.Integer, nullable=False, default=60)
    kwh_snapshot = db.Column(db.Float, nullable=False, default=0.0)
    co2_kg_snapshot = db.Column(db.Float, nullable=False, default=0.0)
    co2_kg_par_kwh_snapshot = db.Column(db.Float, nullable=False, default=0.06)
    mode_calcul = db.Column(db.String(40), nullable=False, default="manuel")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    materiel = db.relationship("MaterielType")
    session = db.relationship("SessionActivite")
    participant = db.relationship("Participant")

    __table_args__ = (
        db.UniqueConstraint("presence_id", "materiel_id", "mode_calcul", name="uq_presence_materiel_conso_ligne"),
    )


class Evaluation(db.Model):
    __tablename__ = "evaluation"
    id = db.Column(db.Integer, primary_key=True)
    participant_id = db.Column(db.Integer, db.ForeignKey("participant.id"), nullable=False)
    competence_id = db.Column(db.Integer, db.ForeignKey("competence.id"), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey("session_activite.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    etat = db.Column(db.Integer, nullable=False, default=0)  # 0=Non acquis, 1=En cours, 2=Acquis, 3=Expert
    date_evaluation = db.Column(db.Date, nullable=False, default=date.today)
    commentaire = db.Column(db.Text, nullable=True)

    participant = db.relationship("Participant")
    competence = db.relationship("Competence")
    session = db.relationship("SessionActivite")
    user = db.relationship("User")

    __table_args__ = (
        db.UniqueConstraint("participant_id", "competence_id", "session_id", name="uq_eval_participant_competence_session"),
    )


class PasseportNote(db.Model):
    __tablename__ = "passeport_note"

    id = db.Column(db.Integer, primary_key=True)
    participant_id = db.Column(db.Integer, db.ForeignKey("participant.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = db.Column(db.Integer, db.ForeignKey("session_activite.id", ondelete="SET NULL"), nullable=True, index=True)
    secteur = db.Column(db.String(80), nullable=True, index=True)
    categorie = db.Column(db.String(60), nullable=False, default="journal", index=True)
    contenu = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, index=True)

    participant = db.relationship("Participant")
    session = db.relationship("SessionActivite")
    user = db.relationship("User")


class PasseportPieceJointe(db.Model):
    __tablename__ = "passeport_piece_jointe"

    id = db.Column(db.Integer, primary_key=True)
    participant_id = db.Column(db.Integer, db.ForeignKey("participant.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = db.Column(db.Integer, db.ForeignKey("session_activite.id", ondelete="SET NULL"), nullable=True, index=True)
    secteur = db.Column(db.String(80), nullable=True, index=True)
    categorie = db.Column(db.String(60), nullable=False, default="atelier", index=True)
    titre = db.Column(db.String(255), nullable=True)
    file_path = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(120), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, index=True)

    participant = db.relationship("Participant")
    session = db.relationship("SessionActivite")
    user = db.relationship("User")


class ObjectifSuivi(db.Model):
    __tablename__ = "objectif_suivi"

    id = db.Column(db.Integer, primary_key=True)
    objectif_id = db.Column(db.Integer, db.ForeignKey("objectif.id"), nullable=False, index=True)
    session_id = db.Column(db.Integer, db.ForeignKey("session_activite.id"), nullable=False, index=True)
    participant_id = db.Column(db.Integer, db.ForeignKey("participant.id"), nullable=True, index=True)

    mode = db.Column(db.String(20), nullable=False, default="ressenti")  # ressenti | competence | mixte
    etat = db.Column(db.Integer, nullable=False, default=1)  # 0=non atteint,1=en progression,2=atteint,3=depasse
    ressenti = db.Column(db.Integer, nullable=True)  # 1..5 (optionnel)
    commentaire = db.Column(db.Text, nullable=True)

    date_saisie = db.Column(db.Date, nullable=False, default=date.today, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    objectif = db.relationship("Objectif")
    session = db.relationship("SessionActivite")
    participant = db.relationship("Participant")
    user = db.relationship("User")


class ArchiveEmargement(db.Model):
    __tablename__ = "archive_emargement"
    id = db.Column(db.Integer, primary_key=True)
    secteur = db.Column(db.String(80), nullable=False, index=True)
    atelier_id = db.Column(db.Integer, db.ForeignKey("atelier_activite.id"), nullable=False)
    atelier = db.relationship("AtelierActivite")
    # pour collectif : session_id ; pour individuel mensuel : null
    session_id = db.Column(db.Integer, db.ForeignKey("session_activite.id"), nullable=True)
    annee = db.Column(db.Integer, nullable=False)
    mois = db.Column(db.Integer, nullable=True)

    docx_path = db.Column(db.String(255), nullable=True)
    pdf_path = db.Column(db.String(255), nullable=True)

    # Option : version corrigée manuellement (upload après édition Word)
    corrected_docx_path = db.Column(db.String(255), nullable=True)
    corrected_pdf_path = db.Column(db.String(255), nullable=True)

    # Suivi envoi mail
    last_emailed_to = db.Column(db.String(255), nullable=True)
    last_emailed_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="open")  # open/locked
    created_at = db.Column(db.DateTime, default=utcnow)



class PeriodeFinancement(db.Model):
    """Périodes enregistrées (souvent calées sur un financeur) pour filtrer les stats.

    - sectorisée : une période peut être rattachée à un secteur (ou globale si secteur=None)
    - RGPD : ne contient pas de données personnelles
    """
    __tablename__ = "periode_financement"
    id = db.Column(db.Integer, primary_key=True)
    secteur = db.Column(db.String(80), nullable=True, index=True)  # None = global
    nom = db.Column(db.String(255), nullable=False)
    date_debut = db.Column(db.Date, nullable=False, index=True)
    date_fin = db.Column(db.Date, nullable=False, index=True)

    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False, index=True)

    def __repr__(self):
        return f"<PeriodeFinancement {self.id} {self.nom} {self.date_debut}..{self.date_fin} secteur={self.secteur}>"


class BilanLourdNarratif(db.Model):
    __tablename__ = "bilan_lourd_narratif"

    id = db.Column(db.Integer, primary_key=True)
    annee = db.Column(db.Integer, nullable=False, index=True)
    secteur = db.Column(db.String(80), nullable=False, index=True)

    faits_marquants = db.Column(db.Text, nullable=True)
    difficultes = db.Column(db.Text, nullable=True)
    perspectives = db.Column(db.Text, nullable=True)
    photos_json = db.Column(db.Text, nullable=True)
    timeline_json = db.Column(db.Text, nullable=True)

    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    updated_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        db.UniqueConstraint("annee", "secteur", name="uq_bilan_lourd_narratif_annee_secteur"),
    )

# ---------------------------------------------------------------------
# RBAC COMPAT: provide User.role property
# ---------------------------------------------------------------------
# Depuis l'introduction du RBAC (User.roles), certaines branches/test DB
# peuvent ne plus avoir la colonne legacy `User.role`. Or beaucoup de routes
# utilisent encore `current_user.role`.
#
# Objectif: éviter les 500/AttributeError en fournissant un fallback READ-ONLY
# (et une compat "directrice" vs "direction") tant que la migration complète
# n'est pas terminée.
#
# IMPORTANT: on n'écrase PAS un attribut SQLAlchemy existant. On ne crée ce
# fallback QUE si `User.role` n'existe pas déjà.
# ---------------------------------------------------------------------

def _role_compat_get(u) -> str:
    # 1) si une colonne legacy existe (cas ancien), on la privilégie
    legacy = getattr(u, "__dict__", {}).get("role", None)
    if legacy:
        return legacy

    # 2) sinon, on dérive depuis RBAC: premier rôle, sinon responsable_secteur
    codes = []
    try:
        codes = [r.code for r in (getattr(u, "roles", []) or []) if getattr(r, "code", None)]
    except Exception:
        codes = []
    code = (codes[0] if codes else "responsable_secteur")

    # 3) compat historique : certaines routes comparent à "directrice"
    mapping = {
        "direction": "directrice",
    }
    return mapping.get(code, code)

def _role_compat_set(u, value: str):
    # Si la colonne legacy n'existe pas, on ignore (fallback read-only).
    try:
        if "role" in getattr(u, "__dict__", {}):
            u.__dict__["role"] = value
    except Exception:
        pass

try:
    # Ne créer la propriété QUE si SQLAlchemy n'a pas déjà mappé `role`
    if not hasattr(User, "role"):
        User.role = property(_role_compat_get, _role_compat_set)  # type: ignore[attr-defined]
except Exception:
    # On ne doit jamais empêcher l'app de démarrer pour un souci de compat.
    pass


# ---------------------------------------------------------------------------
# Référentiels de compétences (DigComp / Pix / CléA, etc.) + projets pédagogiques
# ---------------------------------------------------------------------------
#
# Objectif:
# - Importer des référentiels une seule fois (pas de saisie manuelle)
# - Lier les ateliers à plusieurs projets (Option B)
# - Tagger les compétences au niveau SESSION (ex: "Créer un mail") plutôt qu'au
#   niveau atelier large (ex: "Numérique par tous")
# - Évaluer par session de façon légère (NA / EN_COURS / ACQUIS)
#
# IMPORTANT : le passeport des habitants (PasseportNote / PasseportPieceJointe)
# reste INCHANGÉ et non négociable. Les tables ci-dessous n'écrasent rien et
# pourront ensuite alimenter le passeport via un pont/export.


class Framework(db.Model):
    __tablename__ = "framework"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False, index=True)
    nom = db.Column(db.String(160), nullable=False)
    version = db.Column(db.String(32), nullable=True)
    lang = db.Column(db.String(8), nullable=True, default="fr")
    source_url = db.Column(db.String(512), nullable=True)
    actif = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    skills = db.relationship("Skill", backref="framework", lazy=True)

    def __repr__(self):
        return f"<Framework {self.code} {self.version or ''}>"


class Skill(db.Model):
    __tablename__ = "skill"
    __table_args__ = (
        db.UniqueConstraint("framework_id", "code", name="uq_skill_framework_code"),
    )

    id = db.Column(db.Integer, primary_key=True)
    framework_id = db.Column(db.Integer, db.ForeignKey("framework.id"), nullable=False, index=True)
    code = db.Column(db.String(64), nullable=False, index=True)
    label = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    domain_code = db.Column(db.String(32), nullable=True, index=True)
    domain_label = db.Column(db.String(255), nullable=True)
    sort_order = db.Column(db.Integer, nullable=True)
    actif = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    def __repr__(self):
        return f"<Skill {self.framework_id}:{self.code}>"


class LearningProject(db.Model):
    __tablename__ = "learning_project"

    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    date_debut = db.Column(db.Date, nullable=True)
    date_fin = db.Column(db.Date, nullable=True)
    public_cible = db.Column(db.String(255), nullable=True)
    framework_id_default = db.Column(db.Integer, db.ForeignKey("framework.id"), nullable=True, index=True)
    seuil_reussite = db.Column(db.Float, nullable=False, default=0.6)
    actif = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)

    framework_default = db.relationship("Framework", foreign_keys=[framework_id_default])
    created_by = db.relationship("User", foreign_keys=[created_by_id])

    def __repr__(self):
        return f"<LearningProject {self.id} {self.titre}>"


class LearningProjectSkill(db.Model):
    __tablename__ = "learning_project_skill"
    __table_args__ = (
        db.UniqueConstraint("project_id", "skill_id", name="uq_learning_project_skill"),
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("learning_project.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skill.id", ondelete="CASCADE"), nullable=False, index=True)
    target_level = db.Column(db.String(32), nullable=True)
    poids = db.Column(db.Float, nullable=False, default=1.0)
    obligatoire = db.Column(db.Boolean, nullable=False, default=False)
    notes = db.Column(db.Text, nullable=True)
    actif = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    project = db.relationship("LearningProject", backref=db.backref("skills", lazy=True, cascade="all, delete-orphan"))
    skill = db.relationship("Skill")


class AtelierProject(db.Model):
    __tablename__ = "atelier_project"
    __table_args__ = (
        db.PrimaryKeyConstraint("atelier_id", "project_id"),
    )

    atelier_id = db.Column(db.Integer, db.ForeignKey("atelier_activite.id", ondelete="CASCADE"), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("learning_project.id", ondelete="CASCADE"), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    atelier = db.relationship("AtelierActivite", backref=db.backref("projects", lazy=True, cascade="all, delete-orphan"))
    project = db.relationship("LearningProject", backref=db.backref("ateliers", lazy=True))


class SessionSkill(db.Model):
    __tablename__ = "session_skill"
    __table_args__ = (
        db.PrimaryKeyConstraint("session_id", "skill_id"),
    )

    session_id = db.Column(db.Integer, db.ForeignKey("session_activite.id", ondelete="CASCADE"), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey("skill.id", ondelete="CASCADE"), nullable=False)
    expected_level = db.Column(db.String(32), nullable=True)
    coverage = db.Column(db.Float, nullable=False, default=1.0)
    created_at = db.Column(db.DateTime, default=utcnow)

    session = db.relationship("SessionActivite", backref=db.backref("skills", lazy=True, cascade="all, delete-orphan"))
    skill = db.relationship("Skill")


class SessionAssessment(db.Model):
    __tablename__ = "session_assessment"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("session_activite.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("learning_project.id", ondelete="SET NULL"), nullable=True, index=True)
    method = db.Column(db.String(32), nullable=False, default="OBSERVATION")
    notes = db.Column(db.Text, nullable=True)
    assessed_at = db.Column(db.DateTime, default=utcnow, index=True)
    assessed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)

    session = db.relationship("SessionActivite")
    project = db.relationship("LearningProject")
    assessed_by = db.relationship("User")


class SessionAssessmentSkill(db.Model):
    __tablename__ = "session_assessment_skill"
    __table_args__ = (
        db.UniqueConstraint("session_assessment_id", "skill_id", name="uq_session_assessment_skill"),
    )

    id = db.Column(db.Integer, primary_key=True)
    session_assessment_id = db.Column(
        db.Integer,
        db.ForeignKey("session_assessment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_id = db.Column(db.Integer, db.ForeignKey("skill.id", ondelete="CASCADE"), nullable=False, index=True)

    # NA / EN_COURS / ACQUIS
    result = db.Column(db.String(16), nullable=False, default="EN_COURS", index=True)
    score = db.Column(db.Integer, nullable=True)
    observed_level = db.Column(db.String(32), nullable=True)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    assessment = db.relationship(
        "SessionAssessment",
        backref=db.backref("results", lazy=True, cascade="all, delete-orphan"),
    )
    skill = db.relationship("Skill")
