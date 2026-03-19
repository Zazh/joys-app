import logging
import time
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

_token_cache = {'token': None, 'expires_at': 0}

# Retry: попытка 1 (сразу) → попытка 2 (сразу) → попытка 3 (через крон) → failed
MAX_IMMEDIATE_ATTEMPTS = 2
RETRY_DELAY_MINUTES = 10


def _get_access_token():
    """Получить OAuth-токен SendPulse (кешируется)."""
    now = time.time()
    if _token_cache['token'] and _token_cache['expires_at'] > now:
        return _token_cache['token']

    try:
        resp = requests.post(
            'https://api.sendpulse.com/oauth/access_token',
            json={
                'grant_type': 'client_credentials',
                'client_id': settings.SENDPULSE_API_ID,
                'client_secret': settings.SENDPULSE_API_SECRET,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        _token_cache['token'] = data['access_token']
        _token_cache['expires_at'] = now + data.get('expires_in', 3600) - 60
        return _token_cache['token']
    except Exception as e:
        logger.error('SendPulse auth failed: %s', e)
        return None


def _send_via_api(to, subject, body):
    """Отправить plain-text письмо через SendPulse SMTP API.

    Returns:
        (success: bool, error: str)
    """
    token = _get_access_token()
    if not token:
        return False, 'SendPulse auth failed — no token'

    try:
        resp = requests.post(
            'https://api.sendpulse.com/smtp/emails',
            headers={'Authorization': f'Bearer {token}'},
            json={
                'email': {
                    'subject': subject,
                    'text': body,
                    'from': {
                        'name': getattr(settings, 'DEFAULT_FROM_NAME', 'DR.JOYS'),
                        'email': settings.DEFAULT_FROM_EMAIL,
                    },
                    'to': [{'email': to}],
                },
            },
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json()

        if result.get('result'):
            logger.info('Email sent: %s → %s (id=%s)', subject[:40], to, result.get('id', ''))
            return True, ''
        else:
            error = str(result)
            logger.error('Email rejected: %s → %s: %s', subject[:40], to, error)
            return False, error
    except Exception as e:
        error = str(e)
        logger.error('Email failed: %s → %s: %s', subject[:40], to, error)
        return False, error


def _get_template(slug):
    """Загрузить EmailTemplate из БД (с учётом текущего языка)."""
    from .models import EmailTemplate
    try:
        return EmailTemplate.objects.get(slug=slug)
    except EmailTemplate.DoesNotExist:
        logger.error('EmailTemplate "%s" not found in DB', slug)
        return None


def _send_email(to, template_slug, context):
    """Основная функция отправки email.

    1. Загружает шаблон из БД
    2. Рендерит subject/body с плейсхолдерами
    3. Отправляет через SendPulse
    4. При ошибке — немедленный retry
    5. При повторной ошибке — сохраняет в EmailLog для крон-retry
    """
    from .models import EmailLog

    template = _get_template(template_slug)
    if not template:
        return

    subject, body = template.render(context)

    # Попытка 1
    ok, error = _send_via_api(to, subject, body)
    if ok:
        EmailLog.objects.create(
            to_email=to,
            template_slug=template_slug,
            subject=subject,
            body=body,
            status=EmailLog.Status.SENT,
            attempts=1,
            sent_at=timezone.now(),
        )
        return

    # Попытка 2 — немедленный retry
    ok, error = _send_via_api(to, subject, body)
    if ok:
        EmailLog.objects.create(
            to_email=to,
            template_slug=template_slug,
            subject=subject,
            body=body,
            status=EmailLog.Status.SENT,
            attempts=2,
            sent_at=timezone.now(),
        )
        return

    # 2 попытки не удались — сохранить для крон-retry
    EmailLog.objects.create(
        to_email=to,
        template_slug=template_slug,
        subject=subject,
        body=body,
        status=EmailLog.Status.RETRY,
        attempts=2,
        next_retry_at=timezone.now() + timedelta(minutes=RETRY_DELAY_MINUTES),
        error=error,
    )
    logger.warning('Email queued for retry: %s → %s', template_slug, to)


def retry_pending_emails():
    """Повторная отправка писем из крона.

    Вызывается management command retry_emails.
    """
    from .models import EmailLog

    now = timezone.now()
    pending = EmailLog.objects.filter(
        status=EmailLog.Status.RETRY,
        next_retry_at__lte=now,
    )

    sent_count = 0
    failed_count = 0

    for log in pending:
        ok, error = _send_via_api(log.to_email, log.subject, log.body)
        log.attempts += 1

        if ok:
            log.status = EmailLog.Status.SENT
            log.sent_at = timezone.now()
            log.next_retry_at = None
            log.save(update_fields=['status', 'sent_at', 'attempts', 'next_retry_at'])
            sent_count += 1
            logger.info('Retry OK: %s → %s (attempt %d)', log.template_slug, log.to_email, log.attempts)
        else:
            # 3-я попытка не удалась — финальный failed
            log.status = EmailLog.Status.FAILED
            log.error = error
            log.next_retry_at = None
            log.save(update_fields=['status', 'error', 'attempts', 'next_retry_at'])
            failed_count += 1
            logger.error(
                'Retry FAILED (giving up): %s → %s after %d attempts: %s',
                log.template_slug, log.to_email, log.attempts, error,
            )

    return sent_count, failed_count


# ─── Публичные функции отправки ───

def send_email_verification(user, url):
    """Письмо подтверждения email."""
    _send_email(
        to=user.email,
        template_slug='email_verify',
        context={
            'user_name': user.get_full_name(),
            'user_email': user.email,
            'verify_url': url,
            'site_url': settings.SITE_URL,
        },
    )


def send_password_reset(user, url):
    """Письмо сброса пароля."""
    _send_email(
        to=user.email,
        template_slug='password_reset',
        context={
            'user_name': user.get_full_name(),
            'user_email': user.email,
            'reset_url': url,
            'site_url': settings.SITE_URL,
        },
    )


def send_welcome_email(user):
    """Приветственное письмо после регистрации."""
    _send_email(
        to=user.email,
        template_slug='welcome',
        context={
            'user_name': user.get_full_name(),
            'user_email': user.email,
            'site_url': settings.SITE_URL,
        },
    )


def send_order_created_email(order):
    """Письмо о создании заказа."""
    items = order.items.all()
    items_text = '\n'.join(
        f'  {item.product_name} ({item.size_name}) x {item.quantity} — '
        f'{item.subtotal:.0f} {order.region.currency_symbol}'
        for item in items
    )
    _send_email(
        to=order.customer_email,
        template_slug='order_created',
        context={
            'order_number': order.number,
            'order_date': order.created_at.strftime('%d.%m.%Y %H:%M'),
            'order_total': f'{order.total_amount:.0f}',
            'currency': order.region.currency_symbol,
            'customer_name': order.customer_name,
            'items_text': items_text,
            'delivery_address': f'{order.city}, {order.address}',
            'payment_url': order.payment_url or '',
            'site_url': settings.SITE_URL,
        },
    )


def send_payment_confirmed_email(order):
    """Письмо о подтверждении оплаты."""
    items = order.items.all()
    items_text = '\n'.join(
        f'  {item.product_name} ({item.size_name}) x {item.quantity} — '
        f'{item.subtotal:.0f} {order.region.currency_symbol}'
        for item in items
    )
    _send_email(
        to=order.customer_email,
        template_slug='order_paid',
        context={
            'order_number': order.number,
            'order_date': order.created_at.strftime('%d.%m.%Y %H:%M'),
            'order_total': f'{order.total_amount:.0f}',
            'currency': order.region.currency_symbol,
            'customer_name': order.customer_name,
            'items_text': items_text,
            'delivery_address': f'{order.city}, {order.address}',
            'site_url': settings.SITE_URL,
        },
    )


def send_order_shipped_email(order):
    """Письмо об отправке заказа."""
    _send_email(
        to=order.customer_email,
        template_slug='order_shipped',
        context={
            'order_number': order.number,
            'tracking_number': order.tracking_number if hasattr(order, 'tracking_number') else '',
            'customer_name': order.customer_name,
            'site_url': settings.SITE_URL,
        },
    )


def send_staff_invite(user, password):
    """Письмо с доступом к бэкофису для нового сотрудника."""
    role_display = dict(user.Role.choices).get(user.role, user.role)
    _send_email(
        to=user.email,
        template_slug='staff_invite',
        context={
            'user_name': user.get_full_name() or user.email,
            'user_email': user.email,
            'password': password,
            'role': role_display,
            'login_url': f'{settings.SITE_URL}/backoffice/login/',
            'site_url': settings.SITE_URL,
        },
    )


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
