"""Zentrale Konfiguration.

Lokal werden Werte aus `.env` im Projektverzeichnis gelesen, in Kubernetes
kommen sie als Umgebungsvariablen (ConfigMap/Secret). Echte
Umgebungsvariablen haben Vorrang vor `.env` (z. B.
`DATABASE_URL=sqlite:///x.db alembic ...` trotz vorhandener `.env`).
"""
import os
from pathlib import Path

from sqlalchemy import URL

BASE_DIR = Path(__file__).resolve().parent.parent


def load_dotenv(path=None):
    env_path = path or (BASE_DIR / ".env")
    env = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


_env = load_dotenv()


def get(key, default=None):
    return os.environ.get(key) or _env.get(key) or default


def get_bool(key, default=False):
    value = get(key)
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "ja", "on")


def get_int(key, default):
    value = get(key)
    return int(value) if value else default


def database_url():
    """DATABASE_URL hat Vorrang (z. B. SQLite in Tests), sonst MariaDB aus DB_*."""
    if get("DATABASE_URL"):
        return get("DATABASE_URL")
    return URL.create(
        "mysql+pymysql",
        username=get("DB_USER", "ladedaten"),
        password=get("DB_PASSWORD", ""),
        host=get("DB_HOST", "localhost"),
        port=get_int("DB_PORT", 3306),
        database=get("DB_NAME", "ladedaten"),
        query={"charset": "utf8mb4"},
    )


# Wird im Image aus dem Git-Tag gesetzt
APP_VERSION = get("APP_VERSION", "dev")
SECRET_KEY = get("SECRET_KEY", "")
SESSION_COOKIE_SECURE = get_bool("SESSION_COOKIE_SECURE", True)
# Hinter Ingress/Reverse-Proxy: X-Forwarded-* auswerten (für korrekte QR-URLs)
TRUST_PROXY = get_bool("TRUST_PROXY", False)
LOGIN_RATE_LIMIT = get("LOGIN_RATE_LIMIT", "10 per minute")

UPLOAD_DIR = Path(get("UPLOAD_DIR", str(BASE_DIR / "data" / "fotos")))
MAX_UPLOAD_MB = get_int("MAX_UPLOAD_MB", 25)

# Standard-Etikettengröße "BREITExHÖHE" in mm
LABEL_SIZE = get("LABEL_SIZE", "90x60")

# Wird von `manage.py migrate` beim Start ausgewertet
ADMIN_USERNAME = get("ADMIN_USERNAME", "")
ADMIN_PASSWORD = get("ADMIN_PASSWORD", "")
ADMIN_PASSWORD_HASH = get("ADMIN_PASSWORD_HASH", "")
SEED_DEMO_DATA = get_bool("SEED_DEMO_DATA", True)
DB_WAIT_SECONDS = get_int("DB_WAIT_SECONDS", 60)
