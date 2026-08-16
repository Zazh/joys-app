from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.templatetags.static import static as static_url
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from core.decorators import staff_only_404
from core.seo import llms_txt, robots_txt
from core.sitemaps import SITEMAPS
from pages.views import HomeView


# Без языкового префикса
urlpatterns = [
    path(f'{settings.ADMIN_URL}/', admin.site.urls),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('llms.txt', llms_txt, name='llms_txt'),
    # Браузеры и робот Яндекса дёргают /favicon.ico напрямую, минуя <link>
    path(
        'favicon.ico',
        RedirectView.as_view(
            url=static_url('dist/images/favicon/favicon.ico'), permanent=True,
        ),
    ),
    # Одним файлом: адресов на порядки меньше лимита в 50 000, индекс из
    # нескольких карт только добавил бы роботу лишний переход.
    path('sitemap.xml', sitemap, {'sitemaps': SITEMAPS}, name='django.contrib.sitemaps.views.sitemap'),
    path('region/', include('regions.urls')),
    path('i18n/', include('django.conf.urls.i18n')),  # set_language для страниц вне i18n-префикса
    path('orders/', include('orders.urls')),
    path('accounts/', include('allauth.urls')),  # OAuth callbacks — без языкового префикса
    # API
    path('api/inquiries/', include('inquiries.urls')),
    path('api/modals/', include('modals.urls')),
    # API — внутренняя, схема и Swagger только для персонала:
    # публичная схема раздаёт карту всех эндпоинтов и параметров
    path('api/schema/', staff_only_404(SpectacularAPIView.as_view()), name='schema'),
    path(
        'api/docs/',
        staff_only_404(SpectacularSwaggerView.as_view(url_name='schema')),
        name='swagger-ui',
    ),
    path('qrcodes/', include('qrcodes.urls')),
    path('backoffice/', include('backoffice.urls')),
]

# С языковым префиксом (/ru/, /kk/, /en/)
urlpatterns += i18n_patterns(
    path('accounts/', include('accounts.urls')),
    path('catalog/', include('catalog.urls')),
    path('quiz/', include('quiz.urls')),
    path('', HomeView.as_view(), name='home'),
    path('', include('pages.urls')),
    prefix_default_language=True,
)

if getattr(settings, 'SILK_ENABLED', False):
    urlpatterns += [path('silk/', include('silk.urls', namespace='silk'))]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
