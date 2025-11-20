"""
Test settings for running pytest inside docker.
This overrides DATABASE, CELERY, BLOCKCHAIN, KEY FILES, and disables heavy checks.
"""

from .settings import *  # import everything from base settings
import os

# ==============================================================
# TEST ENVIRONMENT FLAGS
# ==============================================================

DEBUG = True
DJANGO_ENV = "test"
ALLOWED_HOSTS = ["*"]


# ==============================================================
# REDUCE LOG SPAM
# ==============================================================

LOGGING["loggers"]["django"]["level"] = "WARNING"
LOGGING["loggers"]["apps.seed_licenses"]["level"] = "WARNING"
LOGGING["loggers"]["blockchain"]["level"] = "WARNING"

# ==============================================================
# DISABLE CELERY (Important for isolated pytest container)
# ==============================================================

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"


# ==============================================================
# FIX Django test speed
# ==============================================================

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# ==============================================================
# TEST STATIC/MEDIA
# ==============================================================

STATIC_ROOT = BASE_DIR / "test_static"
MEDIA_ROOT = BASE_DIR / "test_media"
