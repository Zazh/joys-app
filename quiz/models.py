from django.db import models

from catalog.models import Product, ProductCharacteristic


# ─── Вопросы и варианты ───

class QuizQuestion(models.Model):
    """Вопрос квиза. Порядок определяет номер шага."""

    key = models.CharField(
        'Ключ', max_length=20, unique=True,
        help_text='q1, q2, q3, q4 — используется в правилах подбора',
    )
    text = models.TextField('Текст вопроса', help_text='HTML-перенос строк через <br>')
    order = models.PositiveIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активно', default=True)

    class Meta:
        verbose_name = 'Вопрос квиза'
        verbose_name_plural = 'Вопросы квиза'
        ordering = ['order']

    def __str__(self):
        return f'{self.key}: {self.text[:50]}'


class QuizOption(models.Model):
    """Вариант ответа на вопрос квиза."""

    question = models.ForeignKey(
        QuizQuestion, on_delete=models.CASCADE,
        related_name='options', verbose_name='Вопрос',
    )
    value = models.CharField(
        'Значение', max_length=50,
        help_text='texture, aroma, banana, yes, no — передаётся в правила',
    )
    label = models.CharField('Текст кнопки', max_length=200)
    bg_color = models.CharField(
        'Цвет фона', max_length=30, blank=True,
        help_text='CSS-цвет, например #E8C840',
    )
    text_color = models.CharField(
        'Цвет текста', max_length=30, blank=True,
        help_text='CSS-цвет, например #fff',
    )
    order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Вариант ответа'
        verbose_name_plural = 'Варианты ответа'
        ordering = ['order']

    def __str__(self):
        return f'{self.question.key}: {self.label} ({self.value})'


