"""Тесты email-инфраструктуры: SendPulse API, retry-логика, шаблоны, публичные функции."""

import time
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from catalog.models import Category, Product, ProductSize, Stock
from emails.models import EmailTemplate, EmailLog
from orders.models import Order, OrderItem
from regions.models import Region


# ─── Фикстуры ───

class EmailTestBase(TestCase):
    """Базовый класс с фикстурами для email-тестов."""

    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(
            code='kz', name='Казахстан',
            currency_code='KZT', currency_symbol='₸',
            payment_gateway='halyk', is_default=True,
        )
        cls.user = User.objects.create_user(
            email='test@example.com', password='test12345',
            first_name='Тест', last_name='Тестов',
        )
        cls.category = Category.objects.create(name='Презервативы', slug='condoms')
        cls.product = Product.objects.create(
            name='DR.JOYS классические', slug='classic',
            category=cls.category, pack_quantity=5,
        )
        cls.size_m = ProductSize.objects.create(
            product=cls.product, name='M', sku='DJ-CL-M', price=Decimal('2500'),
        )

    def _create_order(self, **kwargs):
        defaults = dict(
            region=self.region,
            user=self.user,
            customer_name='Тест Тестов',
            customer_phone='+77001234567',
            customer_email='test@example.com',
            city='Алматы',
            address='ул. Абая 1',
            total_amount=Decimal('5000'),
            status=Order.Status.PAID,
            expires_at=timezone.now() + timedelta(minutes=30),
        )
        defaults.update(kwargs)
        order = Order.objects.create(**defaults)
        OrderItem.objects.create(
            order=order,
            size=self.size_m,
            product_name='DR.JOYS классические',
            size_name='M',
            quantity=2,
            price=Decimal('2500'),
        )
        return order

    def _create_template(self, slug, subject='Тема: {order_number}', body='Текст: {user_name}'):
        return EmailTemplate.objects.create(slug=slug, subject=subject, body=body)


# ─── EmailTemplate.render() ───

class EmailTemplateRenderTest(TestCase):
    """Тесты рендеринга шаблонов email."""

    def test_render_with_all_placeholders(self):
        tpl = EmailTemplate.objects.create(
            slug='test_tpl',
            subject='Заказ #{order_number}',
            body='Здравствуйте, {user_name}! Ваш заказ #{order_number} принят.',
        )
        subject, body = tpl.render({'order_number': '00123', 'user_name': 'Иван'})

        self.assertEqual(subject, 'Заказ #00123')
        self.assertIn('Иван', body)
        self.assertIn('00123', body)

    def test_render_missing_placeholder_preserved(self):
        """Отсутствующий плейсхолдер остаётся как {key}."""
        tpl = EmailTemplate.objects.create(
            slug='test_missing',
            subject='{greeting}, {user_name}!',
            body='Текст',
        )
        subject, _ = tpl.render({'user_name': 'Алия'})

        self.assertEqual(subject, '{greeting}, Алия!')

    def test_render_empty_context(self):
        tpl = EmailTemplate.objects.create(
            slug='test_empty',
            subject='Без плейсхолдеров',
            body='Просто текст',
        )
        subject, body = tpl.render({})

        self.assertEqual(subject, 'Без плейсхолдеров')
        self.assertEqual(body, 'Просто текст')


# ─── _get_access_token() ───

