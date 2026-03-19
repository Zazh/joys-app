from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from pages.views import HomeView

# Без языкового префикса
urlpatterns = [
    path('admin/', admin.site.urls),
    path('region/', include('regions.urls')),
    path('orders/', include('orders.urls')),
    path('accounts/', include('allauth.urls')),  # OAuth callbacks — без языкового префикса
    # API
    path('api/inquiries/', include('inquiries.urls')),
    path('api/modals/', include('modals.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
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

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
