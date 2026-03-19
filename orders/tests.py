import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, RequestFactory, override_settings
from django.utils import timezone

from accounts.models import User
from catalog.models import Category, Product, ProductSize, Stock
from orders.gateways import get_gateway, get_gateway_by_code
from orders.gateways.base import PaymentResult, PaymentStatus
from orders.gateways.halyk import HalykGateway
from orders.gateways.vtb import VTBGateway
from orders.models import Order, OrderItem
from regions.models import Region


class PaymentTestBase(TestCase):
    """Базовый класс с общими фикстурами для платёжных тестов."""

    @classmethod
    def setUpTestData(cls):
        cls.region_kz = Region.objects.create(
            code='kz', name='Казахстан',
            currency_code='KZT', currency_symbol='₸',
            payment_gateway='halyk', is_default=True,
        )
        cls.region_ru = Region.objects.create(
            code='ru', name='Россия',
            currency_code='RUB', currency_symbol='₽',
            payment_currency_code='KZT', payment_currency_symbol='₸',
            payment_gateway='vtb',
        )

        cls.user = User.objects.create_user(
            email='test@example.com', password='test12345',
            first_name='Тест', last_name='Тестов',
        )

        cls.category = Category.objects.create(
            name='Презервативы', slug='condoms',
        )
        cls.product = Product.objects.create(
            name='DR.JOYS классические', slug='classic',
            category=cls.category, pack_quantity=5,
        )
        cls.size_m = ProductSize.objects.create(
            product=cls.product, name='M', sku='DJ-CL-M', price=Decimal('2500'),
        )

    def _create_order(self, region=None, gateway='', payment_id='',
                      status=Order.Status.PENDING, total=Decimal('5000')):
        """Создать заказ + позицию + сток для тестов."""
        region = region or self.region_kz
        order = Order.objects.create(
            region=region,
            user=self.user,
            customer_name='Тест Тестов',
            customer_phone='+77001234567',
            customer_email='test@example.com',
            city='Алматы',
            address='ул. Абая 1',
            total_amount=total,
            payment_gateway=gateway,
            payment_id=payment_id,
            status=status,
            expires_at=timezone.now() + timedelta(minutes=30),
        )
        OrderItem.objects.create(
            order=order,
            size=self.size_m,
            product_name='DR.JOYS классические',
            size_name='M',
            quantity=2,
            price=Decimal('2500'),
        )
        Stock.objects.get_or_create(
            size=self.size_m, region=region,
            defaults={'quantity': 100, 'reserved': 2},
        )
        return order


# ─── Тесты VTB Gateway ───

class VTBGatewayTest(PaymentTestBase):
    """Тесты VTB callback и check_status."""

    def test_get_gateway_by_code_vtb(self):
        gw = get_gateway_by_code('vtb')
        self.assertIsInstance(gw, VTBGateway)
        self.assertEqual(gw.code, 'vtb')

    def test_get_gateway_for_region_ru(self):
        gw = get_gateway(self.region_ru)
        self.assertIsInstance(gw, VTBGateway)

    @patch.object(VTBGateway, '_post')
    def test_create_payment_success(self, mock_post):
        mock_post.return_value = {
            'orderId': 'vtb-order-123',
            'formUrl': 'https://vtb.test/payment/form/123',
        }
        order = self._create_order(region=self.region_ru)
        gw = VTBGateway()
        result = gw.create_payment(order, 'https://site.com/return/', 'https://site.com/callback/')

        self.assertTrue(result.success)
        self.assertEqual(result.payment_id, 'vtb-order-123')
        self.assertIn('vtb.test', result.payment_url)

    @patch.object(VTBGateway, '_post')
    def test_create_payment_failure(self, mock_post):
        mock_post.return_value = {
            'errorCode': '1',
            'errorMessage': 'Duplicate order',
        }
        order = self._create_order(region=self.region_ru)
        gw = VTBGateway()
        result = gw.create_payment(order, 'https://site.com/return/', 'https://site.com/callback/')

        self.assertFalse(result.success)
        self.assertIn('Duplicate', result.error_message)

    @patch.object(VTBGateway, '_post')
    def test_check_status_paid(self, mock_post):
        mock_post.return_value = {'orderStatus': 2}
        gw = VTBGateway()
        status = gw.check_status('vtb-order-123')
        self.assertTrue(status.paid)

    @patch.object(VTBGateway, '_post')
    def test_check_status_not_paid(self, mock_post):
        mock_post.return_value = {'orderStatus': 0}
        gw = VTBGateway()
        status = gw.check_status('vtb-order-123')
        self.assertFalse(status.paid)

    @patch.object(VTBGateway, '_post')
    def test_process_callback_success(self, mock_post):
        """VTB callback с orderId → находит заказ, проверяет статус через API."""
        mock_post.return_value = {'orderStatus': 2}
        order = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-order-456',
        )

        factory = RequestFactory()
        request = factory.post(
            '/orders/payment/callback/vtb/',
            data={'orderId': 'vtb-order-456'},
        )

        gw = VTBGateway()
        result_order, paid = gw.process_callback(request)

        self.assertEqual(result_order.pk, order.pk)
        self.assertTrue(paid)

    @patch.object(VTBGateway, '_post')
    def test_process_callback_not_paid(self, mock_post):
        mock_post.return_value = {'orderStatus': 0}
        order = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-order-789',
        )

        factory = RequestFactory()
        request = factory.post(
            '/orders/payment/callback/vtb/',
            data={'orderId': 'vtb-order-789'},
        )

        gw = VTBGateway()
        result_order, paid = gw.process_callback(request)

        self.assertEqual(result_order.pk, order.pk)
        self.assertFalse(paid)

    def test_process_callback_missing_order_id(self):
        factory = RequestFactory()
        request = factory.post('/orders/payment/callback/vtb/', data={})

        gw = VTBGateway()
        result_order, paid = gw.process_callback(request)

        self.assertIsNone(result_order)
        self.assertFalse(paid)

    @patch.object(VTBGateway, '_post')
    def test_process_callback_order_not_found(self, mock_post):
        factory = RequestFactory()
        request = factory.post(
            '/orders/payment/callback/vtb/',
            data={'orderId': 'nonexistent-id'},
        )

        gw = VTBGateway()
        result_order, paid = gw.process_callback(request)

        self.assertIsNone(result_order)
        self.assertFalse(paid)


# ─── Тесты Halyk Gateway ───

