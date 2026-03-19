import logging

from django.conf import settings

from orders.emails import _send_via_api

logger = logging.getLogger(__name__)


def send_inquiry_notification(submission):
    """Уведомление администратору о новой заявке (plain text)."""
    form = submission.form
    if not form.email_notify_to:
        return

    fields_text = '\n'.join(
        f'  {fv.field.label}: {fv.display_value}'
        for fv in submission.values.select_related('field').order_by('field__order')
    )

    subject = f'Новая заявка: {form.title}'
    body = (
        f'Новая заявка: {form.title}\n\n'
        f'{fields_text}\n\n'
        f'IP: {submission.ip_address}\n'
        f'Дата: {submission.created_at.strftime("%d.%m.%Y %H:%M")}\n'
    )

    ok, error = _send_via_api(form.email_notify_to, subject, body)
    if not ok:
        logger.error('Inquiry notification failed: %s — %s', form.email_notify_to, error)
