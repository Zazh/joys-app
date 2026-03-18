import logging

from django.conf import settings

from orders.emails import _send

logger = logging.getLogger(__name__)


def send_inquiry_notification(submission):
    """Уведомление администратору о новой заявке."""
    form = submission.form
    if not form.email_notify_to:
        return

    fields_data = []
    for fv in submission.values.select_related('field').order_by('field__order'):
        fields_data.append({
            'label': fv.field.label,
            'value': fv.display_value,
        })

    _send(
        to=form.email_notify_to,
        subject=f'Новая заявка: {form.title}',
        template='inquiry_notification',
        context={
            'form_title': form.title,
            'fields': fields_data,
            'ip_address': submission.ip_address,
            'created_at': submission.created_at,
            'site_url': settings.PAYMENT_BASE_URL or 'https://dr-joys.com',
        },
    )
