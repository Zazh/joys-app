from django.core.cache import cache

from pages.models import MenuItem, PageCategory

NAV_CACHE_KEY = 'navigation_data'


def _build_navigation():
    main_menu = list(
        MenuItem.objects
        .filter(is_active=True)
        .select_related('page', 'page_category')
        .order_by('order')
    )
    try:
        legal_pages = list(
            PageCategory.objects.get(slug='legal')
            .pages.filter(is_published=True)
            .order_by('order', 'title')
        )
    except PageCategory.DoesNotExist:
        legal_pages = []

    return {
        'main_menu': main_menu,
        'legal_pages': legal_pages,
    }


def navigation(request):
    """Меню + legal pages — кеш 10 минут, сброс по сигналам в pages.apps."""
    return cache.get_or_set(NAV_CACHE_KEY, _build_navigation, 600)
