"""Local AI test settings, independent of the team's PostgreSQL database."""
import os
from .settings import *
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "local-ai-development-only")
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "m2-demo.sqlite3"}}
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]


DEBUG = True
LOGIN_URL = "login"
