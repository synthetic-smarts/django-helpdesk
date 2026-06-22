"""PostgreSQL-backed test settings for the synsmarts fork (CI + RLS validation).

Mirrors demodesk's helpdesk config but points DATABASES at PostgreSQL so the
RLS/role/composite-FK migrations (synN) and their validation tests run against
the same engine as production (CNPG postgresql 16.6). DB params come from env
(CI sets them to its postgres service); defaults target the local 16.6 container.
sqlite cannot represent RLS, so 1d onward must use this settings module.
"""
import os

from demodesk.config.settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("PGDATABASE", "helpdesk_test"),
        "USER": os.environ.get("PGUSER", "postgres"),
        "PASSWORD": os.environ.get("PGPASSWORD", "postgres"),
        "HOST": os.environ.get("PGHOST", "127.0.0.1"),
        "PORT": os.environ.get("PGPORT", "55432"),
    }
}
