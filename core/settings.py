import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ['SECRET_KEY']
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
ALLOWED_HOSTS = os.environ['ALLOWED_HOSTS'].split(',')

CSRF_TRUSTED_ORIGINS = [
    'https://dr-joys.com',
    'https://www.dr-joys.com',
    'https://app.dr-joys.com',
]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

INSTALLED_APPS = [
    'modeltranslation',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    # allauth
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.yandex',
    # DRF
    'rest_framework',
    'drf_spectacular',
    # Project apps
    'regions',
    'catalog',
    'orders',
    'pages',
    'emails',
    'accounts',
    'modals',
    'quiz',
    'inquiries',
    'reviews',
    'redirects',
    'qrcodes',
    'backoffice',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'redirects.middleware.RedirectMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'regions.middleware.RegionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'accounts.middleware.TrackUserActivityMiddleware',
    'backoffice.admin_ratelimit.AdminLoginRateLimitMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.template.context_processors.i18n',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'catalog.context_processors.placeholder_image',
                'catalog.context_processors.global_jsonld',
                'regions.context_processors.region_context',
                'orders.context_processors.cart_context',
                'backoffice.context_processors.backoffice_badges',
                'pages.context_processors.navigation',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['DB_NAME'],
        'USER': os.environ['DB_USER'],
        'PASSWORD': os.environ['DB_PASSWORD'],
        'HOST': os.environ['DB_HOST'],
        'PORT': os.environ['DB_PORT'],
    }
}

# Cache — используется для rate limiting
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'drjoys-cache',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'ru'
LANGUAGES = [
    ('ru', 'Русский'),
    ('kk', 'Қазақша'),
    ('en', 'English'),
]
LOCALE_PATHS = [BASE_DIR / 'locale']
MODELTRANSLATION_DEFAULT_LANGUAGE = 'ru'
MODELTRANSLATION_FALLBACK_LANGUAGES = ('ru',)
TIME_ZONE = 'Asia/Almaty'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'accounts.User'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Email — SendPulse API
SENDPULSE_API_ID = os.environ.get('SENDPULSE_API_ID', '')
SENDPULSE_API_SECRET = os.environ.get('SENDPULSE_API_SECRET', '')
DEFAULT_FROM_EMAIL = 'info@dr-joys.com'
DEFAULT_FROM_NAME = 'DR.JOYS'

# VTB Payment Gateway (Россия)
VTB_PAYMENT_URL = os.environ.get('VTB_PAYMENT_URL', 'https://vtbkz.rbsuat.com/payment/rest/')
VTB_USERNAME = os.environ.get('VTB_USERNAME', '')
VTB_PASSWORD = os.environ.get('VTB_PASSWORD', '')

# Halyk ePay (Казахстан)
HALYK_OAUTH_URL = os.environ.get('HALYK_OAUTH_URL', 'https://test-epay-oauth.epayment.kz/oauth2/token')
HALYK_PAYMENT_URL = os.environ.get('HALYK_PAYMENT_URL', 'https://test-epay.epayment.kz/')
HALYK_CLIENT_ID = os.environ.get('HALYK_CLIENT_ID', '')
HALYK_CLIENT_SECRET = os.environ.get('HALYK_CLIENT_SECRET', '')
HALYK_TERMINAL_ID = os.environ.get('HALYK_TERMINAL_ID', '')

# Base URL для платёжных callback-ов (в dev — пустая, в prod — https://dr-joys.com)
PAYMENT_BASE_URL = os.environ.get('PAYMENT_BASE_URL', '')

# Базовый URL сайта для ссылок в email, редиректов и т.д.
# dev: http://localhost:8009, staging: https://app.dr-joys.com, prod: https://dr-joys.com
SITE_URL = os.environ.get('SITE_URL', 'http://localhost:8009')

# Секретный URL админки — обязательно задать в .env
ADMIN_URL = os.environ['ADMIN_URL']

# Wildberries API
WB_API_TOKEN = os.environ.get('WB_API_TOKEN', '')

# -----------------------------------------------
# django-allauth (SSO: Google, Yandex)
# -----------------------------------------------
SITE_ID = 1

# Allauth account settings — мы используем свои views для email login/register
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_LOGIN_METHODS = {'email'}

# SSO: авто-мёрж аккаунтов по email
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_STORE_TOKENS = False

# Кастомные адаптеры — redirect SSO popup → callback страницу
ACCOUNT_ADAPTER = 'accounts.adapter.AccountAdapter'
SOCIALACCOUNT_ADAPTER = 'accounts.adapter.SocialAccountAdapter'

# Провайдеры — credentials из .env
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': os.environ.get('GOOGLE_CLIENT_ID', ''),
            'secret': os.environ.get('GOOGLE_CLIENT_SECRET', ''),
        },
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    },
    'yandex': {
        'APP': {
            'client_id': os.environ.get('YANDEX_CLIENT_ID', ''),
            'secret': os.environ.get('YANDEX_CLIENT_SECRET', ''),
        },
    },
}

# -----------------------------------------------
# Django REST Framework
# -----------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

# -----------------------------------------------
# Django Silk — профилирование запросов
# Включается через SILK_ENABLED=true в .env
# -----------------------------------------------
SILK_ENABLED = os.environ.get('SILK_ENABLED', 'false').lower() == 'true'

if SILK_ENABLED:
    INSTALLED_APPS.append('silk')
    # Silk middleware ставим после SessionMiddleware, но до views
    MIDDLEWARE.insert(
        MIDDLEWARE.index('django.middleware.common.CommonMiddleware'),
        'silk.middleware.SilkyMiddleware',
    )
    SILKY_PYTHON_PROFILER = True
    SILKY_PYTHON_PROFILER_BINARY = True
    SILKY_MAX_RECORDED_REQUESTS = 10_000
    SILKY_MAX_RECORDED_REQUESTS_CHECK_PERCENT = 10
    SILKY_AUTHENTICATION = True   # только залогиненные
    SILKY_AUTHORISATION = True    # только is_staff

SPECTACULAR_SETTINGS = {
    'TITLE': 'DR.JOYS API',
    'DESCRIPTION': 'API для e-commerce платформы DR.JOYS',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SCHEMA_PATH_PREFIX': r'/',
}