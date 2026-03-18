from django.http import HttpResponsePermanentRedirect, HttpResponseRedirect
from django.core.cache import cache

from .models import Redirect

CACHE_KEY = 'redirects_map'
CACHE_TIMEOUT = 60 * 15  # 15 минут


def get_redirects_map():
    """Получить словарь редиректов из кеша или БД."""
    redirects_map = cache.get(CACHE_KEY)
    if redirects_map is None:
        redirects_map = {
            r.path: (r.destination, r.redirect_type)
            for r in Redirect.objects.filter(is_active=True)
        }
        cache.set(CACHE_KEY, redirects_map, CACHE_TIMEOUT)
    return redirects_map


class RedirectMiddleware:
    """Middleware для обработки редиректов из БД."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        redirects_map = get_redirects_map()
        path = request.path

        if path in redirects_map:
            destination, redirect_type = redirects_map[path]
            if redirect_type == 301:
                return HttpResponsePermanentRedirect(destination)
            return HttpResponseRedirect(destination)

        return self.get_response(request)
