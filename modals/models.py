from django.db import models


class InteractiveModal(models.Model):
    """Интерактивная модалка с шагами. Тату, промо-акции и т.д."""

    THEME_CHOICES = [
        ('light', 'Светлая'),
        ('dark', 'Тёмная'),
    ]

    slug = models.SlugField('Slug', max_length=100, unique=True)
    title = models.CharField('Название', max_length=200, help_text='Для админки, не отображается')
    theme = models.CharField('Тема', max_length=10, choices=THEME_CHOICES, default='dark')
    trigger_text = models.CharField(
        'Текст кнопки-триггера', max_length=200, blank=True,
        help_text='Текст кнопки, открывающей модалку (например «Прочитать условие»)',
    )
    is_active = models.BooleanField('Активна', default=True)
    created_at = models.DateTimeField('Создана', auto_now_add=True)

    class Meta:
        verbose_name = 'Интерактивная модалка'
        verbose_name_plural = 'Интерактивные модалки'
        ordering = ['title']

    def __str__(self):
        return self.title


class ModalStep(models.Model):
    """Шаг интерактивной модалки."""

    STEP_TYPES = [
        ('content', 'Контент (картинка + текст + «Далее»)'),
        ('form', 'Форма из inquiries'),
        ('cta', 'CTA-кнопка (ссылка)'),
    ]

    modal = models.ForeignKey(
        InteractiveModal, on_delete=models.CASCADE,
        related_name='steps', verbose_name='Модалка',
    )
    order = models.PositiveIntegerField('Порядок', default=0)
    step_type = models.CharField('Тип шага', max_length=10, choices=STEP_TYPES, default='content')

    # Content step
    image = models.ImageField('Картинка', upload_to='modals/', blank=True)
    text = models.TextField('Текст', blank=True)
    button_text = models.CharField('Текст кнопки «Далее»', max_length=100, default='Далее')

    # Badge (например 21+ для тату)
    badge_text = models.CharField('Бейдж', max_length=20, blank=True, help_text='Например «21+»')

    # Form step
    inquiry_form = models.ForeignKey(
        'inquiries.InquiryForm', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='Форма (inquiries)',
        help_text='Для типа «Форма» — какую форму из inquiries встроить',
    )

    # CTA step
    cta_text = models.CharField('Текст CTA-кнопки', max_length=200, blank=True)
    cta_url = models.URLField('Ссылка CTA', blank=True)

    class Meta:
        verbose_name = 'Шаг модалки'
        verbose_name_plural = 'Шаги модалки'
        ordering = ['order']

    def __str__(self):
        return f'{self.modal.slug} — шаг {self.order} ({self.get_step_type_display()})'
