from django.apps import AppConfig


class PagesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pages'
    verbose_name = 'Страницы'

    def ready(self):
        from core.image_utils import connect_signals
        connect_signals()

        # Правку в админке и бэкофисе видно сразу, а не через 10 минут жизни кеша
        from django.core.cache import cache
        from django.db.models.signals import post_delete, post_save

        from .context_processors import CONTACTS_CACHE_KEY, NAV_CACHE_KEY
        from .models import ContactSettings, MenuItem, Page, PageCategory

        def _clear_nav_cache(**kwargs):
            cache.delete(NAV_CACHE_KEY)

        for model in (MenuItem, Page, PageCategory):
            post_save.connect(_clear_nav_cache, sender=model, weak=False)
            post_delete.connect(_clear_nav_cache, sender=model, weak=False)

        def _clear_contacts_cache(**kwargs):
            cache.delete(CONTACTS_CACHE_KEY)

        post_save.connect(_clear_contacts_cache, sender=ContactSettings, weak=False)
        post_delete.connect(_clear_contacts_cache, sender=ContactSettings, weak=False)
