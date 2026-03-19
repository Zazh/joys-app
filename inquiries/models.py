from django.db import models


class InquiryForm(models.Model):
    """Универсальная форма: партнёры, тату, маркетинг и т.д."""

    slug = models.SlugField('Slug', max_length=100, unique=True)
    title = models.CharField('Название', max_length=200)
    description = models.TextField('Описание', blank=True, help_text='Отображается над формой')
    success_title = models.CharField('Заголовок успеха', max_length=200, default='Спасибо!')
    success_text = models.TextField('Текст успеха', default='Мы свяжемся с вами в ближайшее время.')
    submit_text = models.CharField('Текст кнопки', max_length=100, default='Отправить')
    email_notify_to = models.EmailField(
        'Email для уведомлений', blank=True,
        help_text='Куда слать уведомление о новой заявке',
    )
    is_active = models.BooleanField('Активна', default=True)
    created_at = models.DateTimeField('Создана', auto_now_add=True)

    class Meta:
        verbose_name = 'Форма'
        verbose_name_plural = 'Формы'
        ordering = ['title']

    def __str__(self):
        return self.title


class InquiryField(models.Model):
    """Поле формы — тип, лейбл, валидация."""

    FIELD_TYPES = [
        ('text', 'Текст'),
        ('textarea', 'Многострочный текст'),
        ('email', 'Email'),
        ('phone', 'Телефон'),
        ('number', 'Число'),
        ('select', 'Выпадающий список'),
        ('radio', 'Радио-кнопки'),
        ('checkbox', 'Чекбокс'),
    ]

    form = models.ForeignKey(
        InquiryForm, on_delete=models.CASCADE,
        related_name='fields', verbose_name='Форма',
    )
    key = models.SlugField(
        'Ключ поля', max_length=50,
        help_text='Имя поля в JSON (name, email, phone и т.д.)',
    )
    label = models.CharField('Лейбл', max_length=200)
    field_type = models.CharField('Тип', max_length=20, choices=FIELD_TYPES, default='text')
    placeholder = models.CharField('Placeholder', max_length=200, blank=True)
    choices_text = models.TextField(
        'Варианты', blank=True,
        help_text='Для select/radio: по одному на строку в формате value|Текст',
    )
    is_required = models.BooleanField('Обязательное', default=True)
    min_value = models.IntegerField('Мин. значение', null=True, blank=True, help_text='Для number')
    max_value = models.IntegerField('Макс. значение', null=True, blank=True, help_text='Для number')
    order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Поле формы'
        verbose_name_plural = 'Поля формы'
        ordering = ['order']
        unique_together = [('form', 'key')]

    def __str__(self):
        return f'{self.form.slug}.{self.key} ({self.get_field_type_display()})'

    def get_choices(self):
        """Парсит choices_text → список (value, label)."""
        if not self.choices_text:
            return []
        result = []
        for line in self.choices_text.strip().splitlines():
            line = line.strip()
            if '|' in line:
                val, label = line.split('|', 1)
                result.append({'value': val.strip(), 'label': label.strip()})
            elif line:
                result.append({'value': line, 'label': line})
        return result


class InquirySubmission(models.Model):
    """Отправленная заявка."""

    form = models.ForeignKey(
        InquiryForm, on_delete=models.CASCADE,
        related_name='submissions', verbose_name='Форма',
    )
    ip_address = models.GenericIPAddressField('IP', blank=True, null=True)
    created_at = models.DateTimeField('Дата', auto_now_add=True)
    is_processed = models.BooleanField('Обработано', default=False)

    class Meta:
        verbose_name = 'Заявка'
        verbose_name_plural = 'Заявки'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.form.title} — {self.created_at:%d.%m.%Y %H:%M}'

    def get_data_dict(self):
        """Данные заявки как dict {key: value}."""
        return {fv.field.key: fv.value for fv in self.values.select_related('field')}


class InquiryStatusLog(models.Model):
    """История изменений статуса обработки заявки."""
    submission = models.ForeignKey(
        InquirySubmission, on_delete=models.CASCADE,
        related_name='status_logs', verbose_name='Заявка',
    )
    action = models.CharField('Действие', max_length=20, choices=[
        ('processed', 'Обработана'),
        ('unprocessed', 'Снята обработка'),
    ])
    changed_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Кто изменил',
    )
    changed_at = models.DateTimeField('Дата', auto_now_add=True)

    class Meta:
        verbose_name = 'История статуса заявки'
        verbose_name_plural = 'История статусов заявок'
        ordering = ['-changed_at']

    def __str__(self):
        return f'Заявка #{self.submission_id}: {self.get_action_display()}'


class InquiryFieldValue(models.Model):
    """Значение поля в заявке — нормализованное хранение."""

    submission = models.ForeignKey(
        InquirySubmission, on_delete=models.CASCADE,
        related_name='values', verbose_name='Заявка',
    )
    field = models.ForeignKey(
        InquiryField, on_delete=models.CASCADE,
        related_name='values', verbose_name='Поле',
    )
    value = models.TextField('Значение', blank=True)

    class Meta:
        verbose_name = 'Значение поля'
        verbose_name_plural = 'Значения полей'
        unique_together = [('submission', 'field')]

    def __str__(self):
        return f'{self.field.label}: {self.value[:50]}' if self.value else self.field.label

    @property
    def display_value(self):
        """Значение для отображения — для radio/select показывает label."""
        if self.field.field_type in ('radio', 'select') and self.field.choices_text:
            choices = {c['value']: c['label'] for c in self.field.get_choices()}
            return choices.get(self.value, self.value)
        return self.value
