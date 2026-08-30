from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from corsheaders.defaults import default_headers
from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent
LOCAL_DEV_SECRET_KEY = "learning-hub-local-secret-key-2026"
INSECURE_SECRET_KEYS = {
    LOCAL_DEV_SECRET_KEY,
    "change-me-django-secret-key",
    "change-me",
    "changeme",
}


def load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_dotenv_file(BASE_DIR / ".env")


def env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def env_optional_float(name: str) -> float | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    normalized = raw.strip()
    if not normalized:
        return None
    try:
        return float(normalized)
    except ValueError:
        return None


def env_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw is None:
        return default
    values = [item.strip() for item in raw.split(",")]
    return [item for item in values if item]


SECRET_KEY = env_str("SECRET_KEY") or env_str("DJANGO_SECRET_KEY") or LOCAL_DEV_SECRET_KEY
DEBUG = env_bool("DEBUG", env_bool("DJANGO_DEBUG", True))
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", ["127.0.0.1", "localhost"] if DEBUG else [])
if not DEBUG:
    if SECRET_KEY in INSECURE_SECRET_KEYS:
        raise ImproperlyConfigured("Set a unique SECRET_KEY or DJANGO_SECRET_KEY before running with DEBUG=False.")
    if not ALLOWED_HOSTS:
        raise ImproperlyConfigured("Set ALLOWED_HOSTS before running with DEBUG=False.")

USE_X_FORWARDED_HOST = env_bool("USE_X_FORWARDED_HOST", True)
if env_bool("SECURE_PROXY_SSL_HEADER_ENABLED", True):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
else:
    SECURE_PROXY_SSL_HEADER = None

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "django_cleanup.apps.CleanupConfig",
    "apps.users.apps.UsersConfig",
    "apps.employees.apps.EmployeesConfig",
    "apps.online.apps.OnlineConfig",
    "apps.training.apps.TrainingConfig",
]

AUTH_USER_MODEL = "users.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "Studentlist.urls"
WSGI_APPLICATION = "Studentlist.wsgi.application"
ASGI_APPLICATION = "Studentlist.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

if env_bool("POSTGRESQL", False):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env_str("DB_NAME", "online_lessons"),
            "USER": env_str("DB_USER", "postgres"),
            "PASSWORD": env_str("DB_PASSWORD", ""),
            "HOST": env_str("DB_HOST", "127.0.0.1"),
            "PORT": env_str("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = env_str("TIME_ZONE", "Europe/Berlin")
APP_RELEASE = env_str("APP_RELEASE", "")
USE_I18N = True
USE_TZ = True
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", not DEBUG)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", not DEBUG)
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)
SECURE_REDIRECT_EXEMPT = env_list(
    "SECURE_REDIRECT_EXEMPT",
    [
        r"^api/health/",
        r"^api/training/internal/",
    ],
)
CSRF_COOKIE_SAMESITE = env_str("CSRF_COOKIE_SAMESITE", "Lax") or "Lax"
SESSION_COOKIE_SAMESITE = env_str("SESSION_COOKIE_SAMESITE", "Lax") or "Lax"
SESSION_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = env_str("SECURE_REFERRER_POLICY", "strict-origin-when-cross-origin")
X_FRAME_OPTIONS = env_str("X_FRAME_OPTIONS", "DENY")
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 0 if DEBUG else 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", not DEBUG)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", not DEBUG)
HEALTHCHECK_EXPOSE_DETAILS = env_bool("HEALTHCHECK_EXPOSE_DETAILS", DEBUG)

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.online.authentication.OnlineCookieJWTAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "online_auth": env_str("ONLINE_AUTH_RATE", "20/minute"),
        "online_magic_link": env_str("ONLINE_MAGIC_LINK_RATE", "10/minute"),
        "training_ai_question": env_str("TRAINING_AI_QUESTION_RATE", "30/hour"),
        "training_ai_quiz": env_str("TRAINING_AI_QUIZ_RATE", "20/hour"),
        "training_admin_ai_analytics": env_str("TRAINING_ADMIN_AI_ANALYTICS_RATE", "60/hour"),
        "training_directus_sync": env_str("TRAINING_DIRECTUS_SYNC_RATE", "240/hour"),
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", False)
CORS_ALLOW_CREDENTIALS = env_bool("CORS_ALLOW_CREDENTIALS", True)
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    [
        "http://localhost:5180",
        "http://localhost:5182",
        "http://localhost:5183",
        "http://localhost:5184",
        "http://127.0.0.1:5180",
        "http://127.0.0.1:5182",
        "http://127.0.0.1:5183",
        "http://127.0.0.1:5184",
    ],
)
CORS_ALLOW_HEADERS = list(default_headers) + [
    "x-online-auth-scope",
]
if not DEBUG and CORS_ALLOW_ALL_ORIGINS and CORS_ALLOW_CREDENTIALS:
    raise ImproperlyConfigured("CORS_ALLOW_ALL_ORIGINS cannot be enabled with credentials in production.")
CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    [
        "http://localhost:5180",
        "http://localhost:5182",
        "http://localhost:5183",
        "http://localhost:5184",
        "http://127.0.0.1:5180",
        "http://127.0.0.1:5182",
        "http://127.0.0.1:5183",
        "http://127.0.0.1:5184",
    ],
)

DEFAULT_FROM_EMAIL = env_str("DEFAULT_FROM_EMAIL", "no-reply@example.com")

ONLINE_EMAIL_MODE = env_str("ONLINE_EMAIL_MODE", "console")
ONLINE_EMAIL_DIRECTUS_FLOW_URL = env_str("ONLINE_EMAIL_DIRECTUS_FLOW_URL", "")
ONLINE_EMAIL_DIRECTUS_TOKEN = env_str("ONLINE_EMAIL_DIRECTUS_TOKEN", "")
ONLINE_COURSE_ACCESS_DIRECTUS_FLOW_URL = env_str("ONLINE_COURSE_ACCESS_DIRECTUS_FLOW_URL", "")
ONLINE_EMAIL_HOST = env_str("ONLINE_EMAIL_HOST", "")
ONLINE_EMAIL_PORT = env_int("ONLINE_EMAIL_PORT", 587)
ONLINE_EMAIL_HOST_USER = env_str("ONLINE_EMAIL_HOST_USER", "")
ONLINE_EMAIL_HOST_PASSWORD = env_str("ONLINE_EMAIL_HOST_PASSWORD", "")
ONLINE_EMAIL_USE_TLS = env_bool("ONLINE_EMAIL_USE_TLS", True)
ONLINE_EMAIL_FROM_EMAIL = env_str("ONLINE_EMAIL_FROM_EMAIL", DEFAULT_FROM_EMAIL)
ONLINE_FEEDBACK_RECEIVER_EMAIL = env_str("ONLINE_FEEDBACK_RECEIVER_EMAIL", "")
ONLINE_STUDENT_PORTAL_URL = env_str("ONLINE_STUDENT_PORTAL_URL", "http://localhost:5180/login")
ONLINE_PUBLIC_PORTAL_URL = env_str("ONLINE_PUBLIC_PORTAL_URL", "http://localhost:5182/portal")
ONLINE_MAGIC_LINK_TTL_MINUTES = env_int("ONLINE_MAGIC_LINK_TTL_MINUTES", 120)
ONLINE_PAYMENT_MODE = env_str("ONLINE_PAYMENT_MODE", "free")
ONLINE_ATTENDANCE_SYNC_MODE = env_str("ONLINE_ATTENDANCE_SYNC_MODE", "demo")
ONLINE_GRAPH_API_BASE_URL = env_str("ONLINE_GRAPH_API_BASE_URL", "https://graph.microsoft.com/v1.0")
ONLINE_GRAPH_TIMEOUT_SECONDS = env_int("ONLINE_GRAPH_TIMEOUT_SECONDS", 15)
ONLINE_GRAPH_TENANT_ID = env_str("ONLINE_GRAPH_TENANT_ID", "")
ONLINE_GRAPH_CLIENT_ID = env_str("ONLINE_GRAPH_CLIENT_ID", "")
ONLINE_GRAPH_CLIENT_SECRET = env_str("ONLINE_GRAPH_CLIENT_SECRET", "")
ONLINE_GRAPH_ORGANIZER_USER_ID = env_str("ONLINE_GRAPH_ORGANIZER_USER_ID", "")
ONLINE_GRAPH_ORGANIZER_EMAIL = env_str("ONLINE_GRAPH_ORGANIZER_EMAIL", "")
ONLINE_PAYMENT_WEBHOOK_SECRET = env_str("ONLINE_PAYMENT_WEBHOOK_SECRET", "")
ONLINE_PAYMENT_WEBHOOK_REQUIRE_SIGNATURE = env_bool(
    "ONLINE_PAYMENT_WEBHOOK_REQUIRE_SIGNATURE",
    not DEBUG and ONLINE_PAYMENT_MODE not in {"free", "mock"},
)
ONLINE_PUBLIC_CHECKOUT_SUCCESS_URL = env_str("ONLINE_PUBLIC_CHECKOUT_SUCCESS_URL", "http://localhost:5182/success")
ONLINE_PUBLIC_CHECKOUT_CANCEL_URL = env_str("ONLINE_PUBLIC_CHECKOUT_CANCEL_URL", "http://localhost:5182/checkout/{slug}")
ONLINE_GOOGLE_CLIENT_ID = env_str("ONLINE_GOOGLE_CLIENT_ID", "")
ONLINE_MICROSOFT_TENANT_ID = env_str("ONLINE_MICROSOFT_TENANT_ID", ONLINE_GRAPH_TENANT_ID or "common")
ONLINE_MICROSOFT_CLIENT_ID = env_str("ONLINE_MICROSOFT_CLIENT_ID", ONLINE_GRAPH_CLIENT_ID)
ONLINE_MICROSOFT_CLIENT_SECRET = env_str("ONLINE_MICROSOFT_CLIENT_SECRET", ONLINE_GRAPH_CLIENT_SECRET)
ONLINE_MICROSOFT_SCOPES = env_list("ONLINE_MICROSOFT_SCOPES", ["openid", "profile", "email"])
ONLINE_MICROSOFT_AUTO_PROVISION_STUDENTS = env_bool("ONLINE_MICROSOFT_AUTO_PROVISION_STUDENTS", True)
ONLINE_MICROSOFT_STUDENT_EMAILS = env_list("ONLINE_MICROSOFT_STUDENT_EMAILS", [])
ONLINE_MICROSOFT_TEACHER_EMAILS = env_list("ONLINE_MICROSOFT_TEACHER_EMAILS", [])
ONLINE_MICROSOFT_ADMIN_EMAILS = env_list("ONLINE_MICROSOFT_ADMIN_EMAILS", [])
ONLINE_MICROSOFT_DEFAULT_STUDENT_LANGUAGE = env_str("ONLINE_MICROSOFT_DEFAULT_STUDENT_LANGUAGE", "en") or "en"
ONLINE_AUTH_COOKIE_SECURE = env_bool("ONLINE_AUTH_COOKIE_SECURE", not DEBUG)
ONLINE_AUTH_COOKIE_SAMESITE = env_str("ONLINE_AUTH_COOKIE_SAMESITE", "Lax") or "Lax"
ONLINE_AUTH_COOKIE_DOMAIN = env_str("ONLINE_AUTH_COOKIE_DOMAIN", "")
ONLINE_AUTH_COOKIE_PATH = env_str("ONLINE_AUTH_COOKIE_PATH", "/") or "/"
ONLINE_STUDENT_ACCESS_COOKIE_NAME = env_str("ONLINE_STUDENT_ACCESS_COOKIE_NAME", "online_student_access")
ONLINE_STUDENT_REFRESH_COOKIE_NAME = env_str("ONLINE_STUDENT_REFRESH_COOKIE_NAME", "online_student_refresh")
ONLINE_STAFF_ACCESS_COOKIE_NAME = env_str("ONLINE_STAFF_ACCESS_COOKIE_NAME", "online_staff_access")
ONLINE_STAFF_REFRESH_COOKIE_NAME = env_str("ONLINE_STAFF_REFRESH_COOKIE_NAME", "online_staff_refresh")
ONLINE_SSO_STATE_TTL_SECONDS = env_int("ONLINE_SSO_STATE_TTL_SECONDS", 600)
TRAINING_NOTEBOOK_RUNTIME_ENABLED = env_bool("TRAINING_NOTEBOOK_RUNTIME_ENABLED", False)
TRAINING_JUPYTERHUB_BASE_URL = env_str("TRAINING_JUPYTERHUB_BASE_URL", "")
TRAINING_JUPYTERHUB_SERVICE_TOKEN = env_str("TRAINING_JUPYTERHUB_SERVICE_TOKEN", "")
TRAINING_JUPYTERHUB_API_TOKEN = env_str("TRAINING_JUPYTERHUB_API_TOKEN", "")
TRAINING_JUPYTERHUB_SHARED_SECRET = env_str("TRAINING_JUPYTERHUB_SHARED_SECRET", "")
TRAINING_JUPYTERHUB_EGRESS_ENABLED = env_bool("TRAINING_JUPYTERHUB_EGRESS_ENABLED", False)
TRAINING_JUPYTERHUB_GPU_RUNTIME_ENABLED = env_bool("TRAINING_JUPYTERHUB_GPU_RUNTIME_ENABLED", False)
TRAINING_MAX_LAB_SESSION_MINUTES_CAP = env_int("TRAINING_MAX_LAB_SESSION_MINUTES_CAP", 240)
TRAINING_JUPYTERHUB_FORCE_LOGOUT_BEFORE_LOGIN = env_bool("TRAINING_JUPYTERHUB_FORCE_LOGOUT_BEFORE_LOGIN", False)
TRAINING_JUPYTER_LOGIN_TTL_SECONDS = env_int("TRAINING_JUPYTER_LOGIN_TTL_SECONDS", 180)
TRAINING_JUPYTER_SESSION_API_TOKEN_TTL_SECONDS = env_int("TRAINING_JUPYTER_SESSION_API_TOKEN_TTL_SECONDS", 30 * 24 * 60 * 60)
TRAINING_JUPYTER_SESSION_API_TOKEN_GRACE_SECONDS = env_int("TRAINING_JUPYTER_SESSION_API_TOKEN_GRACE_SECONDS", 30 * 24 * 60 * 60)
TRAINING_GRADER_RUNTIME_ENABLED = env_bool("TRAINING_GRADER_RUNTIME_ENABLED", False)
TRAINING_GRADER_MODE = env_str("TRAINING_GRADER_MODE", "demo")
TRAINING_GRADER_WEBHOOK_URL = env_str("TRAINING_GRADER_WEBHOOK_URL", "")
TRAINING_GRADER_WEBHOOK_SECRET = env_str("TRAINING_GRADER_WEBHOOK_SECRET", "")
TRAINING_GRADER_CALLBACK_BASE_URL = env_str("TRAINING_GRADER_CALLBACK_BASE_URL", "")
TRAINING_GRADER_REQUEST_TIMEOUT_SECONDS = env_int("TRAINING_GRADER_REQUEST_TIMEOUT_SECONDS", 20)
TRAINING_LAB_LAUNCH_TTL_SECONDS = env_int("TRAINING_LAB_LAUNCH_TTL_SECONDS", 300)
TRAINING_NBGRADER_BIN = env_str("TRAINING_NBGRADER_BIN", "nbgrader")
TRAINING_NBGRADER_COURSE_ROOT = env_str("TRAINING_NBGRADER_COURSE_ROOT", "")
TRAINING_SUBMISSION_STORAGE_PREFIX = env_str("TRAINING_SUBMISSION_STORAGE_PREFIX", "training/submissions")
TRAINING_SUBMISSION_MAX_UPLOAD_BYTES = env_int("TRAINING_SUBMISSION_MAX_UPLOAD_BYTES", 10 * 1024 * 1024)
TRAINING_GRADER_COMMAND_TIMEOUT_SECONDS = env_int("TRAINING_GRADER_COMMAND_TIMEOUT_SECONDS", 600)
TRAINING_AI_ENABLED = env_bool("TRAINING_AI_ENABLED", True)
TRAINING_AI_PROVIDER = env_str("TRAINING_AI_PROVIDER", "demo")
TRAINING_AI_BASE_URL = env_str("TRAINING_AI_BASE_URL", "")
TRAINING_AI_API_KEY = env_str("TRAINING_AI_API_KEY", "")
TRAINING_AI_CHAT_MODEL = env_str("TRAINING_AI_CHAT_MODEL", "")
TRAINING_AI_TIMEOUT_SECONDS = env_int("TRAINING_AI_TIMEOUT_SECONDS", 45)
TRAINING_AI_TEMPERATURE = env_optional_float("TRAINING_AI_TEMPERATURE")
OPENAI_API_KEY = env_str("OPENAI_API_KEY", "")
OPENAI_TTS_MODEL = env_str("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
OPENAI_TTS_VOICE = env_str("OPENAI_TTS_VOICE", "nova")
OPENAI_TTS_TIMEOUT_SECONDS = env_int("OPENAI_TTS_TIMEOUT_SECONDS", 45)
ANNA_TTS_PROVIDER = env_str("ANNA_TTS_PROVIDER", "gemini-live").lower() or "gemini-live"
GEMINI_API_KEY = env_str("GEMINI_API_KEY", "")
GEMINI_TTS_MODEL = env_str("GEMINI_TTS_MODEL", "gemini-3.1-flash-tts-preview")
GEMINI_TTS_VOICE = env_str("GEMINI_TTS_VOICE", "Achernar")
GEMINI_TTS_TIMEOUT_SECONDS = env_int("GEMINI_TTS_TIMEOUT_SECONDS", 45)
GEMINI_LIVE_MODEL = env_str("GEMINI_LIVE_MODEL", "gemini-3.1-flash-live-preview")
GEMINI_LIVE_VOICE = env_str("GEMINI_LIVE_VOICE", GEMINI_TTS_VOICE or "Achernar")
GEMINI_LIVE_SILENCE_DURATION_MS = env_int("GEMINI_LIVE_SILENCE_DURATION_MS", 650)
GEMINI_LIVE_PREFIX_PADDING_MS = env_int("GEMINI_LIVE_PREFIX_PADDING_MS", 250)
COURSE_BUILDER_AI_ORCHESTRATOR = env_str("COURSE_BUILDER_AI_ORCHESTRATOR", "legacy")
COURSE_BUILDER_AI_AGENTS_TRACING_ENABLED = env_bool("COURSE_BUILDER_AI_AGENTS_TRACING_ENABLED", False)
TRAINING_AI_TRANSCRIPTION_MODEL = env_str("TRAINING_AI_TRANSCRIPTION_MODEL", "whisper-1")
TRAINING_AI_TRANSCRIPTION_TIMEOUT_SECONDS = env_int("TRAINING_AI_TRANSCRIPTION_TIMEOUT_SECONDS", 180)
TRAINING_AI_PGVECTOR_ENABLED = env_bool("TRAINING_AI_PGVECTOR_ENABLED", True)
TRAINING_AI_VECTOR_DIMENSIONS = env_int("TRAINING_AI_VECTOR_DIMENSIONS", 256)
TRAINING_AI_INDEX_CHUNK_SIZE = env_int("TRAINING_AI_INDEX_CHUNK_SIZE", 900)
TRAINING_AI_INDEX_CHUNK_OVERLAP = env_int("TRAINING_AI_INDEX_CHUNK_OVERLAP", 120)
TRAINING_AI_MAX_CONTEXT_CHUNKS = env_int("TRAINING_AI_MAX_CONTEXT_CHUNKS", 5)
TRAINING_AI_QUESTION_MAX_CHARS = env_int("TRAINING_AI_QUESTION_MAX_CHARS", 1200)
TRAINING_DIRECTUS_SYNC_TOKEN = env_str("TRAINING_DIRECTUS_SYNC_TOKEN", env_str("DIRECTUS_API_TOKEN", ""))

