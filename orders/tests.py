import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.core.cache import cache
from django.db import transaction
from django.test import TestCase, RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone, translation

from accounts.models import User
from catalog.models import Category, Product, ProductSize, RegionPrice, Stock
from orders.cart import cart_totals
from orders.gateways import get_gateway, get_gateway_by_code
from orders.gateways.base import CallbackRejected, PaymentResult, PaymentStatus
from orders.gateways.halyk import HalykGateway
from orders.gateways.vtb import (
    SESSION_TIMEOUT_SECS, VTBGateway, _callback_checksum, _checksum_source,
)
from orders.models import PAYMENT_WINDOW, Order, OrderItem
from regions.models import ExchangeRate, Region


@override_settings(ORDER_NOTIFY_EMAIL='')
class PaymentTestBase(TestCase):
    """Базовый класс с общими фикстурами для платёжных тестов.

    `ORDER_NOTIFY_EMAIL=''` — заградитель, а не фикстура: второй колбэк
    `confirm_payment` (`send_payment_received_notification`) в наследниках
    не мокается, и от настоящего HTTPS-запроса в SendPulse набор удерживает
    только пустое значение из окружения. В день, когда владелец включит
    уведомления, обязательный по правилу 5 прогон рассылал бы письма про
    выдуманные заказы.
    """

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
            expires_at=timezone.now() + PAYMENT_WINDOW,
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

@override_settings(VTB_CALLBACK_TOKEN='')
class VTBGatewayTest(PaymentTestBase):
    """Тесты VTB callback и check_status.

    Токен пиннится пустым: тесты класса шлют уведомления БЕЗ подписи, и без
    декоратора их зелёный цвет держится на том, что переменной нет в `.env`
    разработчика. На боевой конфигурации они падали бы на 403. Подписанные
    сценарии перебивают это своим `@override_settings` на методе.
    """

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
    def test_register_sends_session_timeout(self, mock_post):
        """register.do получает sessionTimeoutSecs — без него банк держит форму
        оплаты по своему дефолту, который нам неизвестен."""
        mock_post.return_value = {
            'orderId': 'vtb-order-123',
            'formUrl': 'https://vtb.test/payment/form/123',
        }
        order = self._create_order(region=self.region_ru)
        VTBGateway().create_payment(
            order, 'https://site.com/return/', 'https://site.com/callback/',
        )

        method, params = mock_post.call_args[0]
        self.assertEqual(method, 'register.do')
        self.assertEqual(params['sessionTimeoutSecs'], 1500)

    def test_session_timeout_is_shorter_than_order_window(self):
        """Инвариант: сессия банка короче нашего окна оплаты
        (`orders/models.py::PAYMENT_WINDOW` — его и использует
        `_create_order`).

        Поднять таймаут выше окна ИЛИ сузить окно ниже таймаута — значит
        вернуть дыру «деньги списаны, заказ EXPIRED»: банк ещё принимает
        оплату по заказу, который крон `release_expired_orders` уже отменил
        и снял резерв.
        """
        self.assertLess(SESSION_TIMEOUT_SECS, PAYMENT_WINDOW.total_seconds())

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

    @patch.object(VTBGateway, '_post')
    def test_process_callback_reads_md_order(self, mock_post):
        """Платформа RBS шлёт идентификатор платежа как `mdOrder`.

        До PH-04 обработчик читал только `orderId` — настоящее уведомление
        банка молча игнорировалось (200 OK, заказ не подтверждён).
        """
        mock_post.return_value = {'orderStatus': 2}
        order = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-md-1',
        )

        request = RequestFactory().get(
            '/orders/payment/callback/vtb/',
            data={
                'mdOrder': 'vtb-md-1',
                'orderNumber': order.number,
                'operation': 'deposited',
                'status': '1',
            },
        )

        result_order, paid = VTBGateway().process_callback(request)

        self.assertEqual(result_order.pk, order.pk)
        self.assertTrue(paid)


# ─── Подпись callback-уведомлений ВТБ (симметричная, HMAC-SHA256) ───

class VTBCallbackChecksumTest(TestCase):
    """Тест-вектор алгоритма подписи.

    Взят из документации RBS «Callback-уведомления» (§5.1, пример кода для
    Java): токен `123` и ровно эта строка параметров. Пиннит три вещи разом —
    сортировку по имени, формат `имя;значение;` и верхний регистр hex.
    """

    TOKEN = '123'
    # Порядок ключей намеренно НЕ алфавитный: реализация без сортировки
    # соберёт другую строку и вектор не сойдётся.
    PARAMS = {
        'status': '1',
        'orderNumber': '89312',
        'mdOrder': 'ed6f3abf-cea0-427e-afdf-0ba43ead124f',
        'operation': 'deposited',
        'amount': '1500',
        'checksum': 'в подписи не участвует',
        'sign_alias': 'в подписи не участвует',
    }
    SOURCE = (
        'amount;1500;'
        'mdOrder;ed6f3abf-cea0-427e-afdf-0ba43ead124f;'
        'operation;deposited;'
        'orderNumber;89312;'
        'status;1;'
    )
    CHECKSUM = '9F8253A6BB7777D067DD955751119FA5AAF67B14B9215147190F96B505CDB72C'

    def test_source_string_matches_bank_example(self):
        self.assertEqual(_checksum_source(self.PARAMS), self.SOURCE)

    def test_checksum_matches_vector(self):
        self.assertEqual(_callback_checksum(self.PARAMS, self.TOKEN), self.CHECKSUM)


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

        # Письма уходят через transaction.on_commit, а TestCase держит тест
        # в транзакции — без этой обёртки колбэки не выполнятся никогда.
        with self.captureOnCommitCallbacks(execute=True):
            order.confirm_payment()

        mock_email.assert_called_once()
        called_order = mock_email.call_args[0][0]
        self.assertEqual(called_order.pk, order.pk)

    @patch('emails.service.send_payment_confirmed_email')
    def test_confirm_payment_idempotent(self, mock_email):
        """Повторный вызов confirm_payment не меняет статус (идемпотентность)."""
        order = self._create_order(gateway='halyk', payment_id='test-inv-4')
        with self.captureOnCommitCallbacks(execute=True):
            order.confirm_payment()
        first_paid_at = Order.objects.get(pk=order.pk).paid_at

        # Вызываем второй раз
        order.refresh_from_db()
        with self.captureOnCommitCallbacks(execute=True):
            order.confirm_payment()
        order.refresh_from_db()

        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(order.paid_at, first_paid_at)
        # Email отправлен только 1 раз
        self.assertEqual(mock_email.call_count, 1)

    @patch('emails.service.send_payment_received_notification')
    @patch('emails.service.send_payment_confirmed_email')
    def test_emails_wait_for_commit(self, mock_email, mock_owner):
        """ОБА письма не должны уходить из-под блокировок.

        `confirm_payment` держит select_for_update на заказе и строках Stock;
        HTTP в SendPulse внутри этой транзакции — до ~55 секунд, которые ждут
        и покупатель на return-странице, и чужие оформления того же товара.

        Уведомление владельцу проверяется отдельным моком, а не заодно:
        без него мутация «вернуть второй вызов в прямой» проезжает молча —
        на проде она не видна, пока `ORDER_NOTIFY_EMAIL` пуст, и выстрелит
        ровно в день включения канала.
        """
        order = self._create_order(gateway='halyk', payment_id='commit-1')

        with self.captureOnCommitCallbacks(execute=True):
            order.confirm_payment()
            mock_email.assert_not_called()  # транзакция ещё открыта
            mock_owner.assert_not_called()

        mock_email.assert_called_once()  # ушло после коммита
        mock_owner.assert_called_once()

    @patch('emails.service.send_payment_confirmed_email')
    def test_no_email_when_transaction_rolls_back(self, mock_email):
        """Откат транзакции вокруг подтверждения — письма нет.

        Прямой вызов отправил бы письмо об оплате по заказу, который остался
        неоплаченным.
        """
        order = self._create_order(gateway='halyk', payment_id='commit-2')

        class Rollback(Exception):
            pass

        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(Rollback):
                with transaction.atomic():
                    order.confirm_payment()
                    raise Rollback

        mock_email.assert_not_called()
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    @patch('emails.service._send_via_api', return_value=(True, ''))
    @patch('emails.service.send_payment_confirmed_email')
    def test_expired_order_cannot_be_confirmed(self, mock_email, mock_api):
        """Истёкший заказ подтвердить нельзя — ни кодом, ни кнопкой бэкофиса.

        Держит сразу три вещи, которые больше ничем не закреплены:
        · Р-1 бэклога payments-hardening — автоподтверждение EXPIRED запрещено:
          на бою `expire()` уже вернул резерв, и повторное списание вычло бы
          товар второй раз. Тест держит выход целиком — ни `quantity`, ни
          `reserved` не двигаются;
        · обещание алерта PH-05 владельцу — «кнопка „Подтвердить оплату" НЕ
          сработает»: письмо станет враньём, если guard ослабить;
        · саму мутацию из критериев PH-05 («добавить `confirm_payment`
          в команду»). Она НЕ ловится тестами детектора: guard делает вызов
          пустой операцией, поэтому детектор и остаётся безопасным
          (сверено критиком блока 2 — мутация зелёная, в Handoff записана
          красной).
        """
        order = self._create_order(
            gateway='vtb', payment_id='exp-confirm-1',
            status=Order.Status.EXPIRED,
        )
        stock = Stock.objects.get(size=self.size_m, region=self.region_kz)
        qty_before, reserved_before = stock.quantity, stock.reserved

        with self.captureOnCommitCallbacks(execute=True):
            order.confirm_payment()

        order.refresh_from_db()
        stock.refresh_from_db()
        self.assertEqual(order.status, Order.Status.EXPIRED)
        self.assertIsNone(order.paid_at)
        self.assertEqual(stock.quantity, qty_before)
        self.assertEqual(stock.reserved, reserved_before)
        mock_email.assert_not_called()


