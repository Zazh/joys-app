import base64
import json
import logging
import secrets

import requests
from django.conf import settings

from orders.models import Order
from .base import BaseGateway, CallbackRejected, PaymentResult, PaymentStatus

logger = logging.getLogger(__name__)

# invoiceId по требованиям ePay — цифровая строка. Берём 15 случайных цифр:
# номер заказа (YYMMDD-NNNN) предсказуем, и по нему можно было бы подобрать
# чужой платёж в callback.
INVOICE_ID_DIGITS = 15


class HalykGateway(BaseGateway):
    """Halyk Bank ePay (epay.homebank.kz / test-epay.epayment.kz)."""

    code = 'halyk'

    def __init__(self):
        self.oauth_url = settings.HALYK_OAUTH_URL
        self.payment_url = settings.HALYK_PAYMENT_URL.rstrip('/')
        self.client_id = settings.HALYK_CLIENT_ID
        self.client_secret = settings.HALYK_CLIENT_SECRET
        self.terminal_id = settings.HALYK_TERMINAL_ID
        self.callback_public_key = settings.HALYK_CALLBACK_PUBLIC_KEY

    @staticmethod
    def _generate_invoice_id():
        """Непредсказуемый цифровой invoiceId, уникальный в рамках заказов."""
        for _ in range(10):
            invoice_id = ''.join(secrets.choice('0123456789') for _ in range(INVOICE_ID_DIGITS))
            if not Order.objects.filter(payment_id=invoice_id).exists():
                return invoice_id
        raise RuntimeError('Не удалось сгенерировать уникальный invoiceId')

    def _get_token(self, order, invoice_id, callback_url):
        """Получить OAuth token для платежа."""
        amount = int(order.total_amount)
        data = {
            'grant_type': 'client_credentials',
            'scope': 'payment',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'invoiceID': invoice_id,
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
        invoice_id = self._generate_invoice_id()

        token_data = self._get_token(order, invoice_id, callback_url)
        if not token_data or 'access_token' not in token_data:
            error = token_data.get('error_description', 'Token error') if token_data else 'Connection error'
            logger.error('Halyk token failed for order %s: %s', order.number, error)
            return PaymentResult(success=False, error_message=error)

        amount = int(order.total_amount)

        # Payment object — точно по документации Halyk ePay
        payment_object = {
            'invoiceId': invoice_id,
            'invoiceIdAlt': invoice_id,
            'backLink': return_url + f'?invoiceId={invoice_id}',
            'failureBackLink': return_url + f'?invoiceId={invoice_id}',
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
            order.number, amount, invoice_id,
        )

        return PaymentResult(
            success=True,
            payment_id=invoice_id,
            payment_url='__halyk__',
            _payment_object=payment_object,
        )

    def check_status(self, payment_id):
        # У Halyk нет серверного API проверки статуса, как getOrderStatusExtended
        # у VTB. Единственный источник истины — подписанный callback (postLink),
        # поэтому здесь просто возвращаем то, что уже записано у нас.
        try:
            order = Order.objects.get(payment_id=payment_id)
            return PaymentStatus(
                paid=(order.status == Order.Status.PAID),
                raw_status=order.status,
            )
        except Order.DoesNotExist:
            return PaymentStatus(paid=False, raw_status='not_found')

    def _verify_signature(self, raw_body, signature_b64):
        """Проверить подпись callback публичным ключом терминала.

        Halyk подписывает тело postLink закрытым ключом; открытый ключ выдаёт
        банк вместе с боевым терминалом. Пока ключ не задан — считаем callback
        неподтверждённым (fail-closed), иначе оплату можно подделать обычным
        POST-запросом.
        """
        if not self.callback_public_key:
            return False
        if not signature_b64:
            return False

        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
        except ImportError:
            logger.error('Halyk callback: пакет cryptography не установлен — подпись не проверить')
            return False

        try:
            public_key = serialization.load_pem_public_key(
                self.callback_public_key.encode()
            )
            public_key.verify(
                base64.b64decode(signature_b64),
                raw_body,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return True
        except Exception as e:
            logger.warning('Halyk callback: подпись невалидна (%s)', e)
            return False

    def process_callback(self, request):
        raw_body = request.body or b''

        # Halyk шлёт POST на postLink с JSON или form data
        try:
            if request.content_type and 'json' in request.content_type:
                data = json.loads(raw_body)
            else:
                data = request.POST.dict()
        except (json.JSONDecodeError, ValueError):
            data = request.POST.dict()

        invoice_id = data.get('invoiceId') or data.get('invoiceID', '')
        code = data.get('code', '')
        reason_code = data.get('reasonCode')
        signature = (
            data.get('signature')
            or request.headers.get('X-Signature', '')
        )

        # Без полного payload — он содержит платёжные данные
        logger.info(
            'Halyk callback: invoiceId=%s code=%s reasonCode=%s',
            invoice_id, code, reason_code,
        )

        signature_body = raw_body if raw_body else invoice_id.encode()
        if not self._verify_signature(signature_body, signature):
            logger.error(
                'Halyk callback ОТКЛОНЁН (нет валидной подписи): invoiceId=%s ip=%s',
                invoice_id, request.META.get('REMOTE_ADDR', ''),
            )
            raise CallbackRejected('invalid signature')

        if not invoice_id:
            raise CallbackRejected('no invoiceId')

        try:
            order = Order.objects.get(payment_id=invoice_id)
        except Order.DoesNotExist:
            logger.warning('Halyk callback: order not found for %s', invoice_id)
            raise CallbackRejected('unknown invoiceId')

        # Сумма и валюта должны совпасть с заказом — иначе оплата 1 ₸
        # закрыла бы заказ на любую сумму.
        callback_amount = data.get('amount')
        if callback_amount is not None and int(callback_amount) != int(order.total_amount):
            logger.error(
                'Halyk callback: сумма не совпала order=%s ожидали=%s пришло=%s',
                order.number, int(order.total_amount), callback_amount,
            )
            raise CallbackRejected('amount mismatch')

        callback_currency = data.get('currency')
        if callback_currency and str(callback_currency).upper() != 'KZT':
            logger.error(
                'Halyk callback: валюта не совпала order=%s пришло=%s',
                order.number, callback_currency,
            )
            raise CallbackRejected('currency mismatch')

        # code='ok' и reasonCode=0 означает успешную оплату
        paid = (str(code).lower() == 'ok' and str(reason_code) == '0')
        return order, paid

    def refund(self, payment_id, amount=None):
        logger.warning('Halyk refund not implemented yet')
        return {'error': 'not implemented'}
