"""
Local development settings.
Used when running locally (Docker or native).
"""
from .base import *  # noqa: F401, F403

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

DEBUG = True

SECRET_KEY = env(  # noqa: F405
    "SECRET_KEY",
    default="django-insecure-local-dev-key-change-in-production-!!",
)

ALLOWED_HOSTS = ["*"]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASES = {
    "default": env.db(  # noqa: F405
        "DATABASE_URL",
        default="postgresql://jap:jap@localhost:5432/jap_local",
    ),
}
DATABASES["default"]["ATOMIC_REQUESTS"] = True

# ---------------------------------------------------------------------------
# Email (console backend for local dev)
# ---------------------------------------------------------------------------

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ---------------------------------------------------------------------------
# CORS (allow all for local dev)
# ---------------------------------------------------------------------------

CORS_ALLOW_ALL_ORIGINS = True

# ---------------------------------------------------------------------------
# DRF (add BrowsableAPI for local dev)
# ---------------------------------------------------------------------------

REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [  # noqa: F405
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
]

# ---------------------------------------------------------------------------
# Debug toolbar (optional — install django-debug-toolbar in dev deps to use)
# ---------------------------------------------------------------------------

# INSTALLED_APPS += ["debug_toolbar"]
# MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
# INTERNAL_IPS = ["127.0.0.1"]