# ─── Тесты PaymentCallbackView (integration) ───

@override_settings(VTB_CALLBACK_TOKEN='')
class PaymentCallbackViewTest(PaymentTestBase):
    """Интеграционные тесты view для callback.

    Пустой токен — по той же причине, что и у `VTBGatewayTest`: неподписанные
    уведомления класса не должны зависеть от окружения разработчика.
    """

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

        with self.captureOnCommitCallbacks(execute=True):
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

    def test_vtb_callback_log_is_single_line(self):
        """PP-01: перевод строки (%0A) в параметре callback-а дописывал в лог
        поддельную запись — теперь значения проходят one_line() и запись одна.
        """
        forged = 'x\nINFO orders.views: Callback confirmed: подделка'

        with self.assertLogs('orders.gateways.vtb', level='INFO') as logs:
            self.client.get(
                '/orders/payment/callback/vtb/', {'mdOrder': forged},
            )

        info = [r for r in logs.output if r.startswith('INFO:')]
        self.assertEqual(len(info), 1)
        self.assertIn('mdOrder=x INFO orders.views:', info[0])
        # Ни одна запись callback-пути (включая «order not found») не
        # раскрывает %0A в перевод строки
        for record in logs.output:
            self.assertNotIn('\n', record)

    @patch.object(HalykGateway, '_verify_signature', return_value=True)
    @patch('emails.service.send_payment_confirmed_email')
    def test_halyk_callback_json_confirms_payment(self, mock_email, mock_verify):
        order = self._create_order(
            region=self.region_kz, gateway='halyk', payment_id='223456789012345',
        )

        with self.captureOnCommitCallbacks(execute=True):
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

        with self.captureOnCommitCallbacks(execute=True):
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

    # ── Подпись callback-а (PH-04) ──

    CALLBACK_TOKEN = 'test-callback-token'

    def _callback_query(self, payment_id, order_number, token=None):
        """Параметры уведомления банка; с токеном — подписанные."""
        params = {
            'mdOrder': payment_id,
            'orderNumber': order_number,
            'operation': 'deposited',
            'status': '1',
        }
        if token:
            params['checksum'] = _callback_checksum(params, token)
        return params

    @override_settings(VTB_CALLBACK_TOKEN=CALLBACK_TOKEN)
    @patch.object(VTBGateway, '_post')
    @patch('emails.service.send_payment_confirmed_email')
    def test_vtb_callback_valid_checksum_confirms(self, mock_email, mock_post):
        """Боевой формат: GET, mdOrder, симметричная подпись."""
        mock_post.return_value = {'orderStatus': 2}
        order = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-sig-ok',
        )

        response = self.client.get(
            '/orders/payment/callback/vtb/',
            data=self._callback_query(
                'vtb-sig-ok', order.number, self.CALLBACK_TOKEN,
            ),
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

    @override_settings(VTB_CALLBACK_TOKEN=CALLBACK_TOKEN)
    @patch.object(VTBGateway, '_post')
    def test_vtb_callback_invalid_checksum_is_rejected(self, mock_post):
        """Подпись чужим токеном → 403, заказ не тронут.

        Это и есть смысл проверки: без неё оплату закрывал бы любой GET-запрос
        со стороны, знающий payment_id.

        Заодно пиннится ПОРЯДОК: INFO-строка печатается ДО проверки подписи.
        У отклонённого уведомления это единственный след того, под какими
        именами и с какими значениями банк прислал параметры (сам отказ
        печатает только `mdOrder`) — им и разбирается первый боевой callback.
        ⚠️ `assertLogs` пиннит факт вызова, а не доставку строки в лог; здесь
        нужно ровно первое.
        """
        mock_post.return_value = {'orderStatus': 2}
        order = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-sig-bad',
        )

        with self.assertLogs('orders.gateways.vtb', level='INFO') as logs:
            response = self.client.get(
                '/orders/payment/callback/vtb/',
                data=self._callback_query(
                    'vtb-sig-bad', order.number, 'чужой-токен',
                ),
            )

        self.assertIn(
            'VTB callback: mdOrder=vtb-sig-bad',
            '\n'.join(logs.output),
        )
        self.assertEqual(response.status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)
        mock_post.assert_not_called()

    @override_settings(VTB_CALLBACK_TOKEN=CALLBACK_TOKEN)
    @patch.object(VTBGateway, '_post')
    def test_vtb_callback_without_checksum_is_rejected(self, mock_post):
        mock_post.return_value = {'orderStatus': 2}
        order = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-sig-none',
        )

        response = self.client.get(
            '/orders/payment/callback/vtb/',
            data=self._callback_query('vtb-sig-none', order.number),
        )

        self.assertEqual(response.status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)
        mock_post.assert_not_called()

    @override_settings(VTB_CALLBACK_TOKEN=CALLBACK_TOKEN)
    @patch.object(VTBGateway, '_post')
    def test_vtb_callback_rejection_log_is_single_line(self, mock_post):
        """PP-01 (довесок): ERROR-записи отказа («нет checksum», «подпись не
        сошлась») печатают mdOrder через one_line() — %0A в параметре не
        дописывает поддельную запись и на пути отказа. Тест INFO-строки
        живёт с пустым токеном и до этих веток не доходит."""
        forged = 'x\nERROR подделка'

        for params in (
            {'mdOrder': forged},                       # нет checksum
            {'mdOrder': forged, 'checksum': 'AABB'},   # подпись не сошлась
        ):
            with self.assertLogs('orders.gateways.vtb', level='ERROR') as logs:
                response = self.client.get(
                    '/orders/payment/callback/vtb/', params,
                )
            self.assertEqual(response.status_code, 403)
            self.assertEqual(len(logs.output), 1)
            self.assertNotIn('\n', logs.output[0])
            self.assertIn('mdOrder=x ERROR подделка', logs.output[0])

    @override_settings(VTB_CALLBACK_TOKEN='')
    @patch.object(VTBGateway, '_post')
    @patch('emails.service.send_payment_confirmed_email')
    def test_vtb_callback_without_token_skips_signature(self, mock_email, mock_post):
        """Пустой токен = поведение прода до заполнения `.env.prod`.

        Уведомление без подписи обрабатывается как раньше — иначе деплой кода
        вперёд переменной окружения отключил бы приём оплат.
        """
        mock_post.return_value = {'orderStatus': 2}
        order = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-sig-off',
        )

        response = self.client.get(
            '/orders/payment/callback/vtb/',
            data=self._callback_query('vtb-sig-off', order.number),
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

    @override_settings(VTB_CALLBACK_TOKEN=CALLBACK_TOKEN)
    @patch.object(VTBGateway, '_post')
    def test_vtb_callback_non_ascii_checksum_is_rejected(self, mock_post):
        """Подпись из не-ASCII символов = отказ, а не 500.

        `hmac.compare_digest` на двух `str` требует ASCII и на кириллице
        бросает TypeError. Вьюха ловит только `CallbackRejected`, поэтому до
        правки критика запрос `?checksum=ПОДПИСЬ` роняли обработчик оплаты
        в 500 — на боевом URL, который открыт наружу для банка.
        """
        mock_post.return_value = {'orderStatus': 2}
        order = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-sig-utf8',
        )

        response = self.client.get(
            '/orders/payment/callback/vtb/',
            data={'mdOrder': 'vtb-sig-utf8', 'checksum': 'ПОДПИСЬ'},
        )

        self.assertEqual(response.status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)
        mock_post.assert_not_called()

    @override_settings(VTB_CALLBACK_TOKEN=CALLBACK_TOKEN)
    @patch.object(VTBGateway, '_post')
    def test_vtb_callback_extra_param_breaks_signature(self, mock_post):
        """Подпись считается по ВСЕМ пришедшим параметрам — fail-closed.

        Отсюда следствие, которое стоит помнить при разборе боевого callback-а:
        дописанный кем угодно лишний параметр (в том числе безобидный
        `?utm_source=…` в настройке URL в ЛК банка) попадёт в строку подписи
        и уронит проверку — 403, заказ не подтверждён.
        """
        mock_post.return_value = {'orderStatus': 2}
        order = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-sig-extra',
        )

        params = self._callback_query(
            'vtb-sig-extra', order.number, self.CALLBACK_TOKEN,
        )
        params['utm_source'] = 'дописано-со-стороны'

        response = self.client.get('/orders/payment/callback/vtb/', data=params)

        self.assertEqual(response.status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    @override_settings(VTB_CALLBACK_TOKEN=CALLBACK_TOKEN)
    @patch.object(VTBGateway, '_post')
    @patch('emails.service.send_payment_confirmed_email')
    def test_vtb_callback_valid_checksum_post(self, mock_email, mock_post):
        """Тот же сценарий методом POST: подпись считается по слитому словарю.

        В ЛК банка метод сейчас GET, но приёмка записала оба как рабочие и
        допустила переключение. Без этого теста подпись можно свести к
        `request.GET` — весь набор остался бы зелёным, а переключение метода
        в ЛК дало бы 403 на каждое боевое уведомление.
        """
        mock_post.return_value = {'orderStatus': 2}
        order = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-sig-post',
        )

        response = self.client.post(
            '/orders/payment/callback/vtb/',
            data=self._callback_query(
                'vtb-sig-post', order.number, self.CALLBACK_TOKEN,
            ),
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

    @override_settings(VTB_CALLBACK_TOKEN=CALLBACK_TOKEN)
    @patch.object(VTBGateway, '_post')
    @patch('emails.service.send_payment_confirmed_email')
    def test_vtb_callback_checksum_lowercase_accepted(self, mock_email, mock_post):
        """Подпись в нижнем регистре принимается — сознательная толерантность.

        Банк шлёт верхний (док RBS §4 п.5), но отклонить настоящую оплату
        из-за регистра дороже, чем принять нижний. Существующие подписанные
        тесты это не держат: они берут `checksum` из того же
        `_callback_checksum`, который и так возвращает верхний регистр.
        """
        mock_post.return_value = {'orderStatus': 2}
        order = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-sig-lower',
        )

        params = self._callback_query(
            'vtb-sig-lower', order.number, self.CALLBACK_TOKEN,
        )
        params['checksum'] = params['checksum'].lower()

        response = self.client.get('/orders/payment/callback/vtb/', data=params)

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

    @override_settings(VTB_CALLBACK_TOKEN=CALLBACK_TOKEN)
    @patch.object(VTBGateway, '_post')
    @patch('emails.service.send_payment_confirmed_email')
    def test_vtb_callback_checksum_whitespace_accepted(self, mock_email, mock_post):
        """Пробелы по краям подписи снимаются — вторая половина той же
        толерантности (`.strip()` рядом с `.upper()`)."""
        mock_post.return_value = {'orderStatus': 2}
        order = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-sig-space',
        )

        params = self._callback_query(
            'vtb-sig-space', order.number, self.CALLBACK_TOKEN,
        )
        params['checksum'] = f"  {params['checksum']}  "

        response = self.client.get('/orders/payment/callback/vtb/', data=params)

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)


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

    @patch.object(VTBGateway, 'check_status')
    def test_return_expired_shows_verifying(self, mock_status):
        """PP-06: заказ истёк, деньги могли успеть списаться (банк шлёт на
        returnUrl сразу после оплаты) — покупатель читает нейтральное
        «Платёж проверяется» (Р-3), без креста и кнопки повтора. В банк
        вьюха для мёртвых статусов не ходит — этим занимается детектор
        `check_expired_paid` (PP-05)."""
        order = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-ret-exp',
            status=Order.Status.EXPIRED,
        )
        # `expire()` не чистит payment_url — старая ветка ошибки рисовала
        # по нему «ПОПРОБОВАТЬ СНОВА»; без поля негативный ассерт декоративен
        order.payment_url = 'https://vtb.test/payment/form/exp'
        order.save(update_fields=['payment_url'])

        response = self.client.get('/orders/payment/return/?orderId=vtb-ret-exp')

        self.assertContains(response, 'Платёж проверяется')
        self.assertContains(response, 'заказ не потеряется')
        self.assertNotContains(response, 'не прошла')
        self.assertNotContains(response, 'ПОПРОБОВАТЬ СНОВА')
        mock_status.assert_not_called()
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.EXPIRED)

    @patch.object(VTBGateway, 'check_status')
    def test_return_cancelled_shows_verifying(self, mock_status):
        """То же для отменённого менеджером заказа — второй вход класса
        «деньги списаны, заказ мёртв» (Р-6)."""
        order = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-ret-can',
            status=Order.Status.CANCELLED,
        )
        order.payment_url = 'https://vtb.test/payment/form/can'
        order.save(update_fields=['payment_url'])

        response = self.client.get('/orders/payment/return/?orderId=vtb-ret-can')

        self.assertContains(response, 'Платёж проверяется')
        self.assertNotContains(response, 'не прошла')
        self.assertNotContains(response, 'ПОПРОБОВАТЬ СНОВА')
        mock_status.assert_not_called()
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)

    def test_return_expired_verifying_english(self):
        """en-вариант сверяет именно перевод — ловит несобранный `.mo`
        (прецедент FP-01). Кука `django_language` сильнее заголовка,
        поэтому язык задаётся ею."""
        self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-ret-exp-en',
            status=Order.Status.EXPIRED,
        )
        self.client.cookies['django_language'] = 'en'

        response = self.client.get('/orders/payment/return/?orderId=vtb-ret-exp-en')

        self.assertContains(response, 'Payment is being verified')

    def test_return_halyk_invoice_id(self):
        """Halyk return по invoiceId (не orderId)."""
        order = self._create_order(region=self.region_kz, gateway='halyk')
        invoice_id = order.number.replace('-', '')
        order.payment_id = invoice_id
        order.status = Order.Status.PAID
        order.save(update_fields=['payment_id', 'status'])

        response = self.client.get(f'/orders/payment/return/?invoiceId={invoice_id}')

        self.assertEqual(response.status_code, 200)


