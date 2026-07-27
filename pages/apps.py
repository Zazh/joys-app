from django.apps import AppConfig


class PagesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pages'
    verbose_name = 'Страницы'

    def ready(self):
        from core.image_utils import connect_signals
        connect_signals()

        # Сброс кеша навигации при изменении меню/страниц в админке
        from django.core.cache import cache
        from django.db.models.signals import post_delete, post_save
        from .models import MenuItem, Page, PageCategory

        def _clear_nav_cache(**kwargs):
            cache.delete('navigation_data')

        for model in (MenuItem, Page, PageCategory):
            post_save.connect(_clear_nav_cache, sender=model, weak=False)
            post_delete.connect(_clear_nav_cache, sender=model, weak=False)