class HalykGatewayTest(PaymentTestBase):
    """Тесты Halyk callback и create_payment."""

    def test_get_gateway_by_code_halyk(self):
        gw = get_gateway_by_code('halyk')
        self.assertIsInstance(gw, HalykGateway)
        self.assertEqual(gw.code, 'halyk')

    def test_get_gateway_for_region_kz(self):
        gw = get_gateway(self.region_kz)
        self.assertIsInstance(gw, HalykGateway)

    @patch.object(HalykGateway, '_get_token')
    def test_create_payment_success(self, mock_token):
        mock_token.return_value = {
            'access_token': 'test-token-123',
            'expires_in': 7200,
        }
        order = self._create_order(region=self.region_kz)
        gw = HalykGateway()
        result = gw.create_payment(order, 'https://site.com/return/', 'https://site.com/callback/')

        self.assertTrue(result.success)
        self.assertEqual(result.payment_url, '__halyk__')
        self.assertIn('invoiceId', result._payment_object)
        self.assertEqual(result._payment_object['amount'], 5000)
        self.assertEqual(result._payment_object['currency'], 'KZT')

    @patch.object(HalykGateway, '_get_token')
    def test_create_payment_token_failure(self, mock_token):
        mock_token.return_value = None
        order = self._create_order(region=self.region_kz)
        gw = HalykGateway()
        result = gw.create_payment(order, 'https://site.com/return/', 'https://site.com/callback/')

        self.assertFalse(result.success)

    def test_process_callback_json_success(self):
        """Halyk callback: JSON POST с code=ok, reasonCode=0."""
        order = self._create_order(
            region=self.region_kz, gateway='halyk',
            payment_id=order_number_to_invoice(self._create_order.__name__),
        )
        # Пересоздаём с правильным payment_id
        invoice_id = order.number.replace('-', '')
        order.payment_id = invoice_id
        order.save(update_fields=['payment_id'])

        factory = RequestFactory()
        request = factory.post(
            '/orders/payment/callback/halyk/',
            data=json.dumps({
                'invoiceId': invoice_id,
                'code': 'ok',
                'reasonCode': 0,
            }),
            content_type='application/json',
        )

        gw = HalykGateway()
        result_order, paid = gw.process_callback(request)

        self.assertEqual(result_order.pk, order.pk)
        self.assertTrue(paid)

    def test_process_callback_json_failure(self):
        """Halyk callback: JSON POST с code=error."""
        order = self._create_order(region=self.region_kz, gateway='halyk')
        invoice_id = order.number.replace('-', '')
        order.payment_id = invoice_id
        order.save(update_fields=['payment_id'])

        factory = RequestFactory()
        request = factory.post(
            '/orders/payment/callback/halyk/',
            data=json.dumps({
                'invoiceId': invoice_id,
                'code': 'error',
                'reasonCode': '1',
            }),
            content_type='application/json',
        )

        gw = HalykGateway()
        result_order, paid = gw.process_callback(request)

        self.assertEqual(result_order.pk, order.pk)
        self.assertFalse(paid)

    def test_process_callback_form_data(self):
        """Halyk callback: form POST (не JSON)."""
        order = self._create_order(region=self.region_kz, gateway='halyk')
        invoice_id = order.number.replace('-', '')
        order.payment_id = invoice_id
        order.save(update_fields=['payment_id'])

        factory = RequestFactory()
        request = factory.post(
            '/orders/payment/callback/halyk/',
            data={
                'invoiceId': invoice_id,
                'code': 'ok',
                'reasonCode': '0',
            },
        )

        gw = HalykGateway()
        result_order, paid = gw.process_callback(request)

        self.assertEqual(result_order.pk, order.pk)
        self.assertTrue(paid)

    def test_process_callback_missing_invoice(self):
        factory = RequestFactory()
        request = factory.post(
            '/orders/payment/callback/halyk/',
            data=json.dumps({}),
            content_type='application/json',
        )

        gw = HalykGateway()
        result_order, paid = gw.process_callback(request)

        self.assertIsNone(result_order)
        self.assertFalse(paid)

    def test_process_callback_order_not_found(self):
        factory = RequestFactory()
        request = factory.post(
            '/orders/payment/callback/halyk/',
            data=json.dumps({
                'invoiceId': 'nonexistent',
                'code': 'ok',
                'reasonCode': 0,
            }),
            content_type='application/json',
        )

        gw = HalykGateway()
        result_order, paid = gw.process_callback(request)

        self.assertIsNone(result_order)
        self.assertFalse(paid)

    def test_check_status_from_db(self):
        """Halyk check_status читает статус из БД (нет серверного API)."""
        order = self._create_order(region=self.region_kz, gateway='halyk')
        invoice_id = order.number.replace('-', '')
        order.payment_id = invoice_id
        order.save(update_fields=['payment_id'])

        gw = HalykGateway()

        # Пока pending
        status = gw.check_status(invoice_id)
        self.assertFalse(status.paid)

        # После оплаты
        order.status = Order.Status.PAID
        order.save(update_fields=['status'])
        status = gw.check_status(invoice_id)
        self.assertTrue(status.paid)


# ─── Тесты confirm_payment ───

