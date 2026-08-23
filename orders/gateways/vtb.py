import hashlib
import hmac
import logging
import os
import tempfile

import certifi
import requests
from django.conf import settings

from core.text import one_line
from orders.models import Order
from .base import BaseGateway, CallbackRejected, PaymentResult, PaymentStatus

logger = logging.getLogger(__name__)

# Шлюз ВТБ может перейти на TLS-сертификаты Минцифры (Russian Trusted CA),
# которых нет в бандле certifi. Доверяем им только в запросах к ВТБ:
# собираем объединённый бандл certifi + certs/*.crt и передаём его в verify=.
_CERTS_DIR = os.path.join(os.path.dirname(__file__), 'certs')
_ca_bundle_path = None


def _ca_bundle():
    global _ca_bundle_path
    if _ca_bundle_path is None or not os.path.exists(_ca_bundle_path):
        parts = [open(certifi.where()).read()]
        for name in sorted(os.listdir(_CERTS_DIR)):
            if name.endswith(('.crt', '.pem')):
                parts.append(open(os.path.join(_CERTS_DIR, name)).read())
        fd, path = tempfile.mkstemp(prefix='vtb_ca_bundle_', suffix='.pem')
        with os.fdopen(fd, 'w') as f:
            f.write('\n'.join(parts))
        _ca_bundle_path = path
    return _ca_bundle_path

# Время жизни платёжной сессии банка (register.do). ИНВАРИАНТ: значение должно
# быть МЕНЬШЕ 30-минутного `expires_at` заказа (`orders/views.py::_create_order`).
# Иначе форма оплаты банка переживает наш заказ: крон `release_expired_orders`
# уводит его в EXPIRED и снимает резерв, а покупатель в это время платит —
# возвращается окно «деньги списаны, заказ EXPIRED», подтвердить который уже
# не может ни один из путей `confirm_payment`.
SESSION_TIMEOUT_SECS = 1500  # 25 минут

# ISO 4217 numeric codes
CURRENCY_NUMERIC = {
    'KZT': '398',
    'RUB': '643',
    'USD': '840',
    'EUR': '978',
    'UZS': '860',
    'KGS': '417',
}


# ── Симметричная подпись callback-уведомлений (RBS) ──
# Алгоритм — документация RBS «Callback-уведомления», §4: из параметров
# уведомления убираются `checksum` и `sign_alias`, остальные сортируются по
# имени в прямом алфавитном порядке и склеиваются как `имя;значение;`; от
# строки берётся HMAC-SHA256 с callback-токеном в роли ключа, hex приводится
# к верхнему регистру.
_CHECKSUM_SKIP = ('checksum', 'sign_alias')


def _checksum_source(params):
    """Строка параметров для подписи.

    Пример из документации банка (§5.1):
    `amount;1500;mdOrder;ed6f3abf-…-0ba43ead124f;operation;deposited;`
    `orderNumber;89312;status;1;`
    """
    return ''.join(
        f'{name};{value};'
        for name, value in sorted(params.items())
        if name not in _CHECKSUM_SKIP
    )


def _callback_checksum(params, token):
    """Ожидаемая контрольная сумма уведомления — hex в верхнем регистре."""
    return hmac.new(
        token.encode('utf-8'),
        _checksum_source(params).encode('utf-8'),
        hashlib.sha256,
    ).hexdigest().upper()


