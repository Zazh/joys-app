from decimal import InvalidOperation, Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from .utils import optimize_image_field


# ─── Категория ───

class Category(models.Model):
    name = models.CharField('Название', max_length=200)
    slug = models.SlugField('Slug', max_length=200, unique=True)
    description = models.TextField('Описание', blank=True)
    image = models.ImageField('Обложка', upload_to='categories/', blank=True)
    is_active = models.BooleanField('Активна', default=True)
    order = models.PositiveIntegerField('Порядок', default=0)
    meta_title = models.CharField('META Title', max_length=200, blank=True)
    meta_description = models.TextField('META Description', blank=True)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['order', 'name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active', 'order']),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('catalog:category', kwargs={'category_slug': self.slug})

    def save(self, *args, **kwargs):
        if self.image:
            if self.pk:
                try:
                    old = Category.objects.get(pk=self.pk)
                    image_changed = old.image.name != self.image.name
                except Category.DoesNotExist:
                    image_changed = True
            else:
                image_changed = True
            if image_changed:
                result = optimize_image_field(self.image, max_width=600, quality=100)
                if result:
                    self.image = result
        super().save(*args, **kwargs)


# ─── Товар ───

class Product(models.Model):

    class Badge(models.TextChoices):
        BESTSELLER = 'bestseller', 'Хит продаж'
        NEW = 'new', 'Новинка'
        SALE = 'sale', 'Скидка'

    name = models.CharField('Название', max_length=300)
    tagline = models.CharField('УТП', max_length=500, blank=True,
        help_text='Уникальное торговое предложение. Выводится вместо названия на сайте.',
    )
    slug = models.SlugField('Slug', max_length=300, unique=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
        verbose_name='Категория',
    )

    description = models.TextField('Описание', blank=True)

    badge = models.CharField(
        'Бейдж', max_length=20, choices=Badge.choices, blank=True,
    )
    is_active = models.BooleanField('Активен', default=True)

    pack_quantity = models.PositiveIntegerField(
        'Кол-во в упаковке', null=True, blank=True,
        help_text='Количество штук в упаковке (5, 17, 30, 34 и т.д.).',
    )

    # Прозрачное фото (для квиза, промо-блоков)
    transparent_image = models.ImageField(
        'Прозрачное фото RU (PNG)', upload_to='products/transparent/', blank=True,
        help_text='PNG с прозрачным фоном. Для результатов квиза и промо.',
    )
    transparent_image_kk = models.ImageField(
        'Прозрачное фото KK (PNG)', upload_to='products/transparent/kk/', blank=True,
        help_text='Казахская версия. Если пусто — используется основное.',
    )

    # Zoom (одна картинка, скролл-эффект)
    zoom_image = models.ImageField(
        'Zoom изображение', upload_to='products/zoom/', blank=True,
    )
    zoom_rotation_angle = models.IntegerField(
        'Угол поворота (GSAP)', default=15,
        help_text='Градус поворота для zoom-эффекта при скролле',
    )

    meta_title = models.CharField('META Title', max_length=200, blank=True)
    meta_description = models.TextField('META Description', blank=True)

    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active', 'category']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('catalog:product_detail', kwargs={
            'category_slug': self.category.slug,
            'product_slug': self.slug,
        })

    def get_cover_image(self):
        """Обложка: помеченная is_cover, иначе первое основное фото."""
        images = self.main_images.all()
        return (
            next((img for img in images if img.is_cover), None)
            or next(iter(images), None)
        )

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                old = Product.objects.get(pk=self.pk)
            except Product.DoesNotExist:
                old = None
        else:
            old = None

        # Zoom: max height 1200px, WebP
        if self.zoom_image:
            changed = not old or old.zoom_image.name != self.zoom_image.name
            if changed:
                result = optimize_image_field(self.zoom_image, max_height=1200, quality=100)
                if result:
                    self.zoom_image = result

        # Прозрачное фото: max height 400px, PNG
        if self.transparent_image:
            changed = not old or old.transparent_image.name != self.transparent_image.name
            if changed:
                result = optimize_image_field(
                    self.transparent_image, max_height=400,
                    preserve_transparency=True,
                )
                if result:
                    self.transparent_image = result

        # Прозрачное фото KK
        if self.transparent_image_kk:
            changed = not old or old.transparent_image_kk.name != self.transparent_image_kk.name
            if changed:
                result = optimize_image_field(
                    self.transparent_image_kk, max_height=400,
                    preserve_transparency=True,
                )
                if result:
                    self.transparent_image_kk = result

        super().save(*args, **kwargs)


