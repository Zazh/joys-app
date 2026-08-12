import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.core.cache import cache
from django.test import TestCase, RequestFactory, override_settings
from django.utils import timezone

from accounts.models import User
from catalog.models import Category, Product, ProductSize, RegionPrice, Stock
from orders.gateways import get_gateway, get_gateway_by_code
from orders.gateways.base import CallbackRejected, PaymentResult, PaymentStatus
from orders.gateways.halyk import HalykGateway
from orders.gateways.vtb import VTBGateway
from orders.models import Order, OrderItem
from regions.models import ExchangeRate, Region


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
        """Халык живёт за флагом: без боевого токена регион ведёт себя как
        регион без эквайринга — заказ уходит менеджеру, а не в тестовый контур."""
        self.assertIsNone(get_gateway(self.region_kz))
        with override_settings(HALYK_ENABLED=True):
            self.assertIsInstance(get_gateway(self.region_kz), HalykGateway)

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
    def test_invoice_id_is_not_derived_from_order_number(self, mock_token):
        """invoiceId должен быть случайным — иначе его подберут в callback."""
        mock_token.return_value = {'access_token': 'test-token-123', 'expires_in': 7200}
        gw = HalykGateway()

        order_a = self._create_order(region=self.region_kz)
        order_b = self._create_order(region=self.region_kz)
        result_a = gw.create_payment(order_a, 'https://site.com/return/', 'https://site.com/callback/')
        result_b = gw.create_payment(order_b, 'https://site.com/return/', 'https://site.com/callback/')

        self.assertNotEqual(result_a.payment_id, order_a.number.replace('-', ''))
        self.assertNotEqual(result_a.payment_id, result_b.payment_id)
        self.assertEqual(len(result_a.payment_id), 15)
        self.assertTrue(result_a.payment_id.isdigit())

    @patch.object(HalykGateway, '_get_token')
    def test_create_payment_token_failure(self, mock_token):
        mock_token.return_value = None
        order = self._create_order(region=self.region_kz)
        gw = HalykGateway()
        result = gw.create_payment(order, 'https://site.com/return/', 'https://site.com/callback/')

        self.assertFalse(result.success)

    def _halyk_callback_request(self, payload, as_json=True):
        factory = RequestFactory()
        if as_json:
            return factory.post(
                '/orders/payment/callback/halyk/',
                data=json.dumps(payload),
                content_type='application/json',
            )
        return factory.post('/orders/payment/callback/halyk/', data=payload)

    @patch.object(HalykGateway, '_verify_signature', return_value=True)
    def test_process_callback_json_success(self, mock_verify):
        """Halyk callback: JSON POST с code=ok, reasonCode=0 и валидной подписью."""
        order = self._create_order(
            region=self.region_kz, gateway='halyk', payment_id='123456789012345',
        )

        request = self._halyk_callback_request({
            'invoiceId': '123456789012345',
            'code': 'ok',
            'reasonCode': 0,
        })

        gw = HalykGateway()
        result_order, paid = gw.process_callback(request)

        self.assertEqual(result_order.pk, order.pk)
        self.assertTrue(paid)

    @patch.object(HalykGateway, '_verify_signature', return_value=True)
    def test_process_callback_json_failure(self, mock_verify):
        """Halyk callback: JSON POST с code=error."""
        order = self._create_order(
            region=self.region_kz, gateway='halyk', payment_id='123456789012346',
        )

        request = self._halyk_callback_request({
            'invoiceId': '123456789012346',
            'code': 'error',
            'reasonCode': '1',
        })

        gw = HalykGateway()
        result_order, paid = gw.process_callback(request)

        self.assertEqual(result_order.pk, order.pk)
        self.assertFalse(paid)

    @patch.object(HalykGateway, '_verify_signature', return_value=True)
    def test_process_callback_form_data(self, mock_verify):
        """Halyk callback: form POST (не JSON)."""
        order = self._create_order(
            region=self.region_kz, gateway='halyk', payment_id='123456789012347',
        )

        request = self._halyk_callback_request({
            'invoiceId': '123456789012347',
            'code': 'ok',
            'reasonCode': '0',
        }, as_json=False)

        gw = HalykGateway()
        result_order, paid = gw.process_callback(request)

        self.assertEqual(result_order.pk, order.pk)
        self.assertTrue(paid)

    def test_process_callback_without_signature_is_rejected(self):
        """Без ключа подписи любой callback должен отклоняться (fail-closed)."""
        self._create_order(
            region=self.region_kz, gateway='halyk', payment_id='123456789012348',
        )

        request = self._halyk_callback_request({
            'invoiceId': '123456789012348',
            'code': 'ok',
            'reasonCode': 0,
        })

        gw = HalykGateway()
        with self.assertRaises(CallbackRejected):
            gw.process_callback(request)

    @patch.object(HalykGateway, '_verify_signature', return_value=True)
    def test_process_callback_amount_mismatch_is_rejected(self, mock_verify):
        """Оплата на меньшую сумму не должна закрывать заказ."""
        self._create_order(
            region=self.region_kz, gateway='halyk', payment_id='123456789012349',
        )

        request = self._halyk_callback_request({
            'invoiceId': '123456789012349',
            'code': 'ok',
            'reasonCode': 0,
            'amount': 1,
        })

        gw = HalykGateway()
        with self.assertRaises(CallbackRejected):
            gw.process_callback(request)

    @patch.object(HalykGateway, '_verify_signature', return_value=True)
    def test_process_callback_missing_invoice(self, mock_verify):
        request = self._halyk_callback_request({})

        gw = HalykGateway()
        with self.assertRaises(CallbackRejected):
            gw.process_callback(request)

    @patch.object(HalykGateway, '_verify_signature', return_value=True)
    def test_process_callback_order_not_found(self, mock_verify):
        request = self._halyk_callback_request({
            'invoiceId': 'nonexistent',
            'code': 'ok',
            'reasonCode': 0,
        })

        gw = HalykGateway()
        with self.assertRaises(CallbackRejected):
            gw.process_callback(request)

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

    @patch.object(HalykGateway, '_verify_signature', return_value=True)
    @patch('emails.service.send_payment_confirmed_email')
    def test_halyk_callback_json_confirms_payment(self, mock_email, mock_verify):
        order = self._create_order(
            region=self.region_kz, gateway='halyk', payment_id='223456789012345',
        )

        response = self.client.post(
            '/orders/payment/callback/halyk/',
            data=json.dumps({
                'invoiceId': '223456789012345',
                'code': 'ok',
                'reasonCode': 0,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        mock_email.assert_called_once()

    @patch.object(HalykGateway, '_verify_signature', return_value=True)
    @patch('emails.service.send_payment_confirmed_email')
    def test_halyk_callback_form_confirms_payment(self, mock_email, mock_verify):
        order = self._create_order(
            region=self.region_kz, gateway='halyk', payment_id='223456789012346',
        )

        response = self.client.post(
            '/orders/payment/callback/halyk/',
            data={
                'invoiceId': '223456789012346',
                'code': 'ok',
                'reasonCode': '0',
            },
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

    @patch.object(HalykGateway, '_verify_signature', return_value=True)
    def test_halyk_callback_error_stays_pending(self, mock_verify):
        order = self._create_order(
            region=self.region_kz, gateway='halyk', payment_id='223456789012347',
        )

        response = self.client.post(
            '/orders/payment/callback/halyk/',
            data=json.dumps({
                'invoiceId': '223456789012347',
                'code': 'error',
                'reasonCode': 1,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_halyk_callback_forged_is_rejected_and_order_stays_pending(self):
        """Подделанный callback без подписи → 403, заказ не меняется.

        Это ровно тот сценарий, которым можно было получить товар бесплатно.
        """
        order = self._create_order(
            region=self.region_kz, gateway='halyk', payment_id='223456789012348',
        )

        response = self.client.post(
            '/orders/payment/callback/halyk/',
            data={
                'invoiceId': '223456789012348',
                'code': 'ok',
                'reasonCode': '0',
            },
        )

        self.assertEqual(response.status_code, 403)
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


# ─── Заказ без онлайн-оплаты (Халык выключен флагом) ───

class ManualOrderFallbackTest(PaymentTestBase):
    """Пока HALYK_ENABLED=False, заказ КЗ — заявка менеджеру: без редиректа
    на оплату, без срока истечения, крон его не отменяет."""

    def test_manual_order_survives_release_command(self):
        from io import StringIO
        from django.core.management import call_command

        order = self._create_order(region=self.region_kz)
        order.expires_at = None
        order.save(update_fields=['expires_at'])
        expired = self._create_order(region=self.region_kz)
        expired.expires_at = timezone.now() - timedelta(minutes=1)
        expired.save(update_fields=['expires_at'])

        call_command('release_expired_orders', stdout=StringIO())

        order.refresh_from_db()
        expired.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(expired.status, Order.Status.EXPIRED)

    def test_checkout_json_returns_thanks_without_payment_url(self):
        """Полный путь чекаута: заказ создан, payment_url нет (JS покажет
        «Спасибо»), expires_at пуст — заявка не истечёт."""
        from orders.models import CartItem
        self.client.login(email='test@example.com', password='test12345')
        # Авторизованный пользователь — корзина в БД, не в сессии
        CartItem.objects.create(user=self.user, size=self.size_m, qty=2)
        Stock.objects.get_or_create(
            size=self.size_m, region=self.region_kz,
            defaults={'quantity': 100, 'reserved': 0},
        )

        response = self.client.post(
            '/orders/checkout/',
            data=json.dumps({
                'first_name': 'Тест', 'last_name': 'Тестов',
                'phone': '+77001234567', 'email': 'test@example.com',
                'city': 'Алматы', 'address': 'ул. Абая 1',
            }),
            content_type='application/json',
        )
        data = response.json()
        self.assertTrue(data['ok'], data)
        self.assertNotIn('payment_url', data)

        order = Order.objects.get(number=data['order_number'])
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertIsNone(order.expires_at)
        self.assertEqual(order.payment_gateway, '')


# ─── Оформление заказа: регион берётся из cookie ───

class CheckoutRegionTest(PaymentTestBase):
    """Регион заказа — только `request.region` (cookie). Поле «Страна» в форме
    его не задаёт, а сверяется с ним: иначе корзина, посчитанная по ценам
    одного региона, ушла бы в заказ с конвертацией другого.

    Тесты `SetRegionView` живут здесь же (ТЗ PAY-01): в блоке 1 эта вьюха
    стала штатным механизмом переключения региона на оформлении.
    """

    def setUp(self):
        from orders.models import CartItem

        # all_regions контекст-процессор кеширует на 10 минут, а локальный кеш
        # в прогоне общий для всех тестов — иначе селект соберётся по чужим
        # регионам
        cache.clear()
        self.client.login(email='test@example.com', password='test12345')
        CartItem.objects.create(user=self.user, size=self.size_m, qty=2)
        for region in (self.region_kz, self.region_ru):
            Stock.objects.get_or_create(
                size=self.size_m, region=region,
                defaults={'quantity': 100, 'reserved': 0},
            )
        # Своя цена в рублях — иначе корзина ru взяла бы базовую (тенговую)
        RegionPrice.objects.create(
            size=self.size_m, region=self.region_ru, price=Decimal('500'),
        )
        ExchangeRate.objects.create(
            currency_code='RUB', rate=Decimal('5.5'), quant=1,
            fetched_at=timezone.now(),
        )

    def _set_region_cookie(self, code):
        self.client.cookies['drjoys_region'] = code

    def _post_checkout(self, country):
        return self.client.post('/orders/checkout/', {
            'country': country,
            'city': 'Алматы',
            'street': 'Абая',
            'house': '1',
            'apt': '',
            'first_name': 'Тест',
            'last_name': 'Тестов',
            'phone': '+77001234567',
            'email': 'test@example.com',
        })

    # ─── Префилл селекта ───

    def test_get_preselects_region_from_cookie_ru(self):
        self._set_region_cookie('ru')
        response = self.client.get('/orders/checkout/')
        self.assertContains(response, 'value="ru" selected')
        self.assertNotContains(response, 'value="kz" selected')

    def test_get_preselects_region_from_cookie_kz(self):
        self._set_region_cookie('kz')
        response = self.client.get('/orders/checkout/')
        self.assertContains(response, 'value="kz" selected')
        self.assertNotContains(response, 'value="ru" selected')

    def test_get_renders_region_switch_form(self):
        """Селект «Страна» отправляет POST-форму на /region/set/ — механизм
        переключения не должен потеряться при правках шаблона."""
        self._set_region_cookie('kz')
        response = self.client.get('/orders/checkout/')
        self.assertContains(response, 'action="/region/set/"')
        self.assertContains(response, 'name="next" value="/orders/checkout/"')

    def test_get_preselects_region_for_anonymous(self):
        """Префилл страны — не поле профиля, а зеркало региона: он должен
        стоять и у анонима (ТЗ PAY-01 п.1). Форму аноним пока не видит, но
        ветвление по is_authenticated возвращаться не должно."""
        self.client.logout()  # чистит сессию — корзину кладём после
        session = self.client.session
        session['cart'] = {str(self.size_m.pk): 2}
        session.save()
        self._set_region_cookie('ru')

        response = self.client.get('/orders/checkout/')

        self.assertEqual(response.context['form'].initial['country'], 'ru')

    # ─── Guard страны ───

    def test_mismatched_country_does_not_create_order(self):
        """Устаревшая вкладка: в форме «Россия», в cookie — Казахстан."""
        self._set_region_cookie('kz')
        response = self._post_checkout('ru')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)
        self.assertContains(response, 'Регион изменился')

    def test_mismatched_country_resets_select_to_actual_region(self):
        """Селект на странице ошибки возвращается к реальному региону —
        иначе повторная отправка давала бы ту же ошибку бесконечно."""
        self._set_region_cookie('kz')
        response = self._post_checkout('ru')

        self.assertContains(response, 'value="kz" selected')
        self.assertNotContains(response, 'value="ru" selected')

    def test_mismatched_country_keeps_entered_fields(self):
        """Страница ошибки перепривязывает форму к POST — введённый адрес и
        контакты не должны обнуляться, иначе покупатель набирает всё заново."""
        self._set_region_cookie('kz')
        response = self._post_checkout('ru')

        self.assertContains(response, 'value="Алматы"')
        self.assertContains(response, 'value="Абая"')
        self.assertContains(response, 'value="+77001234567"')

    def test_mismatched_country_keeps_payment_total_line(self):
        """У региона с конвертацией строка пересчёта в ₸ есть и на странице
        ошибки: её текст просит «проверьте цены», а проверять надо обе суммы."""
        self._set_region_cookie('ru')
        response = self._post_checkout('kz')

        self.assertContains(response, 'Регион изменился')
        self.assertContains(response, '(5500 ₸)')

    @override_settings(HALYK_ENABLED=False)
    def test_matching_country_kz_creates_order_without_conversion(self):
        """Флаг закреплён явно: у фикстурного kz `payment_gateway='halyk'`, и
        когда Халык включат (Р-7), тест иначе ушёл бы в сеть к банку."""
        self._set_region_cookie('kz')
        response = self._post_checkout('kz')

        self.assertEqual(response.status_code, 302)
        order = Order.objects.get()
        self.assertEqual(order.region.code, 'kz')
        self.assertEqual(order.total_amount, Decimal('5000'))
        self.assertIsNone(order.display_amount)

    @patch.object(VTBGateway, '_post')
    def test_matching_country_ru_creates_order_with_conversion(self, mock_post):
        """Мина ×7.3: сумма заказа считается по ценам ru (1000 ₽) и
        конвертируется в ₸ — а не берётся тенговая цена другого региона."""
        mock_post.return_value = {
            'orderId': 'vtb-order-777',
            'formUrl': 'https://vtb.test/payment/form/777',
        }
        self._set_region_cookie('ru')
        response = self._post_checkout('ru')

        self.assertEqual(response.status_code, 302)
        order = Order.objects.get()
        self.assertEqual(order.region.code, 'ru')
        self.assertEqual(order.display_amount, Decimal('1000'))
        self.assertEqual(order.display_currency_code, 'RUB')
        self.assertEqual(order.total_amount, Decimal('5500'))

    # ─── SetRegionView ───

    def test_set_region_switches_cookie_and_returns_to_checkout(self):
        response = self.client.post('/region/set/', {
            'region': 'ru', 'next': '/orders/checkout/',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/orders/checkout/')
        self.assertEqual(response.cookies['drjoys_region'].value, 'ru')

    def test_set_region_rejects_external_next(self):
        response = self.client.post('/region/set/', {
            'region': 'ru', 'next': 'https://evil.example/',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/')
        self.assertEqual(response.cookies['drjoys_region'].value, 'ru')

    def test_set_region_rejects_sneaky_next(self):
        """Классические обходы проверки редиректа: схема-относительный адрес,
        обратный слэш и javascript: — все должны уводить на «/»."""
        for sneaky in ('//evil.example/', '/\\evil.example', 'javascript:alert(1)'):
            with self.subTest(next=sneaky):
                response = self.client.post('/region/set/', {
                    'region': 'ru', 'next': sneaky,
                })
                self.assertEqual(response['Location'], '/')