class VTBGateway(BaseGateway):
    """VTB Bank acquiring (vtbkz.rbsuat.com / payment.vtb.kz)."""

    code = 'vtb'

    def __init__(self):
        self.base_url = settings.VTB_PAYMENT_URL.rstrip('/')
        self.username = settings.VTB_USERNAME
        self.password = settings.VTB_PASSWORD

    def _post(self, method, params):
        params['userName'] = self.username
        params['password'] = self.password
        url = f'{self.base_url}/{method}'
        try:
            resp = requests.post(url, data=params, timeout=30, verify=_ca_bundle())
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error('VTB API error: %s %s', method, e)
            return {'errorCode': '-1', 'errorMessage': str(e)}

    # ── BaseGateway interface ──

    def create_payment(self, order, return_url, callback_url):
        amount_minor = int(order.total_amount * 100)
        pay_currency = order.region.payment_currency_code or order.region.currency_code
        currency_code = CURRENCY_NUMERIC.get(pay_currency)

        params = {
            'orderNumber': order.number,
            'amount': amount_minor,
            'returnUrl': return_url,
            'failUrl': return_url,
            'language': 'ru',
            'dynamicCallbackUrl': callback_url,
            'description': f'Заказ {order.number}',
            'sessionTimeoutSecs': SESSION_TIMEOUT_SECS,
        }
        if currency_code:
            params['currency'] = currency_code
        if order.customer_email:
            params['email'] = order.customer_email

        result = self._post('register.do', params)
        logger.info(
            'VTB register.do: order=%s amount=%s → %s',
            order.number, amount_minor,
            'OK' if result.get('formUrl') else result.get('errorMessage', '?'),
        )

        if result.get('formUrl'):
            return PaymentResult(
                success=True,
                payment_id=result['orderId'],
                payment_url=result['formUrl'],
            )
        return PaymentResult(
            success=False,
            error_message=result.get('errorMessage', 'Unknown error'),
        )

    def check_status(self, payment_id):
        result = self._post('getOrderStatusExtended.do', {
            'orderId': payment_id,
            'language': 'ru',
        })
        order_status = result.get('orderStatus')
        logger.info('VTB status: id=%s → %s', payment_id, order_status)
        return PaymentStatus(
            paid=(order_status == 2),
            raw_status=str(order_status),
        )

    def _callback_params(self, request):
        """Параметры уведомления одним словарём.

        Банк настроен на GET, но обработчик исторически принимал и POST —
        читаем оба. Тем же словарём считается подпись: параметр, дописанный
        к запросу со стороны, попадёт в строку подписи и уронит проверку.
        """
        params = request.GET.dict()
        params.update(request.POST.dict())
        return params

    def _verify_callback_checksum(self, params):
        """Проверить симметричную подпись уведомления.

        Пустой `VTB_CALLBACK_TOKEN` = проверка выключена: на деве и на проде
        до заполнения `.env.prod` поведение остаётся прежним.
        """
        token = getattr(settings, 'VTB_CALLBACK_TOKEN', '')
        if not token:
            # Строка обязательна: без неё «подпись сошлась» и «подпись не
            # проверялась» выглядят в логе одинаково, а потерянная при правке
            # `.env.prod` переменная бесшумно вернула бы прод в fail-open.
            logger.warning(
                'VTB callback: подпись НЕ проверяется — VTB_CALLBACK_TOKEN пуст'
            )
            return

        checksum = (params.get('checksum') or '').strip()
        if not checksum:
            # Отдельное сообщение, а не общее «invalid checksum»: если банк
            # пришлёт подпись под другим именем, это видно сразу по логу,
            # без раскопок в алгоритме HMAC.
            logger.error(
                'VTB callback ОТКЛОНЁН (нет checksum): mdOrder=%s',
                one_line(params.get('mdOrder', '')),
            )
            raise CallbackRejected('no checksum')

        # Регистр входящей суммы не фиксируем: банк шлёт верхний, но принять
        # нижний дешевле, чем отклонить настоящую оплату. Сравнение всё равно
        # постоянное по времени.
        # Сравниваем БАЙТЫ, а не строки: `compare_digest` на двух `str` требует
        # ASCII и на любой другой подписи бросает TypeError — а он пролетел бы
        # мимо `CallbackRejected` во вьюхе и превратил бы отказ в 500-ку
        # (`?checksum=ПОДПИСЬ` роняло обработчик, находка критика блока 2).
        expected = _callback_checksum(params, token).encode('utf-8')
        if not hmac.compare_digest(expected, checksum.upper().encode('utf-8')):
            logger.error(
                'VTB callback ОТКЛОНЁН (подпись не сошлась): mdOrder=%s',
                one_line(params.get('mdOrder', '')),
            )
            raise CallbackRejected('invalid checksum')

    def process_callback(self, request):
        params = self._callback_params(request)
        # Платформа RBS шлёт идентификатор платежа как `mdOrder`; `orderId`
        # оставлен ради ручных проверок и старого формата уведомлений.
        gateway_order_id = params.get('mdOrder') or params.get('orderId', '')

        # Лог до всех проверок — по нему разбирается первый боевой callback,
        # если формат или подпись не совпадут. Токен и checksum не пишем.
        # Значения — сырые query-параметры публичного URL: без one_line()
        # `%0A` дописывал в лог поддельную запись (PP-01).
        logger.info(
            'VTB callback: mdOrder=%s orderNumber=%s operation=%s status=%s',
            one_line(gateway_order_id), one_line(params.get('orderNumber', '')),
            one_line(params.get('operation', '')), one_line(params.get('status', '')),
        )

        self._verify_callback_checksum(params)

        if not gateway_order_id:
            return None, False

        try:
            order = Order.objects.get(payment_id=gateway_order_id)
        except Order.DoesNotExist:
            logger.warning('VTB callback: order not found for %s', one_line(gateway_order_id))
            return None, False

        status = self.check_status(gateway_order_id)
        return order, status.paid

    def refund(self, payment_id, amount=None):
        params = {'orderId': payment_id}
        if amount is not None:
            params['amount'] = int(amount * 100)
        return self._post('refund.do', params)
