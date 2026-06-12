import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DEFAULT_SECRET_KEY = "Uneapplicationdesuivibudgétairequisimplifielaviedetoutlemondenormalement"


def _charger_dotenv(chemin: str) -> None:
    """Charge le fichier .env (clé=valeur) dans os.environ.

    - Les variables déjà présentes dans l'environnement restent prioritaires.
    - Format supporté: lignes 'CLE=valeur', commentaires '#', lignes vides.
    Permet au service Windows (NSSM/waitress) et aux scripts d'hériter de
    la même configuration sans dépendance externe.
    """
    try:
        with open(chemin, encoding="utf-8") as fh:
            for ligne in fh:
                ligne = ligne.strip()
                if not ligne or ligne.startswith("#") or "=" not in ligne:
                    continue
                cle, _, valeur = ligne.partition("=")
                cle = cle.strip()
                valeur = valeur.strip().strip('"').strip("'")
                if cle and cle not in os.environ:
                    os.environ[cle] = valeur
    except OSError:
        pass


_charger_dotenv(os.path.join(BASE_DIR, ".env"))

# Dossier "data" optionnel (utile si tu pack en exe ou si tu veux stocker ailleurs)
DEFAULT_DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")  # ex: si ton exe est dans C:\AppGestion\app\
DATA_DIR = os.environ.get("APP_DATA_DIR", DEFAULT_DATA_DIR)
os.makedirs(DATA_DIR, exist_ok=True)


class Config:

    APP_NAME = os.environ.get("APP_NAME", "App Gestion")
    ORGANIZATION_NAME = os.environ.get("ORGANIZATION_NAME", "Votre structure")
    ERP_ENV = os.environ.get("ERP_ENV", "development").strip().lower()

    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        DEFAULT_SECRET_KEY,
    )
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", str(10 * 1024 * 1024)))
    WTF_CSRF_TIME_LIMIT = int(os.environ.get("WTF_CSRF_TIME_LIMIT", str(8 * 60 * 60)))

    # --- Cookies de session ---------------------------------------------------
    # HttpOnly: cookie jamais accessible en JavaScript (mitigation vol de session XSS).
    # SameSite=Lax: cookie non envoyé sur les requêtes cross-site (renfort CSRF).
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
    # Secure: cookie transmis uniquement en HTTPS. Auto-activé si l'URL publique
    # est en https://, sinon surcharger via SESSION_COOKIE_SECURE=1.
    # Ne pas forcer sur un déploiement LAN en HTTP pur: la connexion casserait.
    _public_url = os.environ.get("ERP_PUBLIC_BASE_URL", "").strip().lower()
    SESSION_COOKIE_SECURE = os.environ.get(
        "SESSION_COOKIE_SECURE",
        "1" if _public_url.startswith("https://") else "0",
    ) in {"1", "true", "True", "yes", "YES"}
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE

    # --- DB -----------------------------------------------------------------
    # Objectif :
    # - Priorité aux variables d'environnement (Postgres ou autre)
    # - Fallback SQLite local si rien n'est défini
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
    os.makedirs(INSTANCE_DIR, exist_ok=True)

    # Fallback SQLite unique (stable, version Flask standard)
    DB_PATH = os.path.join(INSTANCE_DIR, "database.db")
    _default_sqlite_uri = "sqlite:///" + DB_PATH.replace("\\", "/")

    # Priorité aux variables d'environnement (dans cet ordre)
    _db_url = (
        os.environ.get("SQLALCHEMY_DATABASE_URI")
        or os.environ.get("DATABASE_URL")
        or _default_sqlite_uri
    )

    # Compat anciens formats (Heroku-like)
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = _db_url

    # --- Domaines / constantes ----------------------------------------------
    SECTEURS = [
        "Numérique",
        "Familles",
        "EPE",
        "Santé Transition",
        "Insertion Sociale et Professionnelle",
        "Animation Globale",
    ]

    # SMTP optionnel (envoi des feuilles d'émargement)
    MAIL_HOST = os.environ.get("MAIL_HOST", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "1") in {"1", "true", "True", "yes", "YES"}
    MAIL_SENDER = os.environ.get("MAIL_SENDER", "")
    MAIL_TIMEOUT_SECONDS = float(os.environ.get("MAIL_TIMEOUT_SECONDS", "10"))

    # URL publique (LAN) de l'application, utilisée pour générer des QR codes.
    # Exemple : http://erp-cgb:8000 ou http://192.168.1.10:8000
    PUBLIC_BASE_URL = os.environ.get("ERP_PUBLIC_BASE_URL", "")

    # Répertoire des uploads (pièces jointes, logos, exports visuels).
    # Par défaut: ./static/uploads (compatible Windows/Linux + hébergement web simple).
    APP_UPLOAD_DIR = os.environ.get("APP_UPLOAD_DIR", os.path.join(BASE_DIR, "static", "uploads"))

    # Migration DB industrialisée
    DB_AUTO_UPGRADE_ON_START = os.environ.get("DB_AUTO_UPGRADE_ON_START", "1") in {"1", "true", "True", "yes", "YES"}
    DB_ENABLE_LEGACY_SCHEMA_PATCH = os.environ.get("DB_ENABLE_LEGACY_SCHEMA_PATCH", "0") in {"1", "true", "True", "yes", "YES"}

    # Réinitialisation mot de passe
    PASSWORD_RESET_TOKEN_MAX_AGE_SECONDS = int(os.environ.get("PASSWORD_RESET_TOKEN_MAX_AGE_SECONDS", "3600"))
    # Affichage du lien de réinitialisation dans la page (dev local sans SMTP).
    # DOIT rester désactivé par défaut: un lien valide affiché à l'écran permet
    # de prendre le contrôle d'un compte. Activer uniquement en local via
    # PASSWORD_RESET_ALLOW_DEBUG_LINK=1.
    PASSWORD_RESET_ALLOW_DEBUG_LINK = os.environ.get("PASSWORD_RESET_ALLOW_DEBUG_LINK", "0") in {"1", "true", "True", "yes", "YES"}