# ─── Тесты крона check_payments ───

class CheckPaymentsCommandTest(PaymentTestBase):
    """Крон `check_payments` — страховка от потерянного callback-а.

    На боевом контуре банк ВТБ ни разу не позвал `dynamicCallbackUrl` (аудит
    PAY-03), поэтому этот путь подтверждения — не запасной, а рабочий.
    """

    def _run(self, *args):
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command('check_payments', *args, stdout=out)
        return out.getvalue()

    @patch.object(VTBGateway, '_post')
    @patch('emails.service.send_payment_confirmed_email')
    def test_confirms_paid_order(self, mock_email, mock_post):
        mock_post.return_value = {'orderStatus': 2}
        order = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-cron-1',
        )
        stock = Stock.objects.get(size=self.size_m, region=self.region_ru)
        qty_before = stock.quantity

        with self.captureOnCommitCallbacks(execute=True):
            self._run()

        order.refresh_from_db()
        stock.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertIsNotNone(order.paid_at)
        self.assertEqual(stock.quantity, qty_before - 2)
        self.assertEqual(mock_email.call_count, 1)

    @patch.object(VTBGateway, '_post')
    def test_unpaid_order_stays_pending(self, mock_post):
        mock_post.return_value = {'orderStatus': 6}
        order = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-cron-2',
        )

        self._run()

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    @patch.object(VTBGateway, '_post')
    def test_manual_order_without_gateway_is_not_touched(self, mock_post):
        """Заявка КЗ (шлюза нет) в выборку крона не попадает.

        Ассерт по выводу, а не по статусу: без фильтра `payment_gateway__gt=''`
        заявка попадает в цикл, `get_gateway_by_code('')` кидает KeyError, его
        глотает `except Exception` — и заказ остаётся PENDING точно так же.
        Отличает эти две картины только вывод команды.
        """
        order = self._create_order(region=self.region_kz)

        output = self._run()

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertNotIn(order.number, output)
        self.assertIn('Нет pending заказов с оплатой', output)
        mock_post.assert_not_called()

    @patch.object(VTBGateway, '_post')
    @patch('emails.service.send_payment_confirmed_email')
    def test_order_option_targets_single_order(self, mock_email, mock_post):
        mock_post.return_value = {'orderStatus': 2}
        target = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-cron-3',
        )
        other = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-cron-4',
        )

        self._run('--order', target.number)

        target.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(target.status, Order.Status.PAID)
        self.assertEqual(other.status, Order.Status.PENDING)

    @patch.object(VTBGateway, 'check_status')
    @patch('emails.service.send_payment_confirmed_email')
    def test_gateway_error_does_not_stop_the_rest(self, mock_email, mock_status):
        """Обрыв связи с банком на одном заказе не должен ронять весь прогон:
        иначе один битый заказ держал бы неподтверждёнными все следующие."""
        broken = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-cron-err',
        )
        good = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-cron-ok',
        )

        def by_payment_id(payment_id):
            if payment_id == 'vtb-cron-err':
                raise RuntimeError('связь с банком оборвалась')
            return PaymentStatus(paid=True, raw_status='2')

        mock_status.side_effect = by_payment_id

        output = self._run()

        broken.refresh_from_db()
        good.refresh_from_db()
        self.assertEqual(broken.status, Order.Status.PENDING)
        self.assertEqual(good.status, Order.Status.PAID)
        self.assertIn('Ошибка проверки', output)


# ─── Тесты детектора «EXPIRED с деньгами» ───

