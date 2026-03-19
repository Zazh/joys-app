from django.db import models


class EmailTemplate(models.Model):
    """Шаблон email-письма, редактируемый из админки."""
    slug = models.SlugField('Ключ', max_length=100, unique=True,
        help_text='email_verify, password_reset, welcome, order_created, order_paid, order_shipped',
    )
    subject = models.CharField('Тема письма', max_length=300,
        help_text='Можно использовать {плейсхолдеры}: {order_number}, {user_name} и т.д.',
    )
    body = models.TextField('Текст письма',
        help_text='Плейн-текст. Плейсхолдеры: {user_name}, {verify_url}, {order_number} и т.д.',
    )
    description = models.TextField('Описание (для админа)', blank=True,
        help_text='Какие плейсхолдеры доступны, когда отправляется',
    )

    class Meta:
        db_table = 'pages_emailtemplate'
        verbose_name = 'Шаблон письма'
        verbose_name_plural = 'Шаблоны писем'
        ordering = ['slug']

    def __str__(self):
        return f'{self.slug} — {self.subject}'

    def render(self, context: dict) -> tuple:
        """Рендерит subject и body, подставляя плейсхолдеры.

        Returns:
            (subject, body) — готовые строки.
        """
        safe = _SafeDict(context)
        return self.subject.format_map(safe), self.body.format_map(safe)


class _SafeDict(dict):
    """dict, который возвращает {key} для отсутствующих ключей."""
    def __missing__(self, key):
        return '{' + key + '}'


class EmailLog(models.Model):
    """Лог отправки email с retry-логикой."""

    class Status(models.TextChoices):
        SENT = 'sent', 'Отправлено'
        RETRY = 'retry', 'Ожидает повтора'
        FAILED = 'failed', 'Ошибка'

    to_email = models.EmailField('Получатель')
    template_slug = models.CharField('Шаблон', max_length=100)
    subject = models.CharField('Тема', max_length=300)
    body = models.TextField('Текст')
    status = models.CharField(
        'Статус', max_length=10,
        choices=Status.choices, default=Status.SENT,
    )
    attempts = models.PositiveSmallIntegerField('Попыток', default=0)
    next_retry_at = models.DateTimeField('Повторить после', null=True, blank=True)
    error = models.TextField('Ошибка', blank=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    sent_at = models.DateTimeField('Отправлен', null=True, blank=True)

    class Meta:
        db_table = 'orders_emaillog'
        verbose_name = 'Лог email'
        verbose_name_plural = 'Логи email'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'next_retry_at']),
        ]

    def __str__(self):
        return f'{self.template_slug} → {self.to_email} [{self.status}]'
