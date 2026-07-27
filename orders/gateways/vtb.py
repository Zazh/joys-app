import logging
import os
import tempfile

import certifi
import requests
from django.conf import settings

from orders.models import Order
from .base import BaseGateway, PaymentResult, PaymentStatus

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

# ISO 4217 numeric codes
CURRENCY_NUMERIC = {
    'KZT': '398',
    'RUB': '643',
    'USD': '840',
    'EUR': '978',
    'UZS': '860',
    'KGS': '417',
}


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

    def process_callback(self, request):
        gateway_order_id = (
            request.POST.get('orderId')
            or request.GET.get('orderId', '')
        )
        if not gateway_order_id:
            return None, False

        try:
            order = Order.objects.get(payment_id=gateway_order_id)
        except Order.DoesNotExist:
            logger.warning('VTB callback: order not found for %s', gateway_order_id)
            return None, False

        status = self.check_status(gateway_order_id)
        return order, status.paid

    def refund(self, payment_id, amount=None):
        params = {'orderId': payment_id}
        if amount is not None:
            params['amount'] = int(amount * 100)
        return self._post('refund.do', params)
