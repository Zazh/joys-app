from django.core.cache import cache

from pages.models import ContactSettings, MenuItem, PageCategory

NAV_CACHE_KEY = 'navigation_data'
CONTACTS_CACHE_KEY = 'contact_settings'


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


def get_contacts():
    """Контакты компании из кеша — футер рисуется на каждой странице, кеш 10 минут.

    В кеш кладём сам объект, а не отрендеренные строки: переводимые поля
    modeltranslation отдаёт по активному языку в момент обращения, а кеш
    один на все языки — иначе на /kk/ и /en/ проступит русский.

    Отдельно от контекст-процессора: JSON-LD собирается во view, до рендера
    шаблона, и должен ходить в тот же кеш, а не делать второй запрос.
    """
    return cache.get_or_set(CONTACTS_CACHE_KEY, ContactSettings.load, 600)


def contacts(request):
    return {'contacts': get_contacts()}
