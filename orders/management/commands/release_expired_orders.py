from django.core.management.base import BaseCommand
from django.utils import timezone

from orders.models import Order


class Command(BaseCommand):
    help = 'Снимает резерв с неоплаченных заказов, у которых истёк срок оплаты'

    def handle(self, *args, **options):
        expired = Order.objects.filter(
            status=Order.Status.PENDING,
            expires_at__lt=timezone.now(),
        )
        count = expired.count()
        if not count:
            self.stdout.write('Нет истёкших заказов.')
            return

        for order in expired:
            order.expire()
            self.stdout.write(f'  Заказ #{order.number} → expired, резерв снят')

        self.stdout.write(self.style.SUCCESS(f'Обработано: {count}'))
