import os
from pathlib import Path
from decouple import config, Csv


def config_bool(key, default=False):
    """
    Environment qiymatini bool ga xavfsiz aylantiradi.
    Ba'zi deploy muhitlarida DEBUG kabi qiymatlar `release`/`production`
    ko'rinishida kelishi mumkin, shuning uchun ValueError chiqarmaymiz.
    """
    raw_value = config(key, default=default)

    if isinstance(raw_value, bool):
        return raw_value
    if raw_value is None:
        return default

    value = str(raw_value).strip().lower()
    if value in {'1', 'true', 'yes', 'on', 'debug', 'development', 'dev'}:
        return True
    if value in {'0', 'false', 'no', 'off', 'release', 'production', 'prod'}:
        return False
    return bool(default)

# 1. PATHS
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 2. SECURITY
# .env faylidan o'qiladi
SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-key-only-for-local-testing-change-this')
DEBUG = config_bool('DEBUG', default=True)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='13.39.83.160,localhost,127.0.0.1', cast=Csv())

# Development uchun async ORM ruxsat berish
if DEBUG:
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

# 3. APPS
INSTALLED_APPS = [
    # Unfold admin (django.contrib.admin dan oldin bo'lishi kerak)
    'unfold',
    'unfold.contrib.filters',
    'unfold.contrib.forms',

    'rest_framework.authtoken',
    'rest_framework',
    'drf_spectacular',
    'corsheaders',
    'apps.api',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # UCHINCHI TOMON KUTUBXONALARI
    'widget_tweaks',  # pip install django-widget-tweaks
    'django.contrib.humanize',  # Number formatting (intcomma, naturaltime)

    # BIZNING APPLAR (To'liq yo'l bilan)
    'apps.core',
    'apps.organizations',
    'apps.users',
    'apps.education',
    'apps.crm',
    'apps.finance',
    'apps.operations',
    'apps.automation',
    'apps.hardware',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    # BIZNING MIDDLEWARE
    'apps.core.middleware.TenantMiddleware',
    'apps.core.middleware.HTMXMiddleware',  # HTMX optimallashtirish
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.tenant_context',
                'apps.core.context_processors.user_permissions_context',
                'apps.core.context_processors.notifications_context',
            ],
        },
    },
]

# ASGI va WSGI
ASGI_APPLICATION = 'config.asgi.application'
WSGI_APPLICATION = 'config.wsgi.application'

# 4. DATABASE
# PostgreSQL yoki SQLite tanlash
USE_POSTGRES = config_bool('USE_POSTGRES', default=False)

if USE_POSTGRES:
    # PostgreSQL sozlamalari
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME', default='crmtizim_db'),
            'USER': config('DB_USER', default='crmtizim_user'),
            'PASSWORD': config('DB_PASSWORD', default=''),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
            'OPTIONS': {
                'client_encoding': 'UTF8',
            },
        }
    }
else:
    # SQLite sozlamalari (development uchun)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# 5. AUTH
AUTH_USER_MODEL = 'users.User'
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'
AUTHENTICATION_BACKENDS = [
    'apps.users.backends.PhoneBackend',
]

# 6. I18N
LANGUAGE_CODE = 'uz'
TIME_ZONE = 'Asia/Tashkent'
USE_I18N = True
USE_TZ = True

# 7. STATIC & MEDIA
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# 8. AUTOMATION
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_BACKUP_CHAT_ID = os.getenv('TELEGRAM_BACKUP_CHAT_ID', '')

# Backup sozlamalari
BACKUP_DIR = BASE_DIR / 'backups'
if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)
BACKUP_CENTER_REAUTH_MINUTES = 15

# --- YANGI SOZLAMALAR (Script orqali) ---

# REST FRAMEWORK
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# DRF-SPECTACULAR (Swagger/OpenAPI)
SPECTACULAR_SETTINGS = {
    'TITLE': 'Smart EDU CRM API',
    'DESCRIPTION': "O'quv Markazlari uchun CRM & LMS Tizimi API hujjatlari",
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'TAGS': [
        {'name': 'Autentifikatsiya', 'description': 'Token olish va autentifikatsiya'},
        {'name': 'Foydalanuvchilar', 'description': 'Foydalanuvchilarni boshqarish'},
        {'name': 'Tranzaksiyalar', 'description': "To'lovlar va tranzaksiyalar"},
        {'name': 'Ota-ona', 'description': "Ota-ona paneli - farzandlar, davomat, to'lovlar"},
        {'name': "O'quvchi", 'description': "O'quvchi paneli - darslar, davomat, reyting"},
        {
            'name': 'Hikvision Face ID',
            'description': (
                "Hikvision Face ID qurilmasi bilan integratsiya. "
                "Desktop agent `x-device-token` header orqali user sync, history sync va live event yuboradi."
            ),
        },
    ],
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': False,
        'filter': True,
        'docExpansion': 'list',
        'tagsSorter': 'alpha',
        'operationsSorter': 'alpha',
    },
    'COMPONENT_SPLIT_REQUEST': True,
    'PREPROCESSING_HOOKS': ['apps.api.spectacular_hooks.custom_preprocessing_hook'],
}

