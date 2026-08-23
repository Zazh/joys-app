from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Order


@receiver(pre_save, sender=Order)
def remember_old_status(sender, instance, **kwargs):
    """Запомнить статус из БД до записи — сравнивает его post_save-обработчик."""
    if not instance.pk:
        instance._old_status = None
        return
    instance._old_status = (
        Order.objects.filter(pk=instance.pk)
        .values_list('status', flat=True)
        .first()
    )


@receiver(post_save, sender=Order)
def send_shipped_email(sender, instance, created, **kwargs):
    """Письмо «заказ отправлен» — только за состоявшуюся запись в БД.

    Расщеплено из pre_save (PP-03): там письмо уходило ДО save(), и упавшая
    запись оставляла покупателя с ложным «отправлен». Отправка — через
    transaction.on_commit, чтобы будущий переход в SHIPPED внутри транзакции
    не ходил в SendPulse под блокировками (зеркало PH-06); при откате
    транзакции колбэк не выполняется — письмо не уходит.
    """
    if created:
        return
    old_status = getattr(instance, '_old_status', None)
    if old_status is None or old_status == instance.status:
        return
    if instance.status != Order.Status.SHIPPED:
        return
    from emails.service import send_order_shipped_email
    transaction.on_commit(lambda: send_order_shipped_email(instance))
