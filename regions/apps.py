from django.apps import AppConfig


class RegionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'regions'
    verbose_name = 'Регионы'

    def ready(self):
        # Правку региона в админке видно сразу, а не через 10 минут жизни кеша
        # (образец — pages/apps.py)
        from django.core.cache import cache
        from django.db.models.signals import post_delete, post_save

        from .context_processors import ALL_REGIONS_CACHE_KEY
        from .middleware import DEFAULT_CACHE_KEY, region_cache_key
        from .models import Region

        def _clear_region_cache(instance, **kwargs):
            # Ключи перечисляем поимённо: шаблонного удаления в LocMem нет
            cache.delete_many([
                ALL_REGIONS_CACHE_KEY,
                DEFAULT_CACHE_KEY,
                region_cache_key(instance.code),
            ])

        post_save.connect(_clear_region_cache, sender=Region, weak=False)
        post_delete.connect(_clear_region_cache, sender=Region, weak=False)