class ConfirmPaymentTest(PaymentTestBase):
    """Тесты бизнес-логики подтверждения оплаты."""

    @patch('emails.service.send_payment_confirmed_email')
    def test_confirm_payment_updates_status(self, mock_email):
        order = self._create_order(gateway='halyk', payment_id='test-inv-1')

        order.confirm_payment()
        order.refresh_from_db()

        self.assertEqual(order.status, Order.Status.PAID)
        self.assertIsNotNone(order.paid_at)

    @patch('emails.service.send_payment_confirmed_email')
    def test_confirm_payment_deducts_stock(self, mock_email):
        order = self._create_order(gateway='halyk', payment_id='test-inv-2')
        stock = Stock.objects.get(size=self.size_m, region=self.region_kz)
        qty_before = stock.quantity
        reserved_before = stock.reserved

        order.confirm_payment()
        stock.refresh_from_db()

        self.assertEqual(stock.quantity, qty_before - 2)  # item.quantity = 2
        self.assertEqual(stock.reserved, reserved_before - 2)

    @patch('emails.service.send_payment_confirmed_email')
    def test_confirm_payment_sends_email(self, mock_email):
        order = self._create_order(gateway='halyk', payment_id='test-inv-3')

        order.confirm_payment()

        mock_email.assert_called_once()
        called_order = mock_email.call_args[0][0]
        self.assertEqual(called_order.pk, order.pk)

    @patch('emails.service.send_payment_confirmed_email')
    def test_confirm_payment_idempotent(self, mock_email):
        """Повторный вызов confirm_payment не меняет статус (идемпотентность)."""
        order = self._create_order(gateway='halyk', payment_id='test-inv-4')
        order.confirm_payment()
        first_paid_at = Order.objects.get(pk=order.pk).paid_at

        # Вызываем второй раз
        order.refresh_from_db()
        order.confirm_payment()
        order.refresh_from_db()

        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(order.paid_at, first_paid_at)
        # Email отправлен только 1 раз
        self.assertEqual(mock_email.call_count, 1)


# ─── Тесты PaymentCallbackView (integration) ───

