from django.conf import settings
from django.http import HttpResponsePermanentRedirect, HttpResponseRedirect
from django.core.cache import cache

from .models import Redirect

CACHE_KEY = 'redirects_map'
CACHE_TIMEOUT = 60 * 15  # 15 минут

# 301 без заголовков браузер запоминает бессрочно, и ошибка в записи
# прилипает в кешах посетителей навсегда; час — потолок жизни ошибки.
# На 302 заголовок не ставим: его не кешируют, правки применяются сразу.
PERMANENT_CACHE_CONTROL = 'max-age=3600'


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


def _slash_alt(path):
    return path[:-1] if path.endswith('/') else path + '/'


def _strip_language_prefix(path):
    """Путь без языкового префикса или None, если префикса нет.

    Middleware стоит до LocaleMiddleware и сверяет сырой request.path,
    поэтому запись `/foo/` сама по себе не ловит `/ru/foo/` — а легаси-трафик
    (QR, печать) бьётся именно в префиксные варианты.
    """
    for code, _name in settings.LANGUAGES:
        prefix = f'/{code}/'
        if path.startswith(prefix):
            return path[len(prefix) - 1:]
        if path == f'/{code}':
            return '/'
    return None


class RedirectMiddleware:
    """Middleware для обработки редиректов из БД."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        redirects_map = get_redirects_map()
        path = request.path

        # Порядок приоритета: точное совпадение → слэш-вариант →
        # то же без языкового префикса. Запись со слэшем ловит путь без
        # слэша и наоборот. `/` и голый префикс (`/ru/`) в фолбэки не идут:
        # запись для `/` не должна перехватывать все языковые главные.
        candidates = [path]
        if path != '/':
            candidates.append(_slash_alt(path))
        stripped = _strip_language_prefix(path)
        if stripped is not None and stripped != '/':
            candidates.append(stripped)
            candidates.append(_slash_alt(stripped))

        target = None
        for candidate in candidates:
            target = redirects_map.get(candidate)
            if target is not None:
                break

        if target is not None:
            destination, redirect_type = target
            if redirect_type == 301:
                response = HttpResponsePermanentRedirect(destination)
                response['Cache-Control'] = PERMANENT_CACHE_CONTROL
                return response
            return HttpResponseRedirect(destination)

        return self.get_response(request)