# ============================================
# REDIS & CELERY CONFIGURATION
# ============================================
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')
USE_REDIS = config_bool('USE_REDIS', default=False)

# Cache sozlamalari
if USE_REDIS:
    # Redis bilan (production uchun - tezroq)
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            },
            'KEY_PREFIX': 'smartedu',
            'TIMEOUT': 300,  # 5 daqiqa default
        }
    }
    # Session backend - Redis
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'
else:
    # Local memory cache (development uchun - Redis kerak emas)
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'smartedu-cache',
            'TIMEOUT': 300,
        }
    }
    # Default session backend
    SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# Celery sozlamalari
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TIMEZONE = 'Asia/Tashkent'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 daqiqa max
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True

# Celery beat (davriy vazifalar)
CELERY_BEAT_SCHEDULE = {
    # Har kuni soat 9:00 da eslatmalar yuborish
    'send-daily-reminders': {
        'task': 'apps.automation.tasks.send_daily_reminders',
        'schedule': 60 * 60 * 24,  # Har 24 soatda
    },
    'process-scheduled-backups': {
        'task': 'apps.core.tasks.process_scheduled_backups',
        'schedule': 300,
    },
}

# CORS (Mobil ilova uchun)
# ⚠️ Production'da faqat o'z domenlaringizni ruxsat bering!
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True  # Faqat development uchun
else:
    CORS_ALLOWED_ORIGINS = os.getenv(
        'CORS_ALLOWED_ORIGINS',
        'https://app.smartedu.uz,https://admin.smartedu.uz'
    ).split(',')


# OPTIMIZATION: WhiteNoise
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

import mimetypes
mimetypes.add_type('application/javascript', '.js', True)

# STATIC FIX
if DEBUG:
    import os
    STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

# LOGGING
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'errors.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['error_file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'apps': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}

# Logs papkasini yaratish
import os
LOGS_DIR = BASE_DIR / 'logs'
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)


# ========================================
# UNFOLD ADMIN PANEL SOZLAMALARI
# ========================================
from django.templatetags.static import static
from django.urls import reverse_lazy

UNFOLD = {
    "SITE_TITLE": "Smart EDU CRM",
    "SITE_HEADER": "Smart EDU CRM",
    "SITE_SYMBOL": "school",  # Material Symbols icon nomi
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "ENVIRONMENT": "apps.core.admin.environment_callback",
    "DASHBOARD_CALLBACK": "apps.core.admin.dashboard_callback",
    "COLORS": {
        "primary": {
            "50": "250 250 250",
            "100": "244 244 245",
            "200": "228 228 231",
            "300": "212 212 216",
            "400": "161 161 170",
            "500": "24 24 27",
            "600": "39 39 42",
            "700": "63 63 70",
            "800": "82 82 91",
            "900": "113 113 122",
            "950": "9 9 11",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {
                "title": "Boshqaruv",
                "separator": True,
                "items": [
                    {
                        "title": "Dashboard",
                        "icon": "dashboard",
                        "link": reverse_lazy("dashboard"),
                    },
                    {
                        "title": "Foydalanuvchilar",
                        "icon": "people",
                        "link": reverse_lazy("admin:users_user_changelist"),
                    },
                ],
            },
            {
                "title": "Ta'lim",
                "separator": True,
                "items": [
                    {
                        "title": "Guruhlar",
                        "icon": "groups",
                        "link": reverse_lazy("admin:education_group_changelist"),
                    },
                    {
                        "title": "Kurslar",
                        "icon": "book",
                        "link": reverse_lazy("admin:education_course_changelist"),
                    },
                    {
                        "title": "Xonalar",
                        "icon": "meeting_room",
                        "link": reverse_lazy("admin:education_room_changelist"),
                    },
                ],
            },
            {
                "title": "Moliya",
                "separator": True,
                "items": [
                    {
                        "title": "Tranzaksiyalar",
                        "icon": "payments",
                        "link": reverse_lazy("admin:finance_transaction_changelist"),
                    },
                    {
                        "title": "Hisoblar",
                        "icon": "account_balance",
                        "link": reverse_lazy("admin:finance_account_changelist"),
                    },
                ],
            },
            {
                "title": "CRM",
                "separator": True,
                "items": [
                    {
                        "title": "Lidlar",
                        "icon": "funnel",
                        "link": reverse_lazy("admin:crm_lead_changelist"),
                    },
                    {
                        "title": "Bosqichlar",
                        "icon": "view_kanban",
                        "link": reverse_lazy("admin:crm_stage_changelist"),
                    },
                ],
            },
            {
                "title": "Tashkilot",
                "separator": True,
                "items": [
                    {
                        "title": "Tashkilotlar",
                        "icon": "business",
                        "link": reverse_lazy("admin:organizations_organization_changelist"),
                    },
                    {
                        "title": "Filiallar",
                        "icon": "store",
                        "link": reverse_lazy("admin:organizations_branch_changelist"),
                    },
                ],
            },
        ],
    },
}

