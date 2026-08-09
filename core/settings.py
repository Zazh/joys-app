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

# Прод отдаётся только по HTTPS (redirect 80→443 в nginx), поэтому куки
# помечаем Secure и включаем HSTS. В DEBUG не трогаем — иначе локальный
# http://localhost:8009 перестанет логинить.
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 год
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

INSTALLED_APPS = [
    'modeltranslation',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.sitemaps',
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
    'core',  # общие теги/утилиты (templatetags/sanitize.py)
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
    'core.middleware.PerformanceMiddleware',
    'core.middleware.ContentSecurityPolicyMiddleware',
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
                'pages.context_processors.contacts',
                'core.context_processors.analytics',
                'core.context_processors.seo',
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
        # Переиспользуем соединения между запросами вместо TCP+auth на каждый
        'CONN_MAX_AGE': 60,
        'CONN_HEALTH_CHECKS': True,
    }
}

# Cache: Redis если задан REDIS_URL, иначе LocMem (только dev/fallback —
# LocMem не шарится между gunicorn-воркерами)
REDIS_URL = os.environ.get('REDIS_URL', '')

if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'drjoys-cache',
        }
    }

# БД для тестов Django заводит свою, а кеш взял бы боевой — и прогон тестов
# затирал бы общий Redis данными из пустой тестовой базы (см. core/test_runner.py)
TEST_RUNNER = 'core.test_runner.IsolatedCacheRunner'

# Сессии: кеш поверх БД — SELECT django_session только при промахе кеша
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'

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

# Все загружаемые файлы получают латинские имена (core/storage.py)
STORAGES = {
    'default': {'BACKEND': 'core.storage.TranslitFileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}

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
# Выключатель эквайринга: боевого токена у Халыка ещё нет, а дефолтные URL ниже —
# тестовый контур, и без флага покупатель улетал бы «оплачивать» в песочницу.
# Пока false — заказ КЗ падает менеджеру заявкой без онлайн-оплаты (get_gateway
# отдаёт None). Появится токен: боевые креды в .env + HALYK_ENABLED=true.
HALYK_ENABLED = os.environ.get('HALYK_ENABLED', '').lower() == 'true'
HALYK_OAUTH_URL = os.environ.get('HALYK_OAUTH_URL', 'https://test-epay-oauth.epayment.kz/oauth2/token')
HALYK_PAYMENT_URL = os.environ.get('HALYK_PAYMENT_URL', 'https://test-epay.epayment.kz/')
HALYK_CLIENT_ID = os.environ.get('HALYK_CLIENT_ID', '')
HALYK_CLIENT_SECRET = os.environ.get('HALYK_CLIENT_SECRET', '')
HALYK_TERMINAL_ID = os.environ.get('HALYK_TERMINAL_ID', '')
# PEM-ключ для проверки подписи postLink. Выдаётся банком вместе с боевым
# терминалом. Пока пусто — callback от Halyk отклоняется (иначе оплату
# можно подтвердить обычным POST-запросом со стороны).
HALYK_CALLBACK_PUBLIC_KEY = os.environ.get('HALYK_CALLBACK_PUBLIC_KEY', '').replace('\\n', '\n')

# Base URL для платёжных callback-ов (в dev — пустая, в prod — https://dr-joys.com)
PAYMENT_BASE_URL = os.environ.get('PAYMENT_BASE_URL', '')

# Базовый URL сайта для ссылок в email, редиректов и т.д.
# dev: http://localhost:8009, staging: https://app.dr-joys.com, prod: https://dr-joys.com
# Он же — единственный источник домена для canonical, hreflang, sitemap.xml,
# robots.txt и llms.txt (core/seo.py): переезд на боевой домен = правка этой
# строки в .env, ничего больше менять не нужно.
SITE_URL = os.environ.get('SITE_URL', 'http://localhost:8009')

# Открыт ли сайт поисковикам. False → robots.txt закрывает всё и в <head>
# уходит noindex. Ставить False на staging/превью: копия каталога на
# техническом домене в индексе — это дубли боевых страниц.
# Дефолт «открыт на проде, закрыт локально»: забытый флаг на staging стоит
# дешевле, чем случайно выпавший из индекса боевой сайт.
SITE_INDEXABLE = os.environ.get('SITE_INDEXABLE', str(not DEBUG)).lower() == 'true'

# Секретный URL админки — обязательно задать в .env
ADMIN_URL = os.environ['ADMIN_URL']

# Wildberries API
WB_API_TOKEN = os.environ.get('WB_API_TOKEN', '')

# Google Analytics 4 — счётчик подключается в base.html только если ID задан
GA_MEASUREMENT_ID = os.environ.get('GA_MEASUREMENT_ID', '')

# Подтверждение владения в Google Search Console — content из HTML-тега
# подтверждения; тег выводится в <head> только если значение задано
GOOGLE_SITE_VERIFICATION = os.environ.get('GOOGLE_SITE_VERIFICATION', '')

# CSP: пока только собираем нарушения в консоль браузера. После проверки,
# что ничего не ломается, поставить CSP_REPORT_ONLY=false — политика
# начнёт реально блокировать посторонние скрипты.
CSP_REPORT_ONLY = os.environ.get('CSP_REPORT_ONLY', 'true').lower() == 'true'

# -----------------------------------------------
# django-allauth (SSO: Google, Yandex)
# -----------------------------------------------
SITE_ID = 1

# Allauth account settings — мы используем свои views для email login/register
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {'email'}
# Заменяет устаревшие ACCOUNT_EMAIL_REQUIRED / ACCOUNT_USERNAME_REQUIRED
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']

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