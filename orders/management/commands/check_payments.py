from django.core.management.base import BaseCommand

from orders.gateways import get_gateway_by_code
from orders.models import Order


class Command(BaseCommand):
    help = 'Проверить и подтвердить оплаченные заказы через шлюз'

    def add_arguments(self, parser):
        parser.add_argument(
            '--order', type=str,
            help='Номер конкретного заказа (например 260318-0002)',
        )

    def handle(self, *args, **options):
        if options['order']:
            orders = Order.objects.filter(
                number=options['order'], status=Order.Status.PENDING,
            )
        else:
            orders = Order.objects.filter(
                status=Order.Status.PENDING,
                payment_gateway__gt='',
            )

        if not orders.exists():
            self.stdout.write('Нет pending заказов с оплатой.')
            return

        for order in orders:
            self.stdout.write(f'\n#{order.number} — {order.total_amount} — gateway: {order.payment_gateway}')

            try:
                gateway = get_gateway_by_code(order.payment_gateway)
                result = gateway.check_status(order.payment_id)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Ошибка проверки: {e}'))
                continue

            if result.paid:
                order.confirm_payment()
                self.stdout.write(self.style.SUCCESS(f'  ✓ Оплачен — подтверждён'))
            else:
                self.stdout.write(f'  Не оплачен (status: {getattr(result, "raw_status", "?")})')
