from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from catalog.models import ProductSize, Stock
from regions.models import Region


class Order(models.Model):
    """Заказ в интернет-магазине."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Ожидает оплаты'
        PAID = 'paid', 'Оплачен'
        SHIPPED = 'shipped', 'Отправлен'
        DELIVERED = 'delivered', 'Доставлен'
        CANCELLED = 'cancelled', 'Отменён'
        EXPIRED = 'expired', 'Истёк'

    number = models.CharField('Номер', max_length=20, unique=True, editable=False)
    status = models.CharField(
        'Статус', max_length=20,
        choices=Status.choices, default=Status.PENDING,
    )
    region = models.ForeignKey(
        Region, on_delete=models.PROTECT,
        related_name='orders', verbose_name='Регион',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='orders', verbose_name='Пользователь',
    )

    # Покупатель
    customer_name = models.CharField('ФИО', max_length=200)
    customer_phone = models.CharField('Телефон', max_length=20)
    customer_email = models.EmailField('Email', blank=True)

    # Доставка
    city = models.CharField('Город', max_length=100)
    address = models.TextField('Адрес')

    # Оплата
    payment_gateway = models.CharField(
        'Шлюз', max_length=20, blank=True,
        help_text='Код шлюза: vtb, halyk',
    )
    payment_id = models.CharField('ID платежа', max_length=200, blank=True,
        help_text='ID транзакции от эквайринга',
    )
    payment_url = models.URLField('Ссылка на оплату', blank=True)
    total_amount = models.DecimalField('Сумма заказа', max_digits=10, decimal_places=2,
        help_text='В валюте оплаты (KZT если конвертация)',
    )
    display_amount = models.DecimalField(
        'Сумма отображения', max_digits=10, decimal_places=2,
        null=True, blank=True,
        help_text='Сумма в валюте отображения (напр. RUB), если отличается от валюты оплаты',
    )
    display_currency_code = models.CharField(
        'Валюта отображения', max_length=3, blank=True,
        help_text='Код валюты отображения (напр. RUB)',
    )
    exchange_rate_snapshot = models.DecimalField(
        'Курс на момент заказа', max_digits=12, decimal_places=4,
        null=True, blank=True,
        help_text='Курс конвертации: 1 единица display_currency = X KZT',
    )

    # Даты
    expires_at = models.DateTimeField('Истекает',
        help_text='Срок действия счёта на оплату',
    )
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    paid_at = models.DateTimeField('Оплачен', null=True, blank=True)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'expires_at']),
            models.Index(fields=['number']),
            models.Index(fields=['payment_id']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f'Заказ #{self.number}'

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self._generate_number()
        super().save(*args, **kwargs)

    def _generate_number(self):
        """Генерация номера заказа: YYMMDD-XXXX."""
        today = timezone.now().strftime('%y%m%d')
        last = (
            Order.objects
            .filter(number__startswith=today)
            .order_by('-number')
            .values_list('number', flat=True)
            .first()
        )
        if last:
            seq = int(last.split('-')[1]) + 1
        else:
            seq = 1
        return f'{today}-{seq:04d}'

    # ─── Бизнес-логика ───

    @transaction.atomic
    def reserve_stock(self):
        """Зарезервировать товар на складе при создании заказа."""
        for item in self.items.select_related('size'):
            stock = Stock.objects.select_for_update().get(
                size=item.size, region=self.region,
            )
            stock.reserved += item.quantity
            stock.save(update_fields=['reserved', 'updated_at'])

    @transaction.atomic
    def release_stock(self):
        """Снять резерв (заказ отменён или истёк)."""
        for item in self.items.select_related('size'):
            try:
                stock = Stock.objects.select_for_update().get(
                    size=item.size, region=self.region,
                )
                stock.reserved = max(0, stock.reserved - item.quantity)
                stock.save(update_fields=['reserved', 'updated_at'])
            except Stock.DoesNotExist:
                pass

    @transaction.atomic
    def confirm_payment(self):
        """Оплата подтверждена — списать со склада.

        Использует select_for_update для защиты от двойного подтверждения
        (callback и return могут прийти одновременно).
        """
        locked = Order.objects.select_for_update().get(pk=self.pk)
        if locked.status != self.Status.PENDING:
            return  # Уже обработан — идемпотентно
        locked.status = self.Status.PAID
        locked.paid_at = timezone.now()
        locked.save(update_fields=['status', 'paid_at'])

        for item in locked.items.select_related('size'):
            try:
                stock = Stock.objects.select_for_update().get(
                    size=item.size, region=locked.region,
                )
                stock.quantity = max(0, stock.quantity - item.quantity)
                stock.reserved = max(0, stock.reserved - item.quantity)
                stock.save(update_fields=['quantity', 'reserved', 'updated_at'])
            except Stock.DoesNotExist:
                pass

        # Обновить self чтобы вызывающий код видел новый статус
        self.status = locked.status
        self.paid_at = locked.paid_at

        # Отправить email о подтверждении оплаты
        from emails.service import send_payment_confirmed_email
        send_payment_confirmed_email(locked)

    @transaction.atomic
    def cancel(self):
        """Отменить заказ — снять резерв."""
        locked = Order.objects.select_for_update().get(pk=self.pk)
        if locked.status != self.Status.PENDING:
            return
        locked.release_stock()
        locked.status = self.Status.CANCELLED
        locked.save(update_fields=['status'])
        self.status = locked.status

    @transaction.atomic
    def expire(self):
        """Заказ истёк — снять резерв."""
        locked = Order.objects.select_for_update().get(pk=self.pk)
        if locked.status != self.Status.PENDING:
            return
        locked.release_stock()
        locked.status = self.Status.EXPIRED
        locked.save(update_fields=['status'])
        self.status = locked.status


class OrderStatusLog(models.Model):
    """История изменений статуса заказа."""
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE,
        related_name='status_logs', verbose_name='Заказ',
    )
    old_status = models.CharField('Старый статус', max_length=20, choices=Order.Status.choices)
    new_status = models.CharField('Новый статус', max_length=20, choices=Order.Status.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Кто изменил',
    )
    changed_at = models.DateTimeField('Дата', auto_now_add=True)
    comment = models.TextField('Комментарий', blank=True)

    class Meta:
        verbose_name = 'История статуса заказа'
        verbose_name_plural = 'История статусов заказов'
        ordering = ['-changed_at']

    def __str__(self):
        return f'{self.order.number}: {self.old_status} → {self.new_status}'


class OrderItem(models.Model):
    """Позиция в заказе."""
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE,
        related_name='items', verbose_name='Заказ',
    )
    size = models.ForeignKey(
        ProductSize, on_delete=models.PROTECT,
        related_name='order_items', verbose_name='Размер',
    )
    # Фиксируем на момент заказа
    product_name = models.CharField('Название товара', max_length=300)
    size_name = models.CharField('Размер', max_length=50)
    quantity = models.PositiveIntegerField('Количество', default=1)
    price = models.DecimalField('Цена за ед.', max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'

    def __str__(self):
        return f'{self.product_name} ({self.size_name}) × {self.quantity}'

    @property
    def subtotal(self):
        return self.price * self.quantity


# ─── Корзина (БД) ───

class CartItem(models.Model):
    """Позиция корзины для авторизованного пользователя."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='cart_items', verbose_name='Пользователь',
    )
    size = models.ForeignKey(
        ProductSize, on_delete=models.CASCADE,
        related_name='cart_items', verbose_name='Размер',
    )
    qty = models.PositiveIntegerField('Количество', default=1)
    created_at = models.DateTimeField('Добавлен', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Корзина'
        verbose_name_plural = 'Корзина'
        unique_together = ['user', 'size']

    def __str__(self):
        return f'{self.user} — {self.size} × {self.qty}'


# ─── Избранное (БД) ───

class FavoriteItem(models.Model):
    """Избранный товар для авторизованного пользователя."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='favorite_items', verbose_name='Пользователь',
    )
    product = models.ForeignKey(
        'catalog.Product', on_delete=models.CASCADE,
        related_name='favorite_items', verbose_name='Товар',
    )
    created_at = models.DateTimeField('Добавлен', auto_now_add=True)

    class Meta:
        verbose_name = 'Избранное'
        verbose_name_plural = 'Избранное'
        unique_together = ['user', 'product']

    def __str__(self):
        return f'{self.user} — {self.product}'