@override_settings(PAYMENT_ALERT_EMAIL='alert@dr-joys.com')
class ExpiredPaidDetectorTest(PaymentTestBase):
    """Крон `check_expired_paid` — вторая половина Р-1.

    Первая (sessionTimeoutSecs, PH-03) закрывает окно конструктивно; этот крон
    ловит то, что всё же проскочило: банк списал деньги по заказу, который мы
    уже отменили. Автоподтверждать такое нельзя — резерв снят, склад ушёл бы
    в минус, — поэтому команда только сигналит.
    """

    ALERT = 'alert@dr-joys.com'
    LOGGER = 'orders.management.commands.check_expired_paid'

    def _run(self):
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command('check_expired_paid', stdout=out)
        return out.getvalue()

    def _expired_order(self, payment_id='vtb-exp-1', gateway='vtb', minutes_ago=10):
        order = self._create_order(
            region=self.region_ru, gateway=gateway, payment_id=payment_id,
            status=Order.Status.EXPIRED,
        )
        order.expires_at = timezone.now() - timedelta(minutes=minutes_ago)
        order.save(update_fields=['expires_at'])
        return order

    @patch('emails.service._send_via_api', return_value=(True, ''))
    @patch.object(VTBGateway, 'check_status', return_value=PaymentStatus(paid=True, raw_status='2'))
    def test_alerts_and_leaves_order_untouched(self, mock_status, mock_api):
        order = self._expired_order()
        stock = Stock.objects.get(size=self.size_m, region=self.region_ru)
        qty_before, reserved_before = stock.quantity, stock.reserved

        with self.assertLogs(self.LOGGER, level='ERROR') as logs:
            self._run()

        # Сигнал ушёл: лог + письмо на отдельный адрес
        self.assertIn(order.number, '\n'.join(logs.output))
        mock_api.assert_called_once()
        to, subject, body = mock_api.call_args[0]
        self.assertEqual(to, self.ALERT)
        self.assertIn(order.number, subject)
        self.assertIn('+77001234567', body)
        self.assertIn(f'/backoffice/orders/{order.number}/', body)
        # Инструкция честная: кнопка бэкофиса для EXPIRED бессильна
        self.assertIn('НЕ сработает', body)

        # Ни статуса, ни склада — Р-1 запрещает автоподтверждение
        order.refresh_from_db()
        stock.refresh_from_db()
        self.assertEqual(order.status, Order.Status.EXPIRED)
        self.assertEqual(stock.quantity, qty_before)
        self.assertEqual(stock.reserved, reserved_before)
        self.assertIsNotNone(order.expired_paid_alerted_at)

    @patch('emails.service._send_via_api', return_value=(True, ''))
    @patch.object(VTBGateway, 'check_status', return_value=PaymentStatus(paid=True, raw_status='2'))
    def test_cancelled_paid_order_is_alerted(self, mock_status, mock_api):
        """Второй вход той же дыры (Р-6): менеджер отменил PENDING кнопкой
        бэкофиса, а покупатель в те же минуты дожал оплату на ещё живой
        форме банка. `cancel()` не трогает payment_id/expires_at — заказ
        обязан попасть в выборку, лог — назвать фактический статус."""
        order = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='vtb-can-1',
            status=Order.Status.CANCELLED,
        )
        stock = Stock.objects.get(size=self.size_m, region=self.region_ru)
        qty_before, reserved_before = stock.quantity, stock.reserved

        with self.assertLogs(self.LOGGER, level='ERROR') as logs:
            self._run()

        joined = '\n'.join(logs.output)
        self.assertIn(order.number, joined)
        self.assertIn('CANCELLED order', joined)         # фактический статус
        self.assertIn('has successful payment', joined)  # стабильный якорь grep-а
        mock_api.assert_called_once()
        _, subject, _ = mock_api.call_args[0]
        self.assertIn(order.number, subject)

        # Ни статуса, ни склада (Р-7) — как и для EXPIRED
        order.refresh_from_db()
        stock.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(stock.quantity, qty_before)
        self.assertEqual(stock.reserved, reserved_before)
        self.assertIsNotNone(order.expired_paid_alerted_at)

    @patch('emails.service._send_via_api', return_value=(True, ''))
    @patch.object(VTBGateway, 'check_status', return_value=PaymentStatus(paid=True, raw_status='2'))
    def test_cancelled_without_payment_is_not_polled(self, mock_status, mock_api):
        """Отменённая заявка, не ходившая в банк, банк не опрашивает:
        фильтр `payment_id__gt=''` держит цену расширения выборки —
        «отменённые без оплаты начнут опрашивать банк» не случается."""
        self._create_order(
            region=self.region_ru, gateway='vtb', payment_id='',
            status=Order.Status.CANCELLED,
        )

        output = self._run()

        mock_status.assert_not_called()
        mock_api.assert_not_called()
        self.assertIn('Свежих истёкших или отменённых заказов с оплатой нет', output)

    @patch('emails.service._send_via_api', return_value=(True, ''))
    @patch.object(VTBGateway, 'check_status', return_value=PaymentStatus(paid=True, raw_status='2'))
    def test_alert_is_not_repeated(self, mock_status, mock_api):
        """Крон ходит каждые полчаса — второй раз владельца не будим."""
        self._expired_order()

        with self.assertLogs(self.LOGGER, level='ERROR'):
            self._run()
        self._run()

        self.assertEqual(mock_api.call_count, 1)

    @patch('emails.service._send_via_api', return_value=(True, ''))
    @patch.object(VTBGateway, 'check_status', return_value=PaymentStatus(paid=False, raw_status='6'))
    def test_unpaid_expired_is_not_alerted(self, mock_status, mock_api):
        """Обычный истёкший заказ — не инцидент; поле пусто, чтобы заказ
        перепроверился, пока не выйдет из суточного окна."""
        order = self._expired_order()

        self._run()

        order.refresh_from_db()
        mock_api.assert_not_called()
        self.assertIsNone(order.expired_paid_alerted_at)

    @patch('emails.service._send_via_api', return_value=(True, ''))
    @patch.object(VTBGateway, 'check_status', return_value=PaymentStatus(paid=True, raw_status='2'))
    def test_pending_and_orders_without_payment_id_are_skipped(self, mock_status, mock_api):
        self._create_order(  # PENDING — им занимается check_payments
            region=self.region_ru, gateway='vtb', payment_id='vtb-exp-pending',
        )
        self._expired_order(payment_id='', minutes_ago=5)  # заявка без оплаты
        # Шлюза нет — спрашивать статус не у кого (get_gateway_by_code → KeyError)
        self._expired_order(payment_id='ghost-1', gateway='', minutes_ago=5)

        output = self._run()

        mock_status.assert_not_called()
        mock_api.assert_not_called()
        self.assertIn('Свежих истёкших или отменённых заказов с оплатой нет', output)

    @patch('emails.service._send_via_api', return_value=(True, ''))
    @patch.object(VTBGateway, 'check_status', return_value=PaymentStatus(paid=True, raw_status='2'))
    def test_old_expired_is_not_polled(self, mock_status, mock_api):
        """Сутки прошли — банк по этому заказу уже не опрашиваем."""
        self._expired_order(minutes_ago=60 * 25)

        self._run()

        mock_status.assert_not_called()
        mock_api.assert_not_called()

    @override_settings(PAYMENT_ALERT_EMAIL='')
    @patch('emails.service._send_via_api', return_value=(True, ''))
    @patch.object(VTBGateway, 'check_status', return_value=PaymentStatus(paid=True, raw_status='2'))
    def test_without_alert_email_signal_stays_in_log(self, mock_status, mock_api):
        """Адрес не задан — сигнал всё равно есть в логе, и поле проставлено:
        иначе крон шумел бы одним и тем же инцидентом каждые полчаса."""
        order = self._expired_order()

        with self.assertLogs(self.LOGGER, level='ERROR') as logs:
            self._run()

        mock_api.assert_not_called()
        self.assertIn(order.number, '\n'.join(logs.output))
        order.refresh_from_db()
        self.assertIsNotNone(order.expired_paid_alerted_at)

    @patch('emails.service._send_via_api', return_value=(True, ''))
    @patch.object(VTBGateway, 'check_status', side_effect=RuntimeError('связь с банком оборвалась'))
    def test_bank_error_does_not_crash_the_command(self, mock_status, mock_api):
        """Обрыв связи не должен ронять прогон и не должен «съедать» заказ:
        поле пусто — вернётся в выборку следующим прогоном."""
        order = self._expired_order()

        output = self._run()

        order.refresh_from_db()
        self.assertIn('Ошибка проверки', output)
        self.assertIsNone(order.expired_paid_alerted_at)
        mock_api.assert_not_called()

    @patch('emails.service._send_via_api')
    @patch.object(VTBGateway, 'check_status')
    def test_problem_orders_do_not_hide_the_next_incident(
        self, mock_status, mock_api,
    ):
        """Проблемный заказ не отменяет разбор остальных в том же прогоне.

        Во всех остальных тестах детектора в выборке ровно один заказ, поэтому
        три `continue` в цикле неотличимы от `break` и `return`: после цикла в
        `handle()` кода нет. Цена подмены — сбой на первом заказе прячет
        следующий инцидент до очередного запуска, а при систематической ошибке
        (банк недоступен, SendPulse отвечает 500) — пока тот не выйдет из
        суточного окна и не пропадёт из выборки навсегда.

        Заказы подобраны так, чтобы каждый уходил в свою ветку `continue`:
        обрыв связи с банком, «оплаты нет», письмо не ушло. Настоящий инцидент
        стоит последним и обязан быть разобран.
        """
        broken = self._expired_order(payment_id='vtb-exp-broken')
        unpaid = self._expired_order(payment_id='vtb-exp-unpaid', minutes_ago=5)
        undelivered = self._expired_order(payment_id='vtb-exp-nomail', minutes_ago=6)
        paid = self._expired_order(payment_id='vtb-exp-paid', minutes_ago=7)

        # Порядок выборки задаём явно (`Order.Meta.ordering = ['-created_at']`):
        # если настоящий инцидент окажется не последним, `break` вместо
        # `continue` ничем себя не проявит и тест станет декоративным.
        now = timezone.now()
        for shift, order in enumerate([broken, unpaid, undelivered, paid]):
            Order.objects.filter(pk=order.pk).update(
                created_at=now - timedelta(minutes=shift),
            )
        self.assertEqual(
            list(Order.objects.filter(status=Order.Status.EXPIRED)
                 .values_list('payment_id', flat=True)),
            ['vtb-exp-broken', 'vtb-exp-unpaid', 'vtb-exp-nomail', 'vtb-exp-paid'],
        )

        def status_by_payment_id(payment_id):
            if payment_id == 'vtb-exp-broken':
                raise RuntimeError('связь с банком оборвалась')
            return PaymentStatus(paid=(payment_id != 'vtb-exp-unpaid'), raw_status='2')

        def send(to, subject, body):
            return (undelivered.number not in subject, '')

        mock_status.side_effect = status_by_payment_id
        mock_api.side_effect = send

        with self.assertLogs(self.LOGGER, level='ERROR') as logs:
            output = self._run()

        # Последний заказ разобран, несмотря на три сбоя перед ним
        self.assertIn(paid.number, '\n'.join(logs.output))
        self.assertIn(paid.number, mock_api.call_args[0][1])
        self.assertIn('Ошибка проверки', output)
        self.assertIn('письмо не ушло', output)

        for order in (broken, unpaid, undelivered, paid):
            order.refresh_from_db()
        self.assertIsNotNone(paid.expired_paid_alerted_at)
        # Проблемные заказы не «съедены» — вернутся в выборку следующим прогоном
        self.assertIsNone(broken.expired_paid_alerted_at)
        self.assertIsNone(unpaid.expired_paid_alerted_at)
        self.assertIsNone(undelivered.expired_paid_alerted_at)

    @patch('emails.service._send_via_api')
    @patch.object(VTBGateway, 'check_status', return_value=PaymentStatus(paid=True, raw_status='2'))
    def test_failed_alert_is_retried_next_run(self, mock_status, mock_api):
        """Сбой SendPulse не должен прятать инцидент навсегда.

        У писем владельцу нет очереди `EmailLog`/`retry_emails` — единственный
        повтор даёт сам крон. Если отметить заказ отправленным при неудачной
        отправке, он выпадет из выборки и письмо про списанные деньги не
        придёт уже никогда (находка критика блока 2).
        """
        order = self._expired_order()

        mock_api.return_value = (False, 'SendPulse 500')
        with self.assertLogs(self.LOGGER, level='ERROR'):
            output = self._run()

        order.refresh_from_db()
        self.assertIn('письмо не ушло', output)
        self.assertIsNone(order.expired_paid_alerted_at)

        # Следующий прогон — SendPulse ожил, письмо ушло, отметка встала
        mock_api.return_value = (True, '')
        with self.assertLogs(self.LOGGER, level='ERROR'):
            self._run()

        order.refresh_from_db()
        self.assertEqual(mock_api.call_count, 2)
        self.assertIsNotNone(order.expired_paid_alerted_at)

    @patch('emails.service._send_via_api', return_value=(True, ''))
    @patch.object(VTBGateway, 'check_status', return_value=PaymentStatus(paid=True, raw_status='2'))
    def test_alert_shows_both_amounts(self, mock_status, mock_api):
        """Регион с конверсией: списано в ₸, покупатель видел ₽ — в письме
        обе суммы.

        Тот же расчёт, что в уведомлении об оплате (общий
        `_owner_total_lines`): именно расхождение этих двух сумм и было
        багом PAY-07, ушедшим живому покупателю.
        """
        order = self._expired_order()
        order.display_amount = Decimal('525')
        order.display_currency_code = 'RUB'
        order.save(update_fields=['display_amount', 'display_currency_code'])

        with self.assertLogs(self.LOGGER, level='ERROR'):
            self._run()

        _, subject, body = mock_api.call_args[0]
        self.assertIn('5000 ₸', subject)
        self.assertIn('5000 ₸', body)
        self.assertIn('525 ₽', body)


