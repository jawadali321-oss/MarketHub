from .base import *  # noqa

DEBUG = True

ALLOWED_HOSTS = ["*"]

# In dev, use console email backend
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Django Debug Toolbar (optional — install separately)

# Relax CORS in dev
CORS_ALLOW_ALL_ORIGINS = True

# Disable SSL redirects in dev
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Show full SQL queries in dev logs
LOGGING["loggers"]["django.db.backends"] = {  # noqa
    "handlers": ["console"],
    "level": "DEBUG",
    "propagate": False,
}
