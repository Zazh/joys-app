import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from emails.service import send_expired_paid_alert
from orders.gateways import get_gateway_by_code
from orders.models import Order

logger = logging.getLogger(__name__)

# Опрашиваем банк только по свежим заказам: платёжная сессия живёт минуты
# (sessionTimeoutSecs=1500), суток заведомо хватает, а старьё дёргать незачем.
LOOKBACK = timedelta(hours=24)


class Command(BaseCommand):
    help = (
        'Найти истёкшие заказы, по которым в банке всё же прошла оплата, '
        'и уведомить владельца. Статус заказа и склад не трогает.'
    )

    def handle(self, *args, **options):
        orders = Order.objects.filter(
            status=Order.Status.EXPIRED,
            payment_id__gt='',
            payment_gateway__gt='',
            expired_paid_alerted_at__isnull=True,
            expires_at__gte=timezone.now() - LOOKBACK,
        )

        if not orders.exists():
            self.stdout.write('Свежих истёкших заказов с оплатой нет.')
            return

        for order in orders:
            self.stdout.write(
                f'\n#{order.number} — {order.total_amount} — '
                f'gateway: {order.payment_gateway}'
            )

            try:
                gateway = get_gateway_by_code(order.payment_gateway)
                result = gateway.check_status(order.payment_id)
            except Exception as e:
                # Поле не трогаем: заказ вернётся в выборку следующим прогоном.
                self.stdout.write(self.style.ERROR(f'  Ошибка проверки: {e}'))
                continue

            if not result.paid:
                self.stdout.write(
                    f'  Оплаты нет (status: {getattr(result, "raw_status", "?")}) — '
                    f'перепроверим следующим прогоном.'
                )
                continue

            # Ни статуса, ни склада: `Order.expire()` уже снял резерв, и
            # автоматический confirm_payment увёл бы остатки в минус (Р-1
            # бэклога payments-hardening). Разбор — ручной, письмом.
            logger.error(
                'EXPIRED order %s has successful payment: gateway=%s payment_id=%s — '
                'деньги списаны, заказ истёк, нужен ручной разбор',
                order.number, order.payment_gateway, order.payment_id,
            )
            send_expired_paid_alert(order)

            order.expired_paid_alerted_at = timezone.now()
            order.save(update_fields=['expired_paid_alerted_at'])
            self.stdout.write(self.style.WARNING(
                '  ⚠ Банк подтверждает оплату — алерт владельцу отправлен.'
            ))