# ─── Размеры (варианты) ───

class ProductSize(models.Model):
    """Размер товара с артикулом и ценой."""
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE,
        related_name='sizes', verbose_name='Товар',
    )
    name = models.CharField('Размер', max_length=50,
        help_text='Например: M, L, XL, 3 шт, 12 шт',
    )
    sku = models.CharField('Артикул', max_length=50, unique=True)

    price = models.DecimalField('Базовая цена', max_digits=10, decimal_places=2,
        help_text='Fallback-цена (KZT). Региональные цены в RegionPrice.',
    )
    old_price = models.DecimalField(
        'Старая базовая цена', max_digits=10, decimal_places=2, blank=True, null=True,
    )

    order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Размер'
        verbose_name_plural = 'Размеры'
        ordering = ['order', 'name']
        indexes = [
            models.Index(fields=['sku']),
        ]

    def __str__(self):
        return f'{self.product.name} — {self.name}'

    @property
    def in_stock(self):
        """Наличие для текущего региона (через prefetch _stocks)."""
        if hasattr(self, '_stocks') and self._stocks:
            return self._stocks[0].available > 0
        return True  # fallback: считаем в наличии

    @property
    def has_discount(self):
        return self.old_price is not None and self.old_price > self.price

    @property
    def discount_percent(self):
        if self.has_discount:
            return round((1 - self.price / self.old_price) * 100)
        return 0


# ─── Региональные цены ───

class RegionPrice(models.Model):
    """Цена варианта товара для конкретного региона."""
    size = models.ForeignKey(
        ProductSize, on_delete=models.CASCADE,
        related_name='region_prices', verbose_name='Размер',
    )
    region = models.ForeignKey(
        'regions.Region', on_delete=models.CASCADE,
        related_name='prices', verbose_name='Регион',
    )
    price = models.DecimalField('Цена', max_digits=10, decimal_places=2)
    old_price = models.DecimalField(
        'Старая цена', max_digits=10, decimal_places=2,
        blank=True, null=True,
    )

    class Meta:
        verbose_name = 'Цена региона'
        verbose_name_plural = 'Цены регионов'
        unique_together = ['size', 'region']
        indexes = [
            models.Index(fields=['size', 'region']),
        ]

    def __str__(self):
        return f'{self.size} — {self.region.code}: {self.price} {self.region.currency_symbol}'

    @property
    def has_discount(self):
        return self.old_price is not None and self.old_price > self.price

    @property
    def discount_percent(self):
        if self.has_discount:
            return round((1 - self.price / self.old_price) * 100)
        return 0


# ─── Остатки ───

class Stock(models.Model):
    """Остаток товара (размер × регион) для интернет-магазина."""
    size = models.ForeignKey(
        ProductSize, on_delete=models.CASCADE,
        related_name='stocks', verbose_name='Размер',
    )
    region = models.ForeignKey(
        'regions.Region', on_delete=models.CASCADE,
        related_name='stocks', verbose_name='Регион',
    )
    quantity = models.PositiveIntegerField('Остаток', default=0)
    reserved = models.PositiveIntegerField('Зарезервировано', default=0,
        help_text='Зарезервировано в неоплаченных заказах',
    )
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Остаток'
        verbose_name_plural = 'Остатки'
        unique_together = ['size', 'region']
        indexes = [
            models.Index(fields=['size', 'region']),
        ]

    def __str__(self):
        return f'{self.size} — {self.region.code}: {self.available} шт'

    @property
    def available(self):
        """Доступно для продажи = остаток − резерв."""
        return max(0, self.quantity - self.reserved)

    @property
    def in_stock(self):
        return self.available > 0


# ─── Характеристики ───

class UnitOfMeasure(models.Model):
    """Единица измерения с типом данных значения."""

    class DataType(models.TextChoices):
        TEXT = 'text', 'Строка'
        INTEGER = 'integer', 'Целое число'
        DECIMAL = 'decimal', 'Десятичное число'

    name = models.CharField('Название', max_length=100)
    abbr = models.CharField('Сокращение', max_length=20)
    data_type = models.CharField(
        'Тип данных', max_length=10,
        choices=DataType.choices, default=DataType.TEXT,
    )

    class Meta:
        verbose_name = 'Единица измерения'
        verbose_name_plural = 'Единицы измерения'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.abbr})'


class Characteristic(models.Model):
    """Определение характеристики (Толщина, Материал и т.д.)."""
    name = models.CharField('Название', max_length=200)
    unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Единица измерения',
        help_text='Если не указана — значение свободный текст',
    )
    order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Характеристика'
        verbose_name_plural = 'Характеристики'
        ordering = ['order', 'name']

    def __str__(self):
        if self.unit:
            return f'{self.name} ({self.unit.abbr})'
        return self.name


class ProductCharacteristic(models.Model):
    """Значение характеристики для конкретного товара."""
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE,
        related_name='characteristics', verbose_name='Товар',
    )
    characteristic = models.ForeignKey(
        Characteristic, on_delete=models.CASCADE,
        verbose_name='Характеристика',
    )
    value = models.CharField('Значение', max_length=500)
    subtitle = models.CharField('Подпись', max_length=500, blank=True, default='',
                                help_text='Вспомогательный текст под значением (опционально)')

    class Meta:
        verbose_name = 'Характеристика товара'
        verbose_name_plural = 'Характеристики товара'
        unique_together = ['product', 'characteristic']
        ordering = ['characteristic__order']

    def __str__(self):
        return f'{self.characteristic.name}: {self.value}'

    def clean(self):
        """Валидация значения по типу данных юнита."""
        unit = self.characteristic.unit if self.characteristic_id else None
        if not unit:
            return  # текст — любое значение допустимо

        if unit.data_type == UnitOfMeasure.DataType.INTEGER:
            try:
                int(self.value)
            except (ValueError, TypeError):
                raise ValidationError(
                    {'value': f'Для "{self.characteristic.name}" нужно целое число'}
                )
        elif unit.data_type == UnitOfMeasure.DataType.DECIMAL:
            try:
                Decimal(self.value)
            except (InvalidOperation, ValueError, TypeError):
                raise ValidationError(
                    {'value': f'Для "{self.characteristic.name}" нужно число'}
                )


# ─── Изображения товара ───

class ProductMainImage(models.Model):
    """Основные фото товара. Одно помечается как обложка (is_cover)."""
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE,
        related_name='main_images', verbose_name='Товар',
    )
    image = models.ImageField('Изображение (RU)', upload_to='products/main/')
    image_kk = models.ImageField(
        'Изображение (KK)', upload_to='products/main/kk/',
        blank=True, help_text='Фото пачки на казахском. Если пусто — используется основное.',
    )
    thumbnail = models.ImageField(
        'Миниатюра', upload_to='products/thumbs/',
        blank=True, editable=False,
    )
    thumbnail_kk = models.ImageField(
        'Миниатюра (KK)', upload_to='products/thumbs/kk/',
        blank=True, editable=False,
    )
    alt_text = models.CharField('Alt текст', max_length=300, blank=True)
    is_cover = models.BooleanField('Обложка', default=False,
        help_text='Главная картинка товара (одна на товар)',
    )
    order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Основное фото'
        verbose_name_plural = 'Основные фото'
        ordering = ['-is_cover', 'order']

    def __str__(self):
        cover = ' [обложка]' if self.is_cover else ''
        return f'{self.product.name} — основное{cover}'

    def _image_changed(self, field_name):
        if not self.pk:
            return True
        try:
            old = ProductMainImage.objects.get(pk=self.pk)
            return getattr(old, field_name).name != getattr(self, field_name).name
        except ProductMainImage.DoesNotExist:
            return True

    def save(self, *args, **kwargs):
        # Основное изображение (RU)
        if self.image and self._image_changed('image'):
            # Thumbnail из оригинала ДО сжатия основного
            thumb = optimize_image_field(self.image, max_height=800, quality=100)
            if thumb:
                self.thumbnail = thumb
            result = optimize_image_field(self.image, max_height=1200, quality=100)
            if result:
                self.image = result
        # Казахское изображение
        if self.image_kk and self._image_changed('image_kk'):
            thumb = optimize_image_field(self.image_kk, max_height=800, quality=100)
            if thumb:
                self.thumbnail_kk = thumb
            result = optimize_image_field(self.image_kk, max_height=1200, quality=100)
            if result:
                self.image_kk = result
        super().save(*args, **kwargs)


