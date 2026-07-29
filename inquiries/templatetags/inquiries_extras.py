from django import template

from ..antispam import HONEYPOT_FIELD, TIMESTAMP_FIELD, make_timestamp_token

register = template.Library()


@register.inclusion_tag('inquiries/_antispam_fields.html')
def inquiry_antispam():
    """Скрытые поля антиспама — ставить внутрь каждой формы заявки."""
    return {
        'honeypot_field': HONEYPOT_FIELD,
        'timestamp_field': TIMESTAMP_FIELD,
        'timestamp_token': make_timestamp_token(),
    }