class QuizResultText(models.Model):
    """Настраиваемые тексты экрана результата квиза."""

    title = models.TextField(
        'Заголовок результата', default='Твой<br>идеальный<br>DR.JOYS',
        help_text='HTML-перенос строк через <br>',
    )
    button_text = models.CharField('Текст кнопки', max_length=100, default='Купить')
    more_text = models.CharField('Текст «ещё вариант»', max_length=100, default='Ещё вариант')

    class Meta:
        verbose_name = 'Тексты результата квиза'
        verbose_name_plural = 'Тексты результата квиза'

    def __str__(self):
        return 'Тексты результата'

    def save(self, *args, **kwargs):
        # Singleton: всегда pk=1
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class QuizRule(models.Model):
    """Правило подбора товара в квизе. Пустое поле = любой ответ."""

    Q1_CHOICES = [
        ('texture', 'Текстура'),
        ('aroma', 'Аромат'),
        ('feel', 'Неощутимость'),
    ]
    Q2_CHOICES = [
        ('banana', 'Банан'),
        ('strawberry', 'Клубника'),
        ('chocolate', 'Шоколад'),
        ('none', 'Без аромата'),
    ]
    Q3_CHOICES = [
        ('daily', 'Каждый день'),
        ('weekly', 'Несколько раз в неделю'),
        ('monthly', 'Несколько раз в месяц'),
        ('yearly', 'Редко'),
    ]
    Q4_CHOICES = [
        ('yes', 'Да'),
        ('no', 'Нет'),
    ]

    q1_important = models.CharField(
        'Q1: Что важнее?', max_length=20,
        choices=Q1_CHOICES, blank=True,
    )
    q2_aroma = models.CharField(
        'Q2: Аромат', max_length=20,
        choices=Q2_CHOICES, blank=True,
    )
    q3_frequency = models.CharField(
        'Q3: Частота', max_length=20,
        choices=Q3_CHOICES, blank=True,
    )
    q4_lube = models.CharField(
        'Q4: Доп. смазка?', max_length=10,
        choices=Q4_CHOICES, blank=True,
    )

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE,
        related_name='quiz_rules', verbose_name='Рекомендуемый товар',
    )
    priority = models.IntegerField(
        'Приоритет', default=0,
        help_text='Чем выше — тем приоритетнее. При совпадении нескольких правил побеждает с высшим.',
    )
    is_active = models.BooleanField('Активно', default=True)

    class Meta:
        verbose_name = 'Правило квиза'
        verbose_name_plural = 'Правила квиза'
        ordering = ['-priority']

    def __str__(self):
        parts = []
        if self.q1_important:
            parts.append(f'Q1={self.get_q1_important_display()}')
        if self.q2_aroma:
            parts.append(f'Q2={self.get_q2_aroma_display()}')
        if self.q3_frequency:
            parts.append(f'Q3={self.get_q3_frequency_display()}')
        if self.q4_lube:
            parts.append(f'Q4={self.get_q4_lube_display()}')
        conditions = ', '.join(parts) if parts else 'Любой ответ'
        return f'[{self.priority}] {conditions} → {self.product.name}'

    # Частота → категория размера пачки: 'large', 'medium', 'small'
    FREQUENCY_SIZE = {
        'daily': 'large',
        'weekly': 'medium',
        'monthly': 'small',
        'yearly': 'small',
    }

    # Ключевые характеристики для группировки товаров-«братьев»
    FAMILY_CHARACTERISTICS = ['Аромат', 'Текстура', 'Объём смазки']

    @classmethod
    def _find_pack_variant(cls, base_product, q3):
        """Подобрать пачку по частоте через характеристики."""
        size_category = cls.FREQUENCY_SIZE.get(q3)
        if not size_category:
            return base_product

        base_chars = dict(
            ProductCharacteristic.objects
            .filter(
                product=base_product,
                characteristic__name_ru__in=cls.FAMILY_CHARACTERISTICS,
            )
            .values_list('characteristic__name_ru', 'value_ru')
        )
        if not base_chars:
            return base_product

        candidates = Product.objects.filter(
            is_active=True,
            category=base_product.category,
            pack_quantity__isnull=False,
        )

        siblings = []
        for candidate in candidates:
            cand_chars = dict(
                ProductCharacteristic.objects
                .filter(
                    product=candidate,
                    characteristic__name_ru__in=cls.FAMILY_CHARACTERISTICS,
                )
                .values_list('characteristic__name_ru', 'value_ru')
            )
            if cand_chars == base_chars:
                siblings.append(candidate)

        if len(siblings) <= 1:
            return base_product

        siblings.sort(key=lambda p: p.pack_quantity)

        if size_category == 'small':
            return siblings[0]
        elif size_category == 'large':
            return siblings[-1]
        else:  # medium
            mid = len(siblings) // 2
            return siblings[mid]

    @classmethod
    def get_results(cls, q1, q2, q3, q4):
        """
        Двухшаговый подбор (возвращает список):
        1. Все правила на высшем совпавшем приоритете → типы товаров
        2. Q3 (частота) → подбор пачки для каждого
        """
        rules = cls.objects.filter(is_active=True).select_related('product').order_by('-priority')
        matched = []
        seen = set()
        best_priority = None

        for rule in rules:
            if rule.q1_important and rule.q1_important != q1:
                continue
            if rule.q2_aroma and rule.q2_aroma != q2:
                continue
            if rule.q3_frequency and rule.q3_frequency != q3:
                continue
            if rule.q4_lube and rule.q4_lube != q4:
                continue

            if best_priority is None:
                best_priority = rule.priority
            elif rule.priority < best_priority:
                break

            product = cls._find_pack_variant(rule.product, q3)
            if product.pk not in seen:
                matched.append(product)
                seen.add(product.pk)

        return matched


class QuizSubmission(models.Model):
    """Сохранённые ответы квиза для аналитики."""

    q1 = models.CharField('Q1', max_length=50, blank=True)
    q2 = models.CharField('Q2', max_length=50, blank=True)
    q3 = models.CharField('Q3', max_length=50, blank=True)
    q4 = models.CharField('Q4', max_length=50, blank=True)
    result_product = models.ForeignKey(
        Product, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='quiz_submissions',
        verbose_name='Рекомендованный товар',
    )
    ip_address = models.GenericIPAddressField('IP', null=True, blank=True)
    session_key = models.CharField('Сессия', max_length=40, blank=True)
    created_at = models.DateTimeField('Дата', auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Прохождение квиза'
        verbose_name_plural = 'Прохождения квиза'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.created_at:%d.%m.%Y %H:%M} — {self.q1}/{self.q2}/{self.q3}/{self.q4}'


class QuizBackground(models.Model):
    """Фон для результата квиза."""

    key = models.SlugField(
        'Ключ', max_length=50, unique=True,
        help_text='banana, strawberry, chocolate, dotted-ribbed, triple-lube',
    )
    image = models.ImageField('Изображение', upload_to='quiz/backgrounds/')
    is_dark_theme = models.BooleanField(
        'Тёмная тема', default=False,
        help_text='Белый текст на тёмном фоне',
    )
    is_active = models.BooleanField('Активно', default=True)

    class Meta:
        verbose_name = 'Фон квиза'
        verbose_name_plural = 'Фоны квиза'

    def __str__(self):
        return self.key