# ─── Тесты уведомления владельцу об оплате ───

@patch('emails.service.send_payment_confirmed_email')
class PaymentNotificationTest(PaymentTestBase):
    """Уведомление владельцу о подтверждённой оплате (PAY-04).

    Письмо покупателю замокано на весь класс, поэтому единственный вызов
    `_send_via_api` в тестах — это и есть уведомление владельца.
    """

    OWNER = 'owner@dr-joys.com'

    def _paid_ru_order(self, payment_id):
        order = self._create_order(
            region=self.region_ru, gateway='vtb', payment_id=payment_id,
        )
        order.display_amount = Decimal('525')
        order.display_currency_code = 'RUB'
        order.save(update_fields=['display_amount', 'display_currency_code'])
        return order

    @override_settings(ORDER_NOTIFY_EMAIL=OWNER)
    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_owner_notified_on_confirm(self, mock_api, mock_email):
        order = self._create_order(gateway='halyk', payment_id='notify-1')

        # Уведомление уходит через on_commit — см. ConfirmPaymentTest
        with self.captureOnCommitCallbacks(execute=True):
            order.confirm_payment()

        mock_api.assert_called_once()
        to, subject, body = mock_api.call_args[0]
        self.assertEqual(to, self.OWNER)
        self.assertIn(order.number, subject)
        self.assertIn('Тест Тестов', body)
        self.assertIn('+77001234567', body)
        self.assertIn('Алматы', body)
        self.assertIn('halyk', body)
        # Ссылка в бэкофис — рабочая: маршрут ловит номер заказа, а не pk
        self.assertIn(f'/backoffice/orders/{order.number}/', body)

    @override_settings(ORDER_NOTIFY_EMAIL='')
    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_no_notification_without_address(self, mock_api, mock_email):
        order = self._create_order(gateway='halyk', payment_id='notify-2')

        # Без обёртки этот тест был бы пустым: on_commit в TestCase не
        # выполняется сам, и `assert_not_called` проходил бы, даже если
        # выкинуть guard `if not to`. На проде ORDER_NOTIFY_EMAIL пуст
        # сознательно — эту ветку кроме этого теста не проверяет никто.
        with self.captureOnCommitCallbacks(execute=True):
            order.confirm_payment()

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        mock_api.assert_not_called()

    @override_settings(ORDER_NOTIFY_EMAIL=OWNER)
    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_notification_not_duplicated(self, mock_api, mock_email):
        order = self._create_order(gateway='halyk', payment_id='notify-3')

        with self.captureOnCommitCallbacks(execute=True):
            order.confirm_payment()
        order.refresh_from_db()
        with self.captureOnCommitCallbacks(execute=True):
            order.confirm_payment()

        self.assertEqual(mock_api.call_count, 1)

    @override_settings(ORDER_NOTIFY_EMAIL=OWNER)
    @patch('emails.service._send_via_api', return_value=(False, 'SendPulse упал'))
    def test_send_failure_does_not_break_confirm(self, mock_api, mock_email):
        """Уведомление не должно стоить нам оплаты: отправка упала — заказ
        всё равно оплачен и склад списан."""
        order = self._create_order(gateway='halyk', payment_id='notify-4')
        stock = Stock.objects.get(size=self.size_m, region=self.region_kz)
        qty_before = stock.quantity

        # Обёртка обязательна: без неё падающая отправка вообще не вызывается
        # и тест проверяет не то, что написано в его имени.
        with self.captureOnCommitCallbacks(execute=True):
            order.confirm_payment()

        mock_api.assert_called_once()  # отправку действительно попробовали
        order.refresh_from_db()
        stock.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(stock.quantity, qty_before - 2)

    # Уведомление шлётся неподписанным POST-ом — токен пиннится пустым,
    # иначе на боевой конфигурации тест падал бы на 403 проверки подписи.
    @override_settings(ORDER_NOTIFY_EMAIL=OWNER, VTB_CALLBACK_TOKEN='')
    @patch.object(VTBGateway, '_post')
    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_notification_from_callback(self, mock_api, mock_post, mock_email):
        mock_post.return_value = {'orderStatus': 2}
        order = self._paid_ru_order('notify-cb')

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                '/orders/payment/callback/vtb/', data={'orderId': 'notify-cb'},
            )

        mock_api.assert_called_once()
        self.assertIn(order.number, mock_api.call_args[0][1])

    @override_settings(ORDER_NOTIFY_EMAIL=OWNER)
    @patch.object(VTBGateway, '_post')
    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_notification_from_return_view(self, mock_api, mock_post, mock_email):
        """Единственный путь, который реально сработал на проде.

        Оплату заказа 260812-0005 подтвердила именно return-вьюха: банк
        `dynamicCallbackUrl` не зовёт (Н-2 аудита), крон отработал раньше
        оплаты. Значит уведомление обязано уходить и отсюда.
        """
        mock_post.return_value = {'orderStatus': 2}
        order = self._paid_ru_order('notify-ret')

        with self.captureOnCommitCallbacks(execute=True):
            self.client.get('/orders/payment/return/?orderId=notify-ret')

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        mock_api.assert_called_once()
        self.assertIn(order.number, mock_api.call_args[0][1])

    @override_settings(ORDER_NOTIFY_EMAIL=OWNER)
    @patch.object(VTBGateway, '_post')
    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_notification_from_cron(self, mock_api, mock_post, mock_email):
        """Крон — рабочий путь подтверждения (callback банк не зовёт),
        поэтому уведомление обязано уходить и отсюда."""
        from io import StringIO
        from django.core.management import call_command

        mock_post.return_value = {'orderStatus': 2}
        order = self._paid_ru_order('notify-cron')

        with self.captureOnCommitCallbacks(execute=True):
            call_command('check_payments', stdout=StringIO())

        mock_api.assert_called_once()
        self.assertIn(order.number, mock_api.call_args[0][1])

    @override_settings(ORDER_NOTIFY_EMAIL=OWNER)
    @patch('emails.service._send_via_api', return_value=(True, ''))
    def test_converted_region_shows_both_amounts(self, mock_api, mock_email):
        """Регион с конверсией: списано в ₸, покупатель видел ₽. В письме
        должны быть обе суммы — иначе владелец читает чужую валюту (та же
        ошибка живёт в письме покупателю, хвост Н-1 аудита PAY-03)."""
        order = self._paid_ru_order('notify-conv')

        with self.captureOnCommitCallbacks(execute=True):
            order.confirm_payment()

        _, subject, body = mock_api.call_args[0]
        self.assertIn('5000 ₸', subject)
        self.assertIn('525 ₽', body)


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


