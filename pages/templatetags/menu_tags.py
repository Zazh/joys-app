from django import template

from pages.models import MenuItem, PageCategory, PromoBlock

register = template.Library()


@register.simple_tag
def get_menu():
    """Получить активные пункты меню."""
    return list(
        MenuItem.objects
        .filter(is_active=True)
        .select_related('page', 'page_category')
        .order_by('order')
    )


@register.simple_tag
def get_category_pages(slug):
    """Получить опубликованные страницы категории по slug."""
    try:
        category = PageCategory.objects.get(slug=slug)
        return list(category.pages.filter(is_published=True).order_by('order', 'title'))
    except PageCategory.DoesNotExist:
        return []


@register.simple_tag
def get_promo(slug):
    """Получить активный промо-блок по slug."""
    try:
        return PromoBlock.objects.prefetch_related('images').get(slug=slug, is_active=True)
    except PromoBlock.DoesNotExist:
        return None
