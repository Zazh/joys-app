from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import Order


@receiver(pre_save, sender=Order)
def order_status_changed(sender, instance, **kwargs):
    """Отправить email при смене статуса заказа на SHIPPED."""
    if not instance.pk:
        return

    try:
        old = Order.objects.get(pk=instance.pk)
    except Order.DoesNotExist:
        return

    if old.status != instance.status and instance.status == Order.Status.SHIPPED:
        from .emails import send_order_shipped_email
        send_order_shipped_email(instance)
