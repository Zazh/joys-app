from pages.models import MenuItem, PageCategory


def navigation(request):
    """Меню + legal pages — один раз для header и footer."""
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
