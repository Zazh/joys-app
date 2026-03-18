import json
import logging

import requests
from django.conf import settings

from orders.models import Order
from .base import BaseGateway, PaymentResult, PaymentStatus

logger = logging.getLogger(__name__)


class HalykGateway(BaseGateway):
    """Halyk Bank ePay (epay.homebank.kz / test-epay.epayment.kz)."""

    code = 'halyk'

    def __init__(self):
        self.oauth_url = settings.HALYK_OAUTH_URL
        self.payment_url = settings.HALYK_PAYMENT_URL.rstrip('/')
        self.client_id = settings.HALYK_CLIENT_ID
        self.client_secret = settings.HALYK_CLIENT_SECRET
        self.terminal_id = settings.HALYK_TERMINAL_ID

    def _get_token(self, order, callback_url):
        """Получить OAuth token для платежа."""
        amount = int(order.total_amount)
        data = {
            'grant_type': 'client_credentials',
            'scope': 'payment',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'invoiceID': order.number.replace('-', ''),
            'amount': amount,
            'currency': 'KZT',
            'terminal': self.terminal_id,
            'postLink': callback_url,
            'failurePostLink': callback_url,
        }
        try:
            resp = requests.post(self.oauth_url, data=data, timeout=30)
            resp.raise_for_status()
            token_data = resp.json()
            # Halyk возвращает expires_in как строку, JS SDK ожидает число
            if 'expires_in' in token_data:
                token_data['expires_in'] = int(token_data['expires_in'])
            return token_data
        except requests.RequestException as e:
            logger.error('Halyk OAuth error: %s', e)
            return None

    # ── BaseGateway interface ──

    def create_payment(self, order, return_url, callback_url):
        token_data = self._get_token(order, callback_url)
        if not token_data or 'access_token' not in token_data:
            error = token_data.get('error_description', 'Token error') if token_data else 'Connection error'
            logger.error('Halyk token failed for order %s: %s', order.number, error)
            return PaymentResult(success=False, error_message=error)

        payment_id = order.number.replace('-', '')
        amount = int(order.total_amount)

        # Payment object — точно по документации Halyk ePay
        payment_object = {
            'invoiceId': order.number.replace('-', ''),
            'invoiceIdAlt': order.number.replace('-', ''),
            'backLink': return_url + f'?invoiceId={order.number.replace("-", "")}',
            'failureBackLink': return_url + f'?invoiceId={order.number.replace("-", "")}',
            'postLink': callback_url,
            'failurePostLink': callback_url,
            'language': 'rus',
            'description': f'Order {order.number}',
            'accountId': str(order.user_id or ''),
            'terminal': self.terminal_id,
            'amount': amount,
            'currency': 'KZT',
            'auth': token_data,
        }

        logger.info(
            'Halyk payment object: order=%s amount=%s invoiceId=%s',
            order.number, amount, payment_id,
        )

        return PaymentResult(
            success=True,
            payment_id=payment_id,
            payment_url='__halyk__',
            _payment_object=payment_object,
        )

    def check_status(self, payment_id):
        # Halyk не имеет серверного API проверки статуса как VTB.
        # Статус приходит только через callback (postLink).
        # При return проверяем по статусу заказа в нашей БД.
        try:
            order = Order.objects.get(payment_id=payment_id)
            return PaymentStatus(
                paid=(order.status == Order.Status.PAID),
                raw_status=order.status,
            )
        except Order.DoesNotExist:
            return PaymentStatus(paid=False, raw_status='not_found')

    def process_callback(self, request):
        # Halyk шлёт POST на postLink с JSON или form data
        try:
            if request.content_type and 'json' in request.content_type:
                data = json.loads(request.body)
            else:
                data = request.POST.dict()
        except (json.JSONDecodeError, ValueError):
            data = request.POST.dict()

        invoice_id = data.get('invoiceId') or data.get('invoiceID', '')
        code = data.get('code', '')
        reason_code = data.get('reasonCode')

        logger.info(
            'Halyk callback: invoiceId=%s code=%s reasonCode=%s data=%s',
            invoice_id, code, reason_code, data,
        )

        if not invoice_id:
            return None, False

        try:
            order = Order.objects.get(payment_id=invoice_id)
        except Order.DoesNotExist:
            logger.warning('Halyk callback: order not found for %s', invoice_id)
            return None, False

        # code='ok' и reasonCode=0 означает успешную оплату
        paid = (str(code).lower() == 'ok' and str(reason_code) == '0')
        return order, paid

    def refund(self, payment_id, amount=None):
        logger.warning('Halyk refund not implemented yet')
        return {'error': 'not implemented'}
