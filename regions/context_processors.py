from .models import Region


def region_context(request):
    """Добавляет данные региона во все шаблоны."""
    region = getattr(request, 'region', None)
    return {
        'current_region': region,
        'region_code': getattr(request, 'region_code', 'kz'),
        'currency_symbol': region.currency_symbol if region else '\u20b8',
        'currency_code': region.currency_code if region else 'KZT',
        'payment_currency_symbol': region.payment_currency_symbol if region and region.needs_conversion else '',
        'needs_conversion': region.needs_conversion if region else False,
        'show_region_modal': getattr(request, 'show_region_modal', False),
        'all_regions': Region.objects.filter(is_active=True),
    }
