from django.apps import AppConfig


class PagesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pages'
    verbose_name = 'Страницы'

    def ready(self):
        from core.image_utils import connect_signals
        connect_signals()