class ProductPackageImage(models.Model):
    """Фото упаковки (слайдер)."""
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE,
        related_name='package_images', verbose_name='Товар',
    )
    image = models.ImageField('Изображение', upload_to='products/package/')
    alt_text = models.CharField('Alt текст', max_length=300, blank=True)
    order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Фото упаковки'
        verbose_name_plural = 'Фото упаковки'
        ordering = ['order']

    def __str__(self):
        return f'{self.product.name} — упаковка'

    def save(self, *args, **kwargs):
        if self.image:
            if self.pk:
                try:
                    old = ProductPackageImage.objects.get(pk=self.pk)
                    image_changed = old.image.name != self.image.name
                except ProductPackageImage.DoesNotExist:
                    image_changed = True
            else:
                image_changed = True
            if image_changed:
                result = optimize_image_field(self.image, max_height=1000, quality=100)
                if result:
                    self.image = result
        super().save(*args, **kwargs)


class ProductIndividualImage(models.Model):
    """Фото индивидуальной упаковки (слайдер)."""
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE,
        related_name='individual_images', verbose_name='Товар',
    )
    image = models.ImageField('Изображение', upload_to='products/individual/')
    alt_text = models.CharField('Alt текст', max_length=300, blank=True)
    order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Фото индивидуальной упаковки'
        verbose_name_plural = 'Фото индивидуальной упаковки'
        ordering = ['order']

    def __str__(self):
        return f'{self.product.name} — индивидуальная'

    def save(self, *args, **kwargs):
        if self.image:
            if self.pk:
                try:
                    old = ProductIndividualImage.objects.get(pk=self.pk)
                    image_changed = old.image.name != self.image.name
                except ProductIndividualImage.DoesNotExist:
                    image_changed = True
            else:
                image_changed = True
            if image_changed:
                result = optimize_image_field(self.image, max_height=1000, quality=100)
                if result:
                    self.image = result
        super().save(*args, **kwargs)


# ─── FAQ ───

class FAQ(models.Model):
    question = models.CharField('Вопрос', max_length=500)
    answer = models.TextField('Ответ')
    is_active = models.BooleanField('Активен', default=True)
    order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQ'
        ordering = ['order']

    def __str__(self):
        return self.question


# ─── Настройки сайта ───

class SiteSettings(models.Model):
    """Singleton: глобальные настройки сайта (всегда pk=1)."""
    placeholder_image = models.ImageField(
        'Плейсхолдер товара', upload_to='site/', blank=True,
        help_text='Заглушка для товаров без фото. Если не задано — SVG по умолчанию.',
    )

    class Meta:
        verbose_name = 'Настройки сайта'
        verbose_name_plural = 'Настройки сайта'

    def __str__(self):
        return 'Настройки сайта'

    def save(self, *args, **kwargs):
        self.pk = 1
        if self.placeholder_image:
            if self._placeholder_image_changed():
                result = optimize_image_field(self.placeholder_image, max_width=800, quality=100)
                if result:
                    self.placeholder_image = result
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    def _placeholder_image_changed(self):
        try:
            old = SiteSettings.objects.get(pk=self.pk)
            return old.placeholder_image.name != self.placeholder_image.name
        except SiteSettings.DoesNotExist:
            return True

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