class PaymentCallbackViewTest(PaymentTestBase):
    """Интеграционные тесты view для callback."""

    def test_unknown_gateway_returns_404(self):
        response = self.client.post('/orders/payment/callback/unknown/')
        self.assertEqual(response.status_code, 404)

    @patch.object(VTBGateway, '_post')
    @patch('emails.service.send_payment_confirmed_email')
    def test_vtb_callback_confirms_payment(self, mock_email, mock_post):
        mock_post.return_value = {'orderStatus': 2}
        order = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-cb-test-1',
        )

        response = self.client.post(
            '/orders/payment/callback/vtb/',
            data={'orderId': 'vtb-cb-test-1'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'OK')

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        mock_email.assert_called_once()

    @patch.object(VTBGateway, '_post')
    def test_vtb_callback_not_paid_stays_pending(self, mock_post):
        mock_post.return_value = {'orderStatus': 0}
        order = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-cb-test-2',
        )

        response = self.client.post(
            '/orders/payment/callback/vtb/',
            data={'orderId': 'vtb-cb-test-2'},
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    @patch('emails.service.send_payment_confirmed_email')
    def test_halyk_callback_json_confirms_payment(self, mock_email):
        order = self._create_order(region=self.region_kz, gateway='halyk')
        invoice_id = order.number.replace('-', '')
        order.payment_id = invoice_id
        order.save(update_fields=['payment_id'])

        response = self.client.post(
            '/orders/payment/callback/halyk/',
            data=json.dumps({
                'invoiceId': invoice_id,
                'code': 'ok',
                'reasonCode': 0,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        mock_email.assert_called_once()

    @patch('emails.service.send_payment_confirmed_email')
    def test_halyk_callback_form_confirms_payment(self, mock_email):
        order = self._create_order(region=self.region_kz, gateway='halyk')
        invoice_id = order.number.replace('-', '')
        order.payment_id = invoice_id
        order.save(update_fields=['payment_id'])

        response = self.client.post(
            '/orders/payment/callback/halyk/',
            data={
                'invoiceId': invoice_id,
                'code': 'ok',
                'reasonCode': '0',
            },
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

    def test_halyk_callback_error_stays_pending(self):
        order = self._create_order(region=self.region_kz, gateway='halyk')
        invoice_id = order.number.replace('-', '')
        order.payment_id = invoice_id
        order.save(update_fields=['payment_id'])

        response = self.client.post(
            '/orders/payment/callback/halyk/',
            data=json.dumps({
                'invoiceId': invoice_id,
                'code': 'error',
                'reasonCode': 1,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    @patch.object(VTBGateway, '_post')
    @patch('emails.service.send_payment_confirmed_email')
    def test_vtb_callback_get_method(self, mock_email, mock_post):
        """VTB может слать callback через GET."""
        mock_post.return_value = {'orderStatus': 2}
        order = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-cb-get-1',
        )

        response = self.client.get(
            '/orders/payment/callback/vtb/?orderId=vtb-cb-get-1',
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

    @patch.object(VTBGateway, '_post')
    @patch('emails.service.send_payment_confirmed_email')
    def test_double_callback_idempotent(self, mock_email, mock_post):
        """Два одинаковых callback не дублируют списание."""
        mock_post.return_value = {'orderStatus': 2}
        order = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-double-1',
        )
        stock = Stock.objects.get(size=self.size_m, region=self.region_ru)
        qty_before = stock.quantity

        # Первый callback
        self.client.post('/orders/payment/callback/vtb/', data={'orderId': 'vtb-double-1'})
        # Второй callback (дубль)
        self.client.post('/orders/payment/callback/vtb/', data={'orderId': 'vtb-double-1'})

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

        stock.refresh_from_db()
        self.assertEqual(stock.quantity, qty_before - 2)  # Списано только 1 раз

        # Email отправлен только 1 раз
        self.assertEqual(mock_email.call_count, 1)


# ─── Тесты PaymentReturnView ───

class PaymentReturnViewTest(PaymentTestBase):
    """Тесты return URL (redirect клиента после оплаты)."""

    def test_return_without_id(self):
        response = self.client.get('/orders/payment/return/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Некорректная ссылка')

    def test_return_order_not_found(self):
        response = self.client.get('/orders/payment/return/?orderId=nonexistent')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Заказ не найден')

    @patch.object(VTBGateway, '_post')
    @patch('emails.service.send_payment_confirmed_email')
    def test_return_vtb_checks_status_and_confirms(self, mock_email, mock_post):
        mock_post.return_value = {'orderStatus': 2}
        order = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-ret-1',
        )

        response = self.client.get('/orders/payment/return/?orderId=vtb-ret-1')

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

    @patch.object(VTBGateway, '_post')
    def test_return_vtb_pending_shows_failure(self, mock_post):
        mock_post.return_value = {'orderStatus': 0}
        order = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-ret-2',
        )

        response = self.client.get('/orders/payment/return/?orderId=vtb-ret-2')

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_return_halyk_invoice_id(self):
        """Halyk return по invoiceId (не orderId)."""
        order = self._create_order(region=self.region_kz, gateway='halyk')
        invoice_id = order.number.replace('-', '')
        order.payment_id = invoice_id
        order.status = Order.Status.PAID
        order.save(update_fields=['payment_id', 'status'])

        response = self.client.get(f'/orders/payment/return/?invoiceId={invoice_id}')

        self.assertEqual(response.status_code, 200)


# ─── Тесты Order lifecycle ───

class OrderLifecycleTest(PaymentTestBase):
    """Тесты жизненного цикла заказа: cancel, expire."""

    def test_cancel_releases_stock(self):
        order = self._create_order()
        stock = Stock.objects.get(size=self.size_m, region=self.region_kz)
        reserved_before = stock.reserved

        order.cancel()
        stock.refresh_from_db()
        order.refresh_from_db()

        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(stock.reserved, reserved_before - 2)

    def test_expire_releases_stock(self):
        order = self._create_order()
        stock = Stock.objects.get(size=self.size_m, region=self.region_kz)
        reserved_before = stock.reserved

        order.expire()
        stock.refresh_from_db()
        order.refresh_from_db()

        self.assertEqual(order.status, Order.Status.EXPIRED)
        self.assertEqual(stock.reserved, reserved_before - 2)

    def test_cancel_idempotent_on_paid(self):
        """Нельзя отменить оплаченный заказ."""
        order = self._create_order(status=Order.Status.PAID)
        order.cancel()
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

    def test_expire_idempotent_on_paid(self):
        """Нельзя завершить по таймеру оплаченный заказ."""
        order = self._create_order(status=Order.Status.PAID)
        order.expire()
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)


# ─── Тест gateway registry ───

class GatewayRegistryTest(TestCase):

    def test_unknown_gateway_raises_keyerror(self):
        with self.assertRaises(KeyError):
            get_gateway_by_code('stripe')

    def test_get_gateway_no_payment(self):
        region = Region.objects.create(
            code='test', name='Test', currency_code='USD', currency_symbol='$',
            payment_gateway='',
        )
        self.assertIsNone(get_gateway(region))


def order_number_to_invoice(name):
    """Хелпер — не используется напрямую, нужен для генерации invoice_id."""
    return ''
