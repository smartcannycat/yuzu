from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from config.settings.config import AppSettings, get_settings

BASE_DIR = Path(__file__).resolve().parent.parent.parent

app_settings = get_settings()

SECRET_KEY = app_settings.SECRET_KEY
DEBUG = app_settings.DEBUG
ALLOWED_HOSTS = list(app_settings.ALLOWED_HOSTS)
if (app_settings.DEBUG or app_settings.is_testing) and "testserver" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("testserver")

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
]

THIRD_PARTY_APPS = [
    "corsheaders",
    "ninja_extra",
    "ninja_jwt",
    "ninja_jwt.token_blacklist",
]

LOCAL_APPS = [
    "apps.core",
    "apps.users",
    "apps.lots",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

AUTH_USER_MODEL = "users.User"

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.ApiProblemDetailsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


def _build_database_config(settings_obj: AppSettings) -> dict[str, Any]:
    if settings_obj.DATABASE_URL:
        parsed = urlparse(settings_obj.DATABASE_URL)
        if parsed.scheme.startswith("sqlite"):
            db_path = parsed.path.lstrip("/") or "db.sqlite3"
            return {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / db_path if not Path(db_path).is_absolute() else Path(db_path),
            }
        if parsed.scheme in {"postgres", "postgresql"}:
            return {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": parsed.path.lstrip("/") or settings_obj.POSTGRES_DB,
                "USER": unquote(parsed.username or settings_obj.POSTGRES_USER),
                "PASSWORD": unquote(parsed.password or settings_obj.POSTGRES_PASSWORD),
                "HOST": parsed.hostname or settings_obj.POSTGRES_HOST,
                "PORT": parsed.port or settings_obj.POSTGRES_PORT,
                "CONN_MAX_AGE": 600,
                "CONN_HEALTH_CHECKS": True,
            }
        raise ValueError(f"Unsupported DATABASE_URL scheme: {parsed.scheme}")

    if settings_obj.USE_SQLITE:
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }

    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": settings_obj.POSTGRES_DB,
        "USER": settings_obj.POSTGRES_USER,
        "PASSWORD": settings_obj.POSTGRES_PASSWORD,
        "HOST": settings_obj.POSTGRES_HOST,
        "PORT": settings_obj.POSTGRES_PORT,
        "CONN_MAX_AGE": 600,
        "CONN_HEALTH_CHECKS": True,
    }


# Database
DATABASES = {
    "default": _build_database_config(app_settings),
}

# Password validation (aligned with API_DATA_CONTRACTS.md: 8..128 characters)
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static and Media files
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

media_root_path = Path(app_settings.MEDIA_ROOT)
MEDIA_URL = app_settings.MEDIA_URL
MEDIA_ROOT = media_root_path if media_root_path.is_absolute() else BASE_DIR / media_root_path

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CORS
CORS_ALLOWED_ORIGINS = app_settings.CORS_ALLOWED_ORIGINS
CORS_ALLOW_ALL_ORIGINS = app_settings.CORS_ALLOW_ALL_ORIGINS

# Production reverse-proxy and cookie hardening
if app_settings.is_production:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Ninja JWT
NINJA_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=app_settings.JWT_ACCESS_TOKEN_LIFETIME_MINUTES),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=app_settings.JWT_REFRESH_TOKEN_LIFETIME_DAYS),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "SIGNING_KEY": app_settings.JWT_SIGNING_KEY or app_settings.SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}