# ─── Сигнал «заказ отправлен»: письмо за границей транзакции (PP-03) ───

class OrderShippedSignalTransactionTest(PaymentTestBase):
    """PP-03: раньше pre_save слал письмо ДО записи — упавший save() оставлял
    покупателя с ложным «отправлен». Теперь post_save + on_commit.

    ⚠️ on_commit-колбэки в TestCase сами не выполняются — проверки писем
    только под captureOnCommitCallbacks(execute=True), иначе тест молча
    пустой (грабля PH-06).
    """

    @patch('emails.service.send_order_shipped_email')
    def test_shipped_email_sent_once_after_commit(self, mock_email):
        order = self._create_order(status=Order.Status.PAID)

        with self.captureOnCommitCallbacks(execute=True):
            order.status = Order.Status.SHIPPED
            order.save(update_fields=['status'])

        mock_email.assert_called_once_with(order)

    @patch('emails.service.send_order_shipped_email')
    def test_rollback_cancels_email(self, mock_email):
        """save() прошёл, но транзакция откатилась — письма нет: колбэк
        умирает вместе с транзакцией."""
        order = self._create_order(status=Order.Status.PAID)

        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    order.status = Order.Status.SHIPPED
                    order.save(update_fields=['status'])
                    raise RuntimeError('искусственный откат после save')
            except RuntimeError:
                pass

        mock_email.assert_not_called()

    @patch('emails.service.send_order_shipped_email')
    def test_other_status_change_sends_nothing(self, mock_email):
        order = self._create_order(status=Order.Status.PAID)

        with self.captureOnCommitCallbacks(execute=True):
            order.status = Order.Status.DELIVERED
            order.save(update_fields=['status'])

        mock_email.assert_not_called()


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

