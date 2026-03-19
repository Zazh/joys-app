"""Тесты email-инфраструктуры: SendPulse API, retry-логика, шаблоны, публичные функции."""

import time
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

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