class GetAccessTokenTest(TestCase):
    """Тесты получения OAuth-токена SendPulse."""

    def setUp(self):
        from emails.service import _token_cache
        _token_cache['token'] = None
        _token_cache['expires_at'] = 0

    @override_settings(SENDPULSE_API_ID='test-id', SENDPULSE_API_SECRET='test-secret')
    @patch('emails.service.requests.post')
    def test_successful_auth(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'access_token': 'abc123', 'expires_in': 3600}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        from emails.service import _get_access_token
        token = _get_access_token()

        self.assertEqual(token, 'abc123')
        mock_post.assert_called_once()

    @override_settings(SENDPULSE_API_ID='test-id', SENDPULSE_API_SECRET='test-secret')
    @patch('emails.service.requests.post')
    def test_token_cached(self, mock_post):
        """Второй вызов использует кешированный токен."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'access_token': 'cached-token', 'expires_in': 3600}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        from emails.service import _get_access_token
        _get_access_token()
        _get_access_token()

        self.assertEqual(mock_post.call_count, 1)

    @override_settings(SENDPULSE_API_ID='test-id', SENDPULSE_API_SECRET='test-secret')
    @patch('emails.service.requests.post')
    def test_auth_failure_returns_none(self, mock_post):
        mock_post.side_effect = Exception('Connection error')

        from emails.service import _get_access_token
        token = _get_access_token()

        self.assertIsNone(token)


# ─── _send_via_api() ───

class SendViaApiTest(TestCase):
    """Тесты отправки через SendPulse SMTP API."""

    @patch('emails.service._get_access_token', return_value='test-token')
    @patch('emails.service.requests.post')
    def test_successful_send(self, mock_post, mock_token):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'result': True, 'id': 'msg-123'}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        from emails.service import _send_via_api
        ok, error = _send_via_api('user@example.com', 'Тема', 'Текст')

        self.assertTrue(ok)
        self.assertEqual(error, '')

    @patch('emails.service._get_access_token', return_value='test-token')
    @patch('emails.service.requests.post')
    def test_api_rejection(self, mock_post, mock_token):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'result': False, 'message': 'Invalid email'}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        from emails.service import _send_via_api
        ok, error = _send_via_api('bad@example.com', 'Тема', 'Текст')

        self.assertFalse(ok)
        self.assertIn('Invalid email', error)

    @patch('emails.service._get_access_token', return_value=None)
    def test_no_token_returns_error(self, mock_token):
        from emails.service import _send_via_api
        ok, error = _send_via_api('user@example.com', 'Тема', 'Текст')

        self.assertFalse(ok)
        self.assertIn('no token', error)

    @patch('emails.service._get_access_token', return_value='test-token')
    @patch('emails.service.requests.post', side_effect=Exception('Timeout'))
    def test_network_error(self, mock_post, mock_token):
        from emails.service import _send_via_api
        ok, error = _send_via_api('user@example.com', 'Тема', 'Текст')

        self.assertFalse(ok)
        self.assertIn('Timeout', error)


# ─── _send_email() — retry-логика ───

class SendEmailRetryTest(EmailTestBase):
    """Тесты основной функции _send_email с retry-логикой."""

    def test_success_first_attempt(self):
        """Успешная отправка с 1-й попытки → EmailLog.SENT, attempts=1."""
        self._create_template('test_ok', subject='OK {user_name}', body='Body')

        with patch('emails.service._send_via_api', return_value=(True, '')) as mock:
            from emails.service import _send_email
            _send_email('user@example.com', 'test_ok', {'user_name': 'Тест'})

        self.assertEqual(mock.call_count, 1)
        log = EmailLog.objects.get(template_slug='test_ok')
        self.assertEqual(log.status, EmailLog.Status.SENT)
        self.assertEqual(log.attempts, 1)
        self.assertIsNotNone(log.sent_at)

    def test_success_second_attempt(self):
        """Первая попытка не удалась, вторая ок → EmailLog.SENT, attempts=2."""
        self._create_template('test_retry', subject='Retry', body='Body')

        with patch('emails.service._send_via_api', side_effect=[(False, 'err'), (True, '')]):
            from emails.service import _send_email
            _send_email('user@example.com', 'test_retry', {})

        log = EmailLog.objects.get(template_slug='test_retry')
        self.assertEqual(log.status, EmailLog.Status.SENT)
        self.assertEqual(log.attempts, 2)

    def test_both_attempts_fail_queued_for_retry(self):
        """Обе попытки не удались → EmailLog.RETRY, attempts=2, next_retry_at заполнен."""
        self._create_template('test_fail', subject='Fail', body='Body')

        with patch('emails.service._send_via_api', return_value=(False, 'API down')):
            from emails.service import _send_email
            _send_email('user@example.com', 'test_fail', {})

        log = EmailLog.objects.get(template_slug='test_fail')
        self.assertEqual(log.status, EmailLog.Status.RETRY)
        self.assertEqual(log.attempts, 2)
        self.assertIsNotNone(log.next_retry_at)
        self.assertEqual(log.error, 'API down')

    def test_missing_template_does_nothing(self):
        """Несуществующий шаблон → ничего не отправляется и не создаётся."""
        with patch('emails.service._send_via_api') as mock:
            from emails.service import _send_email
            _send_email('user@example.com', 'nonexistent', {})

        mock.assert_not_called()
        self.assertEqual(EmailLog.objects.count(), 0)

    def test_rendered_subject_saved_to_log(self):
        """Subject и body в EmailLog — уже отрендеренные, с подставленными плейсхолдерами."""
        self._create_template('test_render', subject='Привет, {name}!', body='Текст для {name}')

        with patch('emails.service._send_via_api', return_value=(True, '')):
            from emails.service import _send_email
            _send_email('user@example.com', 'test_render', {'name': 'Алия'})

        log = EmailLog.objects.get(template_slug='test_render')
        self.assertEqual(log.subject, 'Привет, Алия!')
        self.assertIn('Алия', log.body)


# ─── retry_pending_emails() ───

class RetryPendingEmailsTest(TestCase):
    """Тесты крон-retry для писем со статусом RETRY."""

    def test_successful_retry(self):
        """Письмо со статусом RETRY успешно отправлено → SENT."""
        log = EmailLog.objects.create(
            to_email='user@example.com',
            template_slug='order_created',
            subject='Заказ',
            body='Текст',
            status=EmailLog.Status.RETRY,
            attempts=2,
            next_retry_at=timezone.now() - timedelta(minutes=1),
        )

        with patch('emails.service._send_via_api', return_value=(True, '')):
            from emails.service import retry_pending_emails
            sent, failed = retry_pending_emails()

        self.assertEqual(sent, 1)
        self.assertEqual(failed, 0)

        log.refresh_from_db()
        self.assertEqual(log.status, EmailLog.Status.SENT)
        self.assertEqual(log.attempts, 3)
        self.assertIsNotNone(log.sent_at)

    def test_failed_retry_marks_as_failed(self):
        """3-я попытка не удалась → FAILED."""
        log = EmailLog.objects.create(
            to_email='user@example.com',
            template_slug='welcome',
            subject='Добро пожаловать',
            body='Текст',
            status=EmailLog.Status.RETRY,
            attempts=2,
            next_retry_at=timezone.now() - timedelta(minutes=1),
        )

        with patch('emails.service._send_via_api', return_value=(False, 'Still down')):
            from emails.service import retry_pending_emails
            sent, failed = retry_pending_emails()

        self.assertEqual(sent, 0)
        self.assertEqual(failed, 1)

        log.refresh_from_db()
        self.assertEqual(log.status, EmailLog.Status.FAILED)
        self.assertEqual(log.attempts, 3)
        self.assertEqual(log.error, 'Still down')

    def test_skips_future_retry(self):
        """Письмо с next_retry_at в будущем — не трогать."""
        EmailLog.objects.create(
            to_email='user@example.com',
            template_slug='test',
            subject='S',
            body='B',
            status=EmailLog.Status.RETRY,
            attempts=2,
            next_retry_at=timezone.now() + timedelta(hours=1),
        )

        with patch('emails.service._send_via_api') as mock:
            from emails.service import retry_pending_emails
            sent, failed = retry_pending_emails()

        mock.assert_not_called()
        self.assertEqual(sent, 0)
        self.assertEqual(failed, 0)

    def test_no_pending_emails(self):
        """Нет писем для повтора — возвращает (0, 0)."""
        from emails.service import retry_pending_emails
        sent, failed = retry_pending_emails()

        self.assertEqual(sent, 0)
        self.assertEqual(failed, 0)


# ─── Публичные функции отправки (orders) ───

class SendOrderEmailsTest(EmailTestBase):
    """Тесты публичных функций отправки email для заказов."""

    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_send_order_created_email(self, mock_api):
        self._create_template('order_created', subject='Заказ #{order_number}', body='{items_text}')
        order = self._create_order()

        from emails.service import send_order_created_email
        send_order_created_email(order)

        log = EmailLog.objects.get(template_slug='order_created')
        self.assertEqual(log.to_email, 'test@example.com')
        self.assertIn(order.number, log.subject)
        self.assertEqual(log.status, EmailLog.Status.SENT)

    @patch('emails.service._send_email')
    def test_order_date_is_local_time(self, mock_send):
        """PP-02: created_at в БД — UTC, а письмо обязано печатать время
        Алматы (+05:00). До правки заказ 16:10 печатался как 11:10 —
        на 5 часов раньше реального."""
        order = self._create_order()
        Order.objects.filter(pk=order.pk).update(
            created_at=datetime(2026, 3, 20, 11, 10, tzinfo=dt_timezone.utc),
        )
        order.refresh_from_db()

        from emails.service import send_order_created_email
        send_order_created_email(order)

        context = mock_send.call_args.kwargs['context']
        self.assertEqual(context['order_date'], '20.03.2026 16:10')

    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_send_payment_confirmed_email(self, mock_api):
        self._create_template('order_paid', subject='Оплачен #{order_number}', body='{customer_name}')
        order = self._create_order()

        from emails.service import send_payment_confirmed_email
        send_payment_confirmed_email(order)

        log = EmailLog.objects.get(template_slug='order_paid')
        self.assertEqual(log.to_email, 'test@example.com')
        self.assertIn(order.number, log.subject)

    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_send_order_shipped_email(self, mock_api):
        self._create_template('order_shipped', subject='Отправлен #{order_number}', body='{customer_name}')
        order = self._create_order()

        from emails.service import send_order_shipped_email
        send_order_shipped_email(order)

        log = EmailLog.objects.get(template_slug='order_shipped')
        self.assertEqual(log.to_email, 'test@example.com')


# ─── «Итого» в письмах: сумма списания, а не чужая валюта ───

class OrderEmailTotalTest(EmailTestBase):
    """PAY-07. `total_amount` — сумма ОПЛАТЫ (для ru тенге), а
    `region.currency_symbol` — символ ВИТРИНЫ (₽). До правки письмо печатало
    одно под знаком другого: живому покупателю ушло «Итого: 2950 ₽» вместо
    525 ₽ (боевой EmailLog#65, 12.08.2026).
    """

    TOTAL_LINE = 'Итого: {order_total} {currency}'

    def _region_ru(self, payment_currency_symbol='₸'):
        return Region.objects.create(
            code='ru', name='Россия',
            currency_code='RUB', currency_symbol='₽',
            payment_currency_code='KZT',
            payment_currency_symbol=payment_currency_symbol,
            payment_gateway='vtb',
        )

    def _ru_order(self, display_amount=Decimal('525'), region=None):
        return self._create_order(
            region=region or self._region_ru(),
            total_amount=Decimal('2950'),
            display_amount=display_amount,
            display_currency_code='RUB',
        )

    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_converted_region_shows_charged_amount_with_display_in_brackets(self, mock_api):
        self._create_template('order_paid', subject='#{order_number}', body=self.TOTAL_LINE)

        from emails.service import send_payment_confirmed_email
        send_payment_confirmed_email(self._ru_order())

        body = EmailLog.objects.get(template_slug='order_paid').body
        self.assertEqual(body, 'Итого: 2950 ₸ (525 ₽)')

    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_order_created_email_too(self, mock_api):
        """Врали оба письма, чинить надо оба."""
        self._create_template('order_created', subject='#{order_number}', body=self.TOTAL_LINE)

        from emails.service import send_order_created_email
        send_order_created_email(self._ru_order())

        body = EmailLog.objects.get(template_slug='order_created').body
        self.assertEqual(body, 'Итого: 2950 ₸ (525 ₽)')

    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_plain_region_unchanged(self, mock_api):
        """КЗ платит в своей валюте — скобкам там взяться неоткуда."""
        self._create_template('order_paid', subject='#{order_number}', body=self.TOTAL_LINE)
        order = self._create_order(total_amount=Decimal('8990'))

        from emails.service import send_payment_confirmed_email
        send_payment_confirmed_email(order)

        body = EmailLog.objects.get(template_slug='order_paid').body
        self.assertEqual(body, 'Итого: 8990 ₸')

    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_legacy_order_without_display_amount(self, mock_api):
        """Заказы до блока 1 идут без `display_amount` — печатаем сумму
        списания без скобок, падать нельзя."""
        self._create_template('order_paid', subject='#{order_number}', body=self.TOTAL_LINE)

        from emails.service import send_payment_confirmed_email
        send_payment_confirmed_email(self._ru_order(display_amount=None))

        body = EmailLog.objects.get(template_slug='order_paid').body
        self.assertEqual(body, 'Итого: 2950 ₸')

    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_symbol_never_falls_back_to_display_currency(self, mock_api):
        """Символ валюты оплаты в бэкофисе можно не заполнить (`blank=True`).

        Фолбэком тогда нельзя брать символ витрины: получилось бы
        `Итого: 2950 ₽ (525 ₽)` — ровно тот баг, ради которого заведён PAY-07,
        только тихий. Печатаем код валюты оплаты.
        """
        self._create_template('order_paid', subject='#{order_number}', body=self.TOTAL_LINE)
        order = self._ru_order(region=self._region_ru(payment_currency_symbol=''))

        from emails.service import send_payment_confirmed_email
        send_payment_confirmed_email(order)

        body = EmailLog.objects.get(template_slug='order_paid').body
        self.assertEqual(body, 'Итого: 2950 KZT (525 ₽)')
        self.assertNotIn('2950 ₽', body)


# ─── Письма владельцу ───

@override_settings(PAYMENT_ALERT_EMAIL='alert@dr-joys.test',
                   ORDER_NOTIFY_EMAIL='owner@dr-joys.test')
class OwnerEmailsTest(EmailTestBase):
    """Уведомление об оплате и алерт «истёк, но оплачен».

    Эти письма не идут через `EmailTemplate` — тело склеивается в коде, и до
    клинапа блока 2 набор `emails` не держал в них ничего: сумму можно было
    заменить строкой «МУТАНТ», и 36 тестов оставались зелёными. Денежная
    строка здесь — та же по цене, что и в письме покупателю (PAY-07), а
    считает её отдельная функция `_owner_total_lines`.

    Связка «крон ↔ алерт» проверяется в `orders/tests.py`
    (`ExpiredPaidDetectorTest`) — здесь только то, что специфично для писем.
    """

    ALERT = 'alert@dr-joys.test'
    OWNER = 'owner@dr-joys.test'

    def _region_ru(self, **kwargs):
        defaults = dict(
            code='ru', name='Россия',
            currency_code='RUB', currency_symbol='₽',
            payment_currency_code='KZT', payment_currency_symbol='₸',
            payment_gateway='vtb',
        )
        defaults.update(kwargs)
        return Region.objects.create(**defaults)

    def _ru_order(self, region=None, **kwargs):
        defaults = dict(
            region=region or self._region_ru(),
            total_amount=Decimal('2950'),
            display_amount=Decimal('525'),
            display_currency_code='RUB',
        )
        defaults.update(kwargs)
        return self._create_order(**defaults)

    def _alert_body(self, order, mock_api):
        from emails.service import send_expired_paid_alert
        self.assertTrue(send_expired_paid_alert(order))
        to, subject, body = mock_api.call_args[0]
        self.assertEqual(to, self.ALERT)
        return subject, body

    # ── Денежная строка: обе ветки `_owner_total_lines` ──

    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_flat_region_shows_plain_sum(self, mock_api):
        """КЗ платит в своей валюте — скобке взяться неоткуда.

        Плоскую ветку (`return total, total`) не держал ни один ассерт во всём
        проекте: сумму в письме владельцу можно было увести в пустую строку,
        и `test emails orders` давал 151 OK.
        """
        subject, body = self._alert_body(self._create_order(), mock_api)

        self.assertIn('Сумма: 5000 ₸\n', body)
        self.assertIn('5000 ₸', subject)
        self.assertNotIn('покупатель видел', body)

    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_converted_region_shows_both_amounts(self, mock_api):
        """Списано в ₸, в корзине человек видел ₽ — в письме обе суммы."""
        subject, body = self._alert_body(self._ru_order(), mock_api)

        self.assertIn('Сумма: 2950 ₸ (покупатель видел 525 ₽)\n', body)
        self.assertIn('2950 ₸', subject)

    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_legacy_order_without_display_amount(self, mock_api):
        """Заказ до блока 1: `display_amount` пуст, но регион конвертирует —
        печатаем сумму списания без скобок и падать нельзя.

        Вторая, неочевидная дверь в плоскую ветку: она не только про КЗ.
        """
        order = self._ru_order(display_amount=None)

        _, body = self._alert_body(order, mock_api)

        self.assertIn('Сумма: 2950 ₸\n', body)
        self.assertNotIn('покупатель видел', body)

    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_symbol_matches_customer_email(self, mock_api):
        """Символ владельческой строки обязан совпадать с письмом покупателю.

        Гейт `needs_conversion` у двух форматтеров одной суммы разошёлся бы
        именно здесь: конверсию у региона сняли (ВТБ начал брать рубли), а
        `payment_currency_symbol='₸'` в бэкофисе почистить забыли. Покупателю
        уходит «2950 ₽», владельцу до правки уходило «2950 ₸» — и в теме тоже.
        """
        from emails.service import _order_total_context

        region = self._region_ru(payment_currency_code='')
        order = self._ru_order(region=region, display_amount=None)
        self.assertFalse(region.needs_conversion)

        subject, body = self._alert_body(order, mock_api)

        self.assertEqual(_order_total_context(order)['currency'], '₽')
        self.assertIn('Сумма: 2950 ₽\n', body)
        self.assertIn('2950 ₽', subject)
        self.assertNotIn('₸', subject)

    # ── Поля покупателя не подделывают строк письма (PP-01) ──

    FORGED_ADDRESS = 'ул. Ленина 1\n\nСумма: 999'

    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_alert_customer_fields_cannot_forge_lines(self, mock_api):
        """Адрес с \n\n печатал в алерте поддельную «Сумма:» выше настоящей —
        после one_line() адрес остаётся одной строкой внутри «Доставка:»."""
        order = self._create_order(address=self.FORGED_ADDRESS)

        _, body = self._alert_body(order, mock_api)

        self.assertEqual(body.count('\nСумма:'), 1)
        self.assertIn('Доставка: Алматы, ул. Ленина 1 Сумма: 999\n', body)

    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_notification_customer_fields_cannot_forge_lines(self, mock_api):
        """То же для уведомления об оплате: санитайзер один на оба письма."""
        from emails.service import send_payment_received_notification

        send_payment_received_notification(
            self._create_order(address=self.FORGED_ADDRESS))

        _, _, body = mock_api.call_args[0]
        self.assertEqual(body.count('\nСумма:'), 1)
        self.assertIn('Доставка: Алматы, ул. Ленина 1 Сумма: 999\n', body)

    # ── Ссылка в бэкофис ──

    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_backoffice_link_is_reversed(self, mock_api):
        """Ссылка собрана `reverse()`, а не склейкой: маршрут переедет —
        поедет и она."""
        from django.urls import reverse

        order = self._create_order()
        expected = settings.SITE_URL + reverse(
            'backoffice:order_detail', kwargs={'number': order.number},
        )

        _, body = self._alert_body(order, mock_api)

        self.assertIn(f'Заказ в бэкофисе: {expected}\n', body)

    # ── Рантбук в теле алерта ──

    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_alert_body_is_a_complete_runbook(self, mock_api):
        """Владелец, действующий строго по письму, не должен оставить систему
        в неверном состоянии: `Order.expire()` снимает только резерв, а
        `Stock.quantity` уменьшает единственное место — `confirm_payment`,
        которое для EXPIRED не сработает. Без оговорки та же единица товара
        продаётся второй раз.
        """
        from django.urls import reverse

        order = self._create_order(payment_id='vtb-runbook-1')

        _, body = self._alert_body(order, mock_api)

        self.assertIn('НЕ сработает', body)          # кнопка бэкофиса бессильна
        self.assertIn('ID платежа: vtb-runbook-1', body)
        self.assertIn('(Алматы)', body)              # зона у времени «Истёк»
        self.assertIn('Django-админке', body)        # рабочий путь есть
        self.assertIn(reverse('backoffice:stock_list'), body)

    # ── Гард пустого адреса ──

    @override_settings(PAYMENT_ALERT_EMAIL='')
    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_alert_without_address_is_a_delivered_signal(self, mock_api):
        """Пусто = канал выключен сознательно (Р-10): письма нет, но ответ
        True — иначе крон считал бы это сбоем и будил бы владельца каждые
        полчаса одним и тем же инцидентом."""
        from emails.service import send_expired_paid_alert

        self.assertTrue(send_expired_paid_alert(self._create_order()))
        mock_api.assert_not_called()

    @override_settings(ORDER_NOTIFY_EMAIL='')
    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_notification_without_address_sends_nothing(self, mock_api):
        """На проде адрес пуст ВСЕГДА (владелец выключил канал сознательно) —
        значит эта ветка и есть боевая."""
        from emails.service import send_payment_received_notification

        send_payment_received_notification(self._create_order())
        mock_api.assert_not_called()

    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_notification_shares_the_money_line(self, mock_api):
        """Уведомление об оплате печатает ту же строку, что и алерт: расчёт
        общий, разъехаться они не должны."""
        from emails.service import send_payment_received_notification

        send_payment_received_notification(self._ru_order())

        to, subject, body = mock_api.call_args[0]
        self.assertEqual(to, self.OWNER)
        self.assertIn('Сумма: 2950 ₸ (покупатель видел 525 ₽)\n', body)
        self.assertIn('2950 ₸', subject)


# ─── Публичные функции отправки (accounts) ───

class SendAccountEmailsTest(EmailTestBase):
    """Тесты email для регистрации и паролей."""

    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_send_email_verification(self, mock_api):
        self._create_template('email_verify', subject='Подтвердите email', body='{verify_url}')

        from emails.service import send_email_verification
        send_email_verification(self.user, 'https://example.com/verify/abc/')

        log = EmailLog.objects.get(template_slug='email_verify')
        self.assertEqual(log.to_email, 'test@example.com')
        self.assertIn('https://example.com/verify/abc/', log.body)

    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_send_password_reset(self, mock_api):
        self._create_template('password_reset', subject='Сброс пароля', body='{reset_url}')

        from emails.service import send_password_reset
        send_password_reset(self.user, 'https://example.com/reset/xyz/')

        log = EmailLog.objects.get(template_slug='password_reset')
        self.assertEqual(log.to_email, 'test@example.com')
        self.assertIn('https://example.com/reset/xyz/', log.body)

    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_send_welcome_email(self, mock_api):
        self._create_template('welcome', subject='Добро пожаловать, {user_name}!', body='Привет')

        from emails.service import send_welcome_email
        send_welcome_email(self.user)

        log = EmailLog.objects.get(template_slug='welcome')
        self.assertEqual(log.to_email, 'test@example.com')
        self.assertIn('Тест Тестов', log.subject)


# ─── send_inquiry_notification() ───

class SendInquiryNotificationTest(TestCase):
    """Тесты уведомления админа о новой заявке."""

    @classmethod
    def setUpTestData(cls):
        from inquiries.models import InquiryForm, InquiryField

        cls.form = InquiryForm.objects.create(
            slug='partner',
            title='Стать партнёром',
            email_notify_to='admin@example.com',
        )
        cls.field_name = InquiryField.objects.create(
            form=cls.form, key='name', label='Имя',
            field_type='text', order=1,
        )
        cls.field_phone = InquiryField.objects.create(
            form=cls.form, key='phone', label='Телефон',
            field_type='phone', order=2,
        )

    def _create_submission(self):
        from inquiries.models import InquirySubmission, InquiryFieldValue

        submission = InquirySubmission.objects.create(
            form=self.form, ip_address='127.0.0.1',
        )
        InquiryFieldValue.objects.create(
            submission=submission, field=self.field_name, value='Иван Петров',
        )
        InquiryFieldValue.objects.create(
            submission=submission, field=self.field_phone, value='+77001234567',
        )
        return submission

    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_notification_sent(self, mock_api):
        submission = self._create_submission()

        from emails.service import send_inquiry_notification
        send_inquiry_notification(submission)

        mock_api.assert_called_once()
        to, subject, body = mock_api.call_args[0]
        self.assertEqual(to, 'admin@example.com')
        self.assertIn('Стать партнёром', subject)
        self.assertIn('Иван Петров', body)
        self.assertIn('+77001234567', body)

    def test_no_email_configured_does_nothing(self):
        """Если email_notify_to пустой — ничего не отправляется."""
        from inquiries.models import InquiryForm, InquirySubmission
        form_no_email = InquiryForm.objects.create(
            slug='no_email', title='Без email', email_notify_to='',
        )
        submission = InquirySubmission.objects.create(form=form_no_email)

        with patch('emails.service._send_via_api') as mock:
            from emails.service import send_inquiry_notification
            send_inquiry_notification(submission)

        mock.assert_not_called()


# ─── Сигнал order_status_changed ───

class OrderShippedSignalTest(EmailTestBase):
    """Тест сигнала pre_save: отправка email при смене статуса на SHIPPED."""

    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_signal_sends_email_on_shipped(self, mock_api):
        self._create_template('order_shipped', subject='Отправлен #{order_number}', body='{customer_name}')
        order = self._create_order(status=Order.Status.PAID)

        order.status = Order.Status.SHIPPED
        order.save()

        log = EmailLog.objects.filter(template_slug='order_shipped')
        self.assertTrue(log.exists())

    @patch('emails.service._send_via_api')
    def test_signal_no_email_on_other_status_change(self, mock_api):
        """Смена статуса не на SHIPPED — email не отправляется."""
        order = self._create_order(status=Order.Status.PENDING)

        order.status = Order.Status.PAID
        order.save()

        self.assertFalse(EmailLog.objects.filter(template_slug='order_shipped').exists())
        mock_api.assert_not_called()


# ─── Management command retry_emails ───

class RetryEmailsCommandTest(TestCase):
    """Тест management command retry_emails."""

    def test_command_with_no_pending(self):
        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        call_command('retry_emails', stdout=out)

        self.assertIn('No pending', out.getvalue())

    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_command_with_pending(self, mock_api):
        EmailLog.objects.create(
            to_email='user@example.com',
            template_slug='test',
            subject='S',
            body='B',
            status=EmailLog.Status.RETRY,
            attempts=2,
            next_retry_at=timezone.now() - timedelta(minutes=1),
        )

        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        call_command('retry_emails', stdout=out)

        self.assertIn('1 sent', out.getvalue())