@override_settings(HALYK_ENABLED=False)
class ManualOrderFallbackTest(PaymentTestBase):
    """Пока HALYK_ENABLED=False, заказ КЗ — заявка менеджеру: без редиректа
    на оплату, без срока истечения, крон его не отменяет.

    Флаг пиннится явно — тем же приёмом и по той же причине, что в
    `CheckoutWithdrawnItemTest`: у фикстурного kz `payment_gateway='halyk'`,
    и в день, когда Халык включат, форменный чекаут этого класса ушёл бы
    в сеть к банку вместо красного теста.
    """

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

    def _fill_cart(self):
        """Залогиненный покупатель с товаром в корзине и стоком в КЗ."""
        from orders.models import CartItem

        # Регион приходит из кеша (regions/middleware), а он общий на прогон:
        # чужой закешированный дефолт увёл бы country в расхождение с region
        cache.clear()
        self.client.login(email='test@example.com', password='test12345')
        # Авторизованный пользователь — корзина в БД, не в сессии
        CartItem.objects.create(user=self.user, size=self.size_m, qty=2)
        Stock.objects.get_or_create(
            size=self.size_m, region=self.region_kz,
            defaults={'quantity': 100, 'reserved': 0},
        )

    def test_checkout_form_creates_order_without_payment_url(self):
        """Полный путь чекаута формой: заказ создан, payment_url нет —
        покупателя уводит на «Спасибо», expires_at пуст (заявка не истечёт).

        До JC-06 этот инвариант проверялся на JSON-ветке checkout; ветка
        удалена вместе с её единственным браузерным клиентом, а инвариант
        живёт — теперь на форменном, единственном пути денег.
        """
        self._fill_cart()

        response = self.client.post(
            '/orders/checkout/',
            data={
                'country': self.region_kz.code,
                'city': 'Алматы', 'street': 'ул. Абая', 'house': '1', 'apt': '',
                'first_name': 'Тест', 'last_name': 'Тестов',
                'phone': '+77001234567', 'email': 'test@example.com',
            },
        )

        order = Order.objects.latest('created_at')
        self.assertRedirects(response, reverse(
            'orders:checkout_success', kwargs={'order_number': order.number},
        ))
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertIsNone(order.expires_at)
        self.assertEqual(order.payment_gateway, '')

    def test_checkout_json_body_no_longer_handled_as_api(self):
        """JSON-ветки checkout больше нет: тело application/json обрабатывает
        обычная форменная ветка — HTML-ответ вместо JSON, и заказ не создаётся.

        Проверяем по типу ответа, а не по статусу: статус — деталь рендера
        страницы с ошибкой, а исчезновение ветки — это именно отсутствие
        JSON-тела (`{'ok': False, ...}`) и 401 у неавторизованного.
        """
        self._fill_cart()
        before = Order.objects.count()

        response = self.client.post(
            '/orders/checkout/',
            data=json.dumps({
                'first_name': 'Тест', 'last_name': 'Тестов',
                'phone': '+77001234567', 'email': 'test@example.com',
                'city': 'Алматы', 'address': 'ул. Абая 1',
            }),
            content_type='application/json',
        )

        self.assertNotIn('application/json', response['Content-Type'])
        self.assertEqual(Order.objects.count(), before)


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
        переключения не должен потеряться при правках шаблона.

        Проверяем именно `#regionSwitchForm`, а не `action="/region/set/"`:
        такую же форму печатают на КАЖДОЙ странице переключатель региона в
        шапке (`base.html`) и `_modal_region.html`, поэтому ассерт по action
        оставался зелёным даже при полностью удалённом механизме PAY-02.

        Сам `<select>` тоже под ассертами: `value="ru" selected` из соседних
        тестов живёт в `<option>` и переименование селекта переживает, а
        переименование рвёт разом обработчик PAY-02 (селект снова инертен) и
        отправку поля `country` формой (заказ не оформляется вовсе)."""
        self._set_region_cookie('kz')
        response = self.client.get('/orders/checkout/')
        html = response.content.decode()

        self.assertIn('id="id_country"', html)      # его ищет обработчик PAY-02
        select = next(
            chunk for chunk in html.split('<select')
            if 'id="id_country"' in chunk
        ).split('</select>')[0]
        self.assertIn('name="country"', select)     # его сверяет guard PAY-01

        self.assertIn('id="regionSwitchForm"', html)
        form = next(
            chunk for chunk in html.split('<form')
            if 'id="regionSwitchForm"' in chunk
        ).split('</form>')[0]
        self.assertIn('action="/region/set/"', form)
        self.assertIn('id="regionSwitchCode"', form)
        self.assertIn('name="region"', form)
        self.assertIn('name="next" value="/orders/checkout/"', form)
        # обработчик, который её сабмитит, — на месте
        self.assertIn("getElementById('regionSwitchForm')", html)
        self.assertIn("getElementById('id_country')", html)
        # и она стоит ДО #checkoutForm: вложенные формы невалидны, браузер
        # выбросил бы внутреннюю и смена страны ушла бы не туда
        self.assertLess(
            html.index('id="regionSwitchForm"'),
            html.index('id="checkoutForm"'),
        )

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
        """У региона с конвертацией строка списания в ₸ есть и на странице
        ошибки: её текст просит «проверьте цены», а проверять надо обе суммы.
        Формат — подписанная строка, а не скобки (редизайн итога 2026-08-16)."""
        self._set_region_cookie('ru')
        response = self._post_checkout('kz')

        self.assertContains(response, 'Регион изменился')
        self.assertContains(response, 'Спишется с карты')
        # Разделитель разрядов — неразрывный пробел ru-локали (PP-08)
        self.assertContains(response, '5\xa0500 ₸')

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


class CheckoutMirHintTest(CheckoutRegionTest):
    """Подсказка «Онлайн-оплата — только картой „Мир“» (PAY-05).

    Фикстуры и хелперы берём у CheckoutRegionTest: там уже собраны корзина,
    цены ru, курс и `_set_region_cookie`.
    """

    HINT = 'Онлайн-оплата — только картой «Мир»'

    def test_hint_shown_for_vtb_region(self):
        self._set_region_cookie('ru')
        response = self.client.get('/orders/checkout/')
        self.assertContains(response, self.HINT)

    def test_hint_hidden_for_region_without_gateway(self):
        """КЗ живёт заявками (HALYK_ENABLED=False) — предупреждать не о чем,
        Р-6 запрещает любые сообщения об отсутствии онлайн-оплаты."""
        self._set_region_cookie('kz')
        response = self.client.get('/orders/checkout/')
        self.assertNotContains(response, self.HINT)

    def test_hint_follows_region_switch(self):
        """Смена региона селектом = cookie + перезагрузка: подсказка обязана
        появиться и исчезнуть вместе с ней."""
        self._set_region_cookie('kz')
        self.assertNotContains(self.client.get('/orders/checkout/'), self.HINT)

        self.client.post('/region/set/', {'region': 'ru', 'next': '/orders/checkout/'})
        self.assertContains(self.client.get('/orders/checkout/'), self.HINT)

    def test_template_comment_does_not_leak_into_html(self):
        """`{# … #}` в Django однострочный (tag_re без DOTALL), многострочный
        уезжает в HTML текстом. Поймано владельцем на ревью PAY-05."""
        self._set_region_cookie('ru')
        response = self.client.get('/orders/checkout/')
        self.assertNotContains(response, 'Подсказка только для региона')
        self.assertNotContains(response, 'Р-6')


class CheckoutThousandsSeparatorTest(CheckoutRegionTest):
    """PP-08: суммы checkout печатаются с разделителем разрядов
    (`floatformat:"0g"`) — в одном формате с модалкой корзины
    (`toLocaleString('ru-RU')`, SB-06). Разделитель ru-локали Django —
    неразрывный пробел, в assert именно `\\xa0`, не обычный пробел.

    Фикстуры и хелперы — у CheckoutRegionTest (корзина, цены ru, курс).
    """

    def test_totals_grouped_with_nbsp(self):
        from orders.models import CartItem

        # 2500 ₸ × 8 = 20 000 — сумма с разрядом тысяч
        CartItem.objects.filter(user=self.user).update(qty=8)
        self._set_region_cookie('kz')

        response = self.client.get('/orders/checkout/')

        self.assertContains(response, '20\xa0000 ₸')

    def test_payment_total_grouped_for_conversion_region(self):
        """У ru-региона строка «Спишется с карты» тоже с разделителем:
        500 ₽ × 4 = 2 000 ₽, конверсия ×5.5 → 11 000 ₸."""
        from orders.models import CartItem

        CartItem.objects.filter(user=self.user).update(qty=4)
        self._set_region_cookie('ru')

        response = self.client.get('/orders/checkout/')

        self.assertContains(response, '2\xa0000 ₽')
        self.assertContains(response, '11\xa0000 ₸')


@override_settings(HALYK_ENABLED=False)
class CheckoutWithdrawnItemTest(CheckoutRegionTest):
    """Guard «снят с продажи» в `_create_order`: coming_soon отсекается только
    при добавлении в корзину, is_active — вообще нигде на пути корзины.
    Товар, снятый ПОСЛЕ добавления, без guard-а становился заказом — склад
    при этом полон, и Stock-проверка его не ловит.

    Фикстуры и хелперы — у CheckoutRegionTest: корзина, сток, цены, курс.
    HALYK_ENABLED пиннится по той же причине, что и в тесте kz-оформления
    родителя: сломанный guard уводил бы тест в сеть к банку вместо красного.
    """

    def _post_checkout_kz(self):
        self._set_region_cookie('kz')
        return self._post_checkout('kz')

    def test_coming_soon_size_does_not_create_order(self):
        ProductSize.objects.filter(pk=self.size_m.pk).update(coming_soon=True)
        response = self._post_checkout_kz()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'снят с продажи')
        self.assertEqual(Order.objects.count(), 0)
        stock = Stock.objects.get(size=self.size_m, region=self.region_kz)
        self.assertEqual(stock.reserved, 0)

    def test_inactive_product_does_not_create_order(self):
        Product.objects.filter(pk=self.product.pk).update(is_active=False)
        response = self._post_checkout_kz()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'снят с продажи')
        self.assertEqual(Order.objects.count(), 0)

    def test_cart_is_kept_for_correction(self):
        """Корзина не чистится: покупатель должен сам убрать снятый товар,
        а не потерять остальное содержимое."""
        from orders.models import CartItem

        ProductSize.objects.filter(pk=self.size_m.pk).update(coming_soon=True)
        self._post_checkout_kz()

        self.assertTrue(CartItem.objects.filter(user=self.user).exists())

    # ─── Витрина: пометка ДО сабмита (второй хотфикс) ───

    def test_withdrawn_item_marked_on_checkout_page(self):
        """Метка вместо цены, submit заблокирован с подсказкой; «Итого»
        скрыт — доступных позиций в корзине нет вовсе."""
        ProductSize.objects.filter(pk=self.size_m.pk).update(coming_soon=True)
        self._set_region_cookie('kz')
        response = self.client.get('/orders/checkout/')

        self.assertContains(response, 'Скоро в продаже')
        self.assertContains(response, 'Удалите недоступные товары в корзине')
        self.assertContains(response, 'text-xs" disabled>')
        # «Итого» модалки корзины (text-xs) есть на каждой странице —
        # проверяем именно блок checkout-сводки (text-sm)
        self.assertNotContains(response, 'uppercase text-sm">Итого')
        self.assertNotContains(response, '5000')  # цена недоступной скрыта

    def test_mixed_cart_totals_exclude_withdrawn(self):
        """Смешанная корзина: итог — только по доступной позиции."""
        from orders.models import CartItem

        size_l = ProductSize.objects.create(
            product=self.product, name='L', sku='DJ-CL-L', price=Decimal('1000'),
        )
        CartItem.objects.create(user=self.user, size=size_l, qty=1)
        Stock.objects.create(size=size_l, region=self.region_kz, quantity=5)
        ProductSize.objects.filter(pk=self.size_m.pk).update(coming_soon=True)
        self._set_region_cookie('kz')
        response = self.client.get('/orders/checkout/')

        self.assertContains(response, 'Скоро в продаже')
        self.assertContains(response, 'uppercase text-sm">Итого')
        self.assertContains(response, '1\xa0000 ₸')  # floatformat:"0g" (PP-08)
        self.assertNotContains(response, '5000')


class CartUnavailableLabelTest(PaymentTestBase):
    """`unavailable_label` в payload корзины — витринное зеркало guard-а
    «снят с продажи»: покупатель видит проблему в корзине, а не ошибкой
    на сабмите. Формулировки — те же, что на странице товара."""

    def setUp(self):
        from orders.models import CartItem

        cache.clear()
        self.client.login(email='test@example.com', password='test12345')
        self.client.cookies['drjoys_region'] = 'kz'
        CartItem.objects.create(user=self.user, size=self.size_m, qty=1)
        Stock.objects.get_or_create(
            size=self.size_m, region=self.region_kz,
            defaults={'quantity': 10, 'reserved': 0},
        )

    def _item(self):
        data = self.client.get('/orders/cart/').json()
        return data['items'][0]

    def test_available_item_has_no_label(self):
        self.assertNotIn('unavailable_label', self._item())

    def test_coming_soon_size(self):
        ProductSize.objects.filter(pk=self.size_m.pk).update(coming_soon=True)
        self.assertEqual(self._item()['unavailable_label'], 'Скоро в продаже')

    def test_inactive_product(self):
        Product.objects.filter(pk=self.product.pk).update(is_active=False)
        self.assertEqual(self._item()['unavailable_label'], 'Снят с продажи')

    def test_zero_stock(self):
        Stock.objects.filter(size=self.size_m, region=self.region_kz).update(
            quantity=0,
        )
        self.assertEqual(self._item()['unavailable_label'], 'Нет в наличии')

    def test_missing_stock_row_counts_as_unavailable(self):
        """Нет строки Stock у региона — чекаут упал бы «нет в наличии»
        (`Stock.DoesNotExist` в `_create_order`), витрина обязана совпадать."""
        Stock.objects.filter(size=self.size_m, region=self.region_kz).delete()
        self.assertEqual(self._item()['unavailable_label'], 'Нет в наличии')

    def test_totals_exclude_unavailable_but_badge_counts_all(self):
        """Итог — без недоступных (их цена не показывается, сумма обязана
        сходиться с видимыми), бейдж — всё содержимое корзины."""
        from orders.models import CartItem

        size_l = ProductSize.objects.create(
            product=self.product, name='L', sku='DJ-CL-L', price=Decimal('1000'),
        )
        CartItem.objects.create(user=self.user, size=size_l, qty=2)
        Stock.objects.create(size=size_l, region=self.region_kz, quantity=5)
        ProductSize.objects.filter(pk=self.size_m.pk).update(coming_soon=True)

        data = self.client.get('/orders/cart/').json()

        self.assertEqual(data['cart_total'], '2000.00')
        self.assertEqual(data['cart_count'], 3)


# ─── Язык ответов /orders/ (серверная половина JC-01) ───

class OrdersAcceptLanguageTest(PaymentTestBase):
    """`/orders/…` живёт вне `i18n_patterns`: язык ответа выбирает
    `LocaleMiddleware` по заголовку `Accept-Language` — ровно поэтому три
    GET-а фронта его шлют (`cart.js`, `favorites.js`, `profile.js`, JC-01).
    Тест держит серверную половину контракта: перестанет ответ зависеть от
    заголовка — покупатель на `/en/` снова получит `product_url` вида
    `/ru/…` и кликом по карточке корзины сменит себе язык сайта.
    """

    def setUp(self):
        from orders.models import CartItem, FavoriteItem

        cache.clear()
        self.client.login(email='test@example.com', password='test12345')
        self.client.cookies['drjoys_region'] = 'kz'
        CartItem.objects.create(user=self.user, size=self.size_m, qty=1)
        FavoriteItem.objects.create(user=self.user, product=self.product)
        Stock.objects.get_or_create(
            size=self.size_m, region=self.region_kz,
            defaults={'quantity': 10, 'reserved': 0},
        )

    def _first(self, url, lang=None):
        headers = {'HTTP_ACCEPT_LANGUAGE': lang} if lang else {}
        return self.client.get(url, **headers).json()['items'][0]

    def test_cart_product_url_follows_header(self):
        for lang in ('en', 'kk'):
            with self.subTest(lang=lang):
                url = self._first('/orders/cart/', lang)['product_url']
                self.assertTrue(url.startswith(f'/{lang}/'), url)

    def test_favorites_product_url_follows_header(self):
        url = self._first('/orders/favorites/', 'kk')['product_url']
        self.assertTrue(url.startswith('/kk/'), url)

    def test_unavailable_label_is_translated(self):
        """Метка недоступной позиции приходит тем же путём, что и ссылка."""
        ProductSize.objects.filter(pk=self.size_m.pk).update(coming_soon=True)
        item = self._first('/orders/cart/', 'en')
        self.assertEqual(item['unavailable_label'], 'Coming soon')

    def test_without_header_answer_is_russian(self):
        url = self._first('/orders/cart/')['product_url']
        self.assertTrue(url.startswith('/ru/'), url)

    def test_cookie_beats_header(self):
        """Порядок `LocaleMiddleware`: префикс URL → кука → заголовок. Кука
        сильнее — браузерные сценарии языка воспроизводятся только с
        очищенной `django_language` (грабля Handoff блока 1 js-cleanup)."""
        self.client.cookies['django_language'] = 'ru'
        url = self._first('/orders/cart/', 'en')['product_url']
        self.assertTrue(url.startswith('/ru/'), url)


# ─── Статус заказа на языке покупателя ───

class OrderStatusI18nTest(PaymentTestBase):
    """Лейблы `Order.Status` ленивые — история заказов говорит на языке
    страницы (вторая половина JC-01: заголовок `Accept-Language` фронт слал
    и раньше, но переводить было нечего). Куку `django_language` тесты не
    ставят намеренно: она сильнее заголовка и обнулила бы смысл проверки.
    """

    def setUp(self):
        cache.clear()
        self.client.login(email='test@example.com', password='test12345')
        self._create_order(status=Order.Status.PAID)

    def _status(self, lang=None):
        headers = {'HTTP_ACCEPT_LANGUAGE': lang} if lang else {}
        response = self.client.get('/orders/history/', **headers)
        self.assertEqual(response.status_code, 200)
        return response.json()['orders'][0]['status_display']

    def test_labels_are_translated(self):
        for lang, label in (('en', 'Paid'), ('kk', 'Төленді')):
            with self.subTest(lang=lang):
                with translation.override(lang):
                    self.assertEqual(str(Order.Status.PAID.label), label)

    def test_history_follows_header(self):
        self.assertEqual(self._status('en'), 'Paid')
        self.assertEqual(self._status('kk'), 'Төленді')

    def test_history_without_header_is_russian(self):
        self.assertEqual(self._status(), 'Оплачен')

    def test_lazy_label_does_not_break_json(self):
        """Регресс на сериализацию: DRF разворачивает ленивую строку сам,
        ответ обязан остаться валидным JSON (иначе `response.json()` бросит)."""
        payload = self.client.get(
            '/orders/history/', HTTP_ACCEPT_LANGUAGE='en').json()
        self.assertTrue(payload['ok'])
        self.assertIsInstance(payload['orders'][0]['status_display'], str)


# ─── Суммы корзины одной функцией ───

class CartTotalsTest(TestCase):
    """`cart_totals` — единственный счёт сумм корзины: payload корзины,
    страница оформления и её страница ошибки берут их отсюда. Позиции
    подаём словарями (форма `Cart.get_items()`), БД тут не нужна."""

    @staticmethod
    def _item(price, qty, old_price=None, unavailable=''):
        item = {
            'qty': qty,
            'price': Decimal(price),
            'old_price': Decimal(old_price) if old_price else None,
            'subtotal': Decimal(price) * qty,
        }
        if unavailable:
            item['unavailable_label'] = unavailable
        return item

    def test_empty_cart(self):
        totals = cart_totals([])

        self.assertEqual(totals.total, Decimal('0'))
        self.assertEqual(totals.old_total, Decimal('0'))
        self.assertEqual(totals.count, 0)

    def test_item_without_old_price_uses_price(self):
        totals = cart_totals([self._item('1000', 2)])

        self.assertEqual(totals.total, Decimal('2000'))
        self.assertEqual(totals.old_total, Decimal('2000'))
        self.assertEqual(totals.count, 2)

    def test_mixed_items(self):
        totals = cart_totals([
            self._item('1000', 2, old_price='1500'),
            self._item('300', 1),
        ])

        self.assertEqual(totals.total, Decimal('2300'))
        self.assertEqual(totals.old_total, Decimal('3300'))
        self.assertEqual(totals.count, 3)

    def test_unavailable_item_is_counted_but_not_summed(self):
        """Тот же контракт, что у витрины: цена недоступной позиции не
        показывается, поэтому в итог не идёт, а из бейджа не исчезает."""
        totals = cart_totals([
            self._item('1000', 2),
            self._item('500', 3, old_price='700', unavailable='Нет в наличии'),
        ])

        self.assertEqual(totals.total, Decimal('2000'))
        self.assertEqual(totals.old_total, Decimal('2000'))
        self.assertEqual(totals.count, 5)


class CartDiscountTotalTest(PaymentTestBase):
    """Сумма без скидки на сквозном пути: RegionPrice.old_price → JSON
    корзины и зачёркнутая цена на оформлении.

    До PH-10 её не пиннило ничто: сломанный фолбэк `old_price or price`
    оставлял набор зелёным, хотя строка скидки исчезала у покупателя.
    """

    def setUp(self):
        from orders.models import CartItem

        cache.clear()
        self.client.login(email='test@example.com', password='test12345')
        self.client.cookies['drjoys_region'] = 'kz'
        CartItem.objects.create(user=self.user, size=self.size_m, qty=2)
        Stock.objects.get_or_create(
            size=self.size_m, region=self.region_kz,
            defaults={'quantity': 10, 'reserved': 0},
        )
        RegionPrice.objects.create(
            size=self.size_m, region=self.region_kz,
            price=Decimal('2000'), old_price=Decimal('2500'),
        )

    def test_cart_payload_keeps_old_total(self):
        data = self.client.get('/orders/cart/').json()

        self.assertEqual(data['cart_total'], '4000.00')
        self.assertEqual(data['cart_old_total'], '5000.00')

    def test_checkout_page_shows_struck_out_total(self):
        response = self.client.get('/orders/checkout/')

        self.assertEqual(response.context['cart_total'], Decimal('4000'))
        self.assertEqual(response.context['cart_old_total'], Decimal('5000'))
        self.assertContains(response, 'line-through')


class CartPaymentTotalTest(PaymentTestBase):
    """`payment_total` в payload корзины — строка «Спишется с карты» в модалке
    корзины, а она есть на КАЖДОЙ странице сайта (`src/js/modules/cart.js`
    читает именно этот ключ).

    Ключ появляется по своему критерию — сумма после конвертации ≠ суммы
    витрины, — а не по `region.needs_conversion`, как на странице оформления.
    Расхождение известное (ревью `orders`, «вне скоупа» PH-10), поэтому
    пиннится ровно как есть: до этого теста ключ можно было убрать из ответа
    целиком, и набор оставался зелёным (проверено мутацией, критик блока 3).
    """

    def setUp(self):
        from orders.models import CartItem

        cache.clear()
        self.client.login(email='test@example.com', password='test12345')
        CartItem.objects.create(user=self.user, size=self.size_m, qty=2)
        for region in (self.region_kz, self.region_ru):
            Stock.objects.get_or_create(
                size=self.size_m, region=region,
                defaults={'quantity': 10, 'reserved': 0},
            )
        # Своя цена в рублях — иначе корзина ru взяла бы базовую (тенговую)
        RegionPrice.objects.create(
            size=self.size_m, region=self.region_ru, price=Decimal('500'),
        )
        ExchangeRate.objects.create(
            currency_code='RUB', rate=Decimal('5.5'), quant=1,
            fetched_at=timezone.now(),
        )

    def _payload(self, code):
        self.client.cookies['drjoys_region'] = code
        return self.client.get('/orders/cart/').json()

    def test_region_with_conversion_gets_payment_total(self):
        data = self._payload('ru')

        self.assertEqual(data['cart_total'], '1000.00')
        self.assertEqual(data['payment_total'], '5500')

    def test_region_without_conversion_has_no_payment_total(self):
        """У kz валюта витрины и валюта оплаты совпадают — лишней строки
        в модалке быть не должно."""
        data = self._payload('kz')

        self.assertEqual(data['cart_total'], '5000.00')
        self.assertNotIn('payment_total', data)
