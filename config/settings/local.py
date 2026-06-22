"""
Local (Development) Settings
"""
from .base import *

# Development uchun DEBUG rejimi
DEBUG = True

# Development uchun ALLOWED_HOSTS
ALLOWED_HOSTS = ['*']

# Debug Toolbar (agar o'rnatilgan bo'lsa)
try:
    import debug_toolbar
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
    INTERNAL_IPS = ['127.0.0.1']
except ImportError:
    pass

# Email backend - development uchun console
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}
