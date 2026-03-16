"""
Test settings.
Used exclusively by pytest — never in a running server.
Inherits from local.py and overrides what needs to be isolated for tests.
"""

from .local import *  # noqa: F401, F403

# ---------------------------------------------------------------------------
# Database — explicit test DB, never touches jap_local
# ---------------------------------------------------------------------------

# Django creates and drops this DB automatically before/after the test suite.
# The user's local DB (jap_local) is never touched.
DATABASES["default"]["TEST"] = {"NAME": "jap_test"}  # noqa: F405

# ---------------------------------------------------------------------------
# Channels — in-memory layer (no Redis required during tests)
# ---------------------------------------------------------------------------

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

# ---------------------------------------------------------------------------
# Passwords — faster hashing for tests
# ---------------------------------------------------------------------------

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# ---------------------------------------------------------------------------
# Email — in-memory backend for tests (no real emails sent)
# ---------------------------------------------------------------------------

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
