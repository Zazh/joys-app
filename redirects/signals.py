from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import Redirect
from .middleware import CACHE_KEY


@receiver([post_save, post_delete], sender=Redirect)
def clear_redirects_cache(sender, **kwargs):
    cache.delete(CACHE_KEY)
