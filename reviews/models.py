from django.db import models
from django.db.models import Q, Value


MIN_CONTENT_LENGTH = 20  # минимум ~1 предложение


class ReviewQuerySet(models.QuerySet):
    def with_content(self):
        """Исключить пустые и слишком короткие отзывы (< 20 символов)."""
        from django.db.models.functions import Coalesce, Length
        return (
            self
            .annotate(
                _total_len=Coalesce(Length('text'), Value(0))
                + Coalesce(Length('pros'), Value(0))
                + Coalesce(Length('cons'), Value(0)),
            )
            .filter(_total_len__gte=MIN_CONTENT_LENGTH)
        )


class Review(models.Model):
    """Отзыв с Wildberries."""

    objects = ReviewQuerySet.as_manager()

    wb_id = models.CharField('WB ID', max_length=50, unique=True, db_index=True)
    nm_id = models.PositiveBigIntegerField(
        'nmId (артикул WB)', null=True, blank=True, db_index=True,
    )
    product_name = models.CharField('Название товара (WB)', max_length=500, blank=True)
    supplier_article = models.CharField('Артикул поставщика', max_length=100, blank=True)

    # Автор
    user_name = models.CharField('Имя автора', max_length=200, blank=True)

    # Содержание
    rating = models.PositiveSmallIntegerField('Оценка', help_text='1-5')
    text = models.TextField('Текст отзыва', blank=True)
    pros = models.TextField('Достоинства', blank=True)
    cons = models.TextField('Недостатки', blank=True)
    tags = models.JSONField('Теги (bables)', default=list, blank=True)

    # Фото
    photos = models.JSONField(
        'Фото', default=list, blank=True,
        help_text='Список URL: [{fullSize, miniSize}]',
    )

    # Ответ продавца
    answer_text = models.TextField('Ответ продавца', blank=True)

    # Управление
    is_pinned = models.BooleanField(
        'Закреплён вручную', default=False, db_index=True,
        help_text='Всегда показывается на сайте (не участвует в ротации)',
    )
    is_featured = models.BooleanField(
        'Показать на сайте', default=False, db_index=True,
        help_text='Закреплённые + авто-ротация. Управляется командой rotate_featured_reviews.',
    )
    is_excluded = models.BooleanField(
        'Исключён из выборки', default=False, db_index=True,
        help_text='Отзыв чужого магазина (OTAKU SHOP и т.д.). Учитывается в статистике, но не показывается на сайте.',
    )
    product = models.ForeignKey(
        'catalog.Product', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='wb_reviews', verbose_name='Товар на сайте',
        help_text='Привязка к товару в каталоге (опционально)',
    )

    # Даты
    wb_created_at = models.DateTimeField('Дата на WB')
    synced_at = models.DateTimeField('Синхронизировано', auto_now=True)

    class Meta:
        verbose_name = 'Отзыв WB'
        verbose_name_plural = 'Отзывы WB'
        ordering = ['-wb_created_at']
        indexes = [
            models.Index(fields=['is_featured', '-wb_created_at']),
            models.Index(fields=['rating']),
        ]

    def __str__(self):
        name = self.user_name or 'Аноним'
        return f'{name} — {"★" * self.rating} ({self.wb_created_at:%d.%m.%Y})'

    # Типы карточек для отображения
    CARD_LIST = 'list'              # только pros/cons/comment
    CARD_TEXT_LIST_TAGS = 'text_list_tags'  # text + pros/cons + tags
    CARD_TEXT_TAGS = 'text_tags'    # text + tags (без pros/cons)
    CARD_TEXT_LIST = 'text_list'    # text + pros/cons (без tags)
    CARD_TEXT = 'text'              # только text

    CARD_TYPE_CHOICES = [
        (CARD_LIST, 'Список (достоинства/недостатки)'),
        (CARD_TEXT_LIST_TAGS, 'Текст + список + теги'),
        (CARD_TEXT_TAGS, 'Текст + теги'),
        (CARD_TEXT_LIST, 'Текст + список'),
        (CARD_TEXT, 'Только текст'),
    ]

    @property
    def card_type(self):
        """Определяет лучший вариант карточки по контенту."""
        has_text = bool(self.text)
        has_list = bool(self.pros or self.cons)
        has_tags = bool(self.tags)

        if has_text and has_list and has_tags:
            return self.CARD_TEXT_LIST_TAGS
        if has_text and has_tags:
            return self.CARD_TEXT_TAGS
        if has_text and has_list:
            return self.CARD_TEXT_LIST
        if has_list:
            return self.CARD_LIST
        if has_text:
            return self.CARD_TEXT
        # Fallback: даже без контента — text (пустая карточка)
        return self.CARD_TEXT

    @property
    def content_length(self):
        """Суммарная длина контента для сортировки (самый длинный первый)."""
        return len(self.text) + len(self.pros) + len(self.cons)

    @property
    def has_list(self):
        return bool(self.pros or self.cons)

    @property
    def formatted_tags(self):
        """Теги как список строк (WB присылает разные форматы)."""
        if not self.tags:
            return []
        result = []
        for tag in self.tags:
            if isinstance(tag, str):
                result.append(tag)
            elif isinstance(tag, dict):
                result.append(tag.get('name', str(tag)))
        return result

    @property
    def full_text(self):
        """Полный текст: text + pros + cons."""
        parts = []
        if self.text:
            parts.append(self.text)
        if self.pros:
            parts.append(f'Достоинства: {self.pros}')
        if self.cons:
            parts.append(f'Недостатки: {self.cons}')
        return '\n'.join(parts)

    @property
    def first_photo_url(self):
        if self.photos:
            return self.photos[0].get('fullSize', '')
        return ''

    @property
    def formatted_date(self):
        """Дата в формате '24 нояб. 2025'."""
        if not self.wb_created_at:
            return ''
        months = {
            1: 'янв.', 2: 'февр.', 3: 'март', 4: 'апр.',
            5: 'мая', 6: 'июн.', 7: 'июл.', 8: 'авг.',
            9: 'сент.', 10: 'окт.', 11: 'нояб.', 12: 'дек.',
        }
        d = self.wb_created_at
        return f'{d.day} {months[d.month]} {d.year}'


class FeaturedReview(Review):
    """Proxy для раздела «Опубликованные отзывы на сайте»."""

    class Meta:
        proxy = True
        verbose_name = 'Опубликованный отзыв'
        verbose_name_plural = 'Опубликованные отзывы на сайте'
