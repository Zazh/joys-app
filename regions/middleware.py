import re

from django.core.cache import cache

from .models import Region

CACHE_TTL = 600
DEFAULT_CACHE_KEY = 'region:default'

# Сентинел «региона с таким кодом нет»: cache.get_or_set не кеширует None,
# и без него каждый запрос с битым cookie шёл бы в БД
NOT_FOUND = ''

# Код региона приходит из cookie, то есть из чужих рук, а становится частью
# ключа кеша. Пять символов — max_length поля, набор символов — чтобы в ключ
# не уехали пробелы и переводы строк. Всё остальное считаем неизвестным
# регионом, как и раньше считала выборка из БД.
_CODE_RE = re.compile(r'[\w-]{1,5}\Z', re.ASCII)


def region_cache_key(code):
    return f'region:{code}'


def _load_region(code):
    region = Region.objects.filter(code=code, is_active=True).first()
    return region if region else NOT_FOUND


def get_region(code):
    """Активный регион по коду — из общего кеша. None, если такого нет."""
    if not _CODE_RE.match(code):
        return None
    region = cache.get_or_set(
        region_cache_key(code), lambda: _load_region(code), CACHE_TTL,
    )
    return region or None


def get_default_region():
    region = cache.get_or_set(
        DEFAULT_CACHE_KEY, lambda: Region.get_default() or NOT_FOUND, CACHE_TTL,
    )
    return region or None


class RegionMiddleware:
    """
    Читает регион из cookie 'drjoys_region'.
    Устанавливает request.region, request.region_code, request.show_region_modal.

    Кеш — общий (`django.core.cache`), а не словарь в памяти воркера: тот жил
    до рестарта, и правка региона в админке доезжала до покупателей вразнобой.
    Сбрасывают его сигналы в `RegionsConfig.ready()`, TTL здесь — страховка.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        region_code = request.COOKIES.get('drjoys_region')

        if region_code:
            region = get_region(region_code)
            show_modal = region is None
            if not region:
                region = get_default_region()
        else:
            region = get_default_region()
            show_modal = True

        request.region = region
        request.region_code = region.code if region else 'kz'
        request.show_region_modal = show_modal

        return self.get_response(request)
