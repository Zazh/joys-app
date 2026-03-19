from django import template
from django.utils.safestring import mark_safe

register = template.Library()

STATUS_COLORS = {
    'pending': ('bg-yellow-100 text-yellow-800', 'Ожидает'),
    'paid': ('bg-green-100 text-green-800', 'Оплачен'),
    'shipped': ('bg-blue-100 text-blue-800', 'Отправлен'),
    'delivered': ('bg-emerald-100 text-emerald-800', 'Доставлен'),
    'cancelled': ('bg-red-100 text-red-800', 'Отменён'),
    'expired': ('bg-stone-100 text-stone-600', 'Истёк'),
}


@register.filter
def status_badge(status):
    css, label = STATUS_COLORS.get(status, ('bg-stone-100 text-stone-600', status))
    return mark_safe(f'<span class="inline-block px-2 py-0.5 rounded-full text-xs font-medium {css}">{label}</span>')


@register.filter
def status_label(status):
    _, label = STATUS_COLORS.get(status, ('', status))
    return label
