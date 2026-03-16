"""
Development/staging settings.
Closer to production but with some debugging enabled.
DJANGO_SETTINGS_MODULE=config.settings.dev
"""
from .base import *  # noqa: F401, F403

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

DEBUG = True

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])  # noqa: F405

# ---------------------------------------------------------------------------
# Database — must be set via DATABASE_URL env var
# ---------------------------------------------------------------------------

DATABASES = {
    "default": env.db("DATABASE_URL"),  # noqa: F405
}
DATABASES["default"]["ATOMIC_REQUESTS"] = True

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

CORS_ALLOWED_ORIGINS = env.list(  # noqa: F405
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:4000", "http://localhost:5173"],
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "DEBUG",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
