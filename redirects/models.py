from django.db import models


class Redirect(models.Model):
    """Редирект: путь на текущем сайте → внешний URL (легаси и т.д.)."""

    class RedirectType(models.IntegerChoices):
        PERMANENT = 301, '301 — Постоянный'
        TEMPORARY = 302, '302 — Временный'

    path = models.CharField(
        'Путь на сайте', max_length=500, unique=True, db_index=True,
        help_text='Путь без домена, например: /100-sex-positions/',
    )
    destination = models.CharField(
        'Куда перенаправлять', max_length=500,
        help_text='Полный URL, например: https://old-site.com/100-sex-positions#popup:myform',
    )
    redirect_type = models.IntegerField(
        'Тип редиректа',
        choices=RedirectType.choices, default=RedirectType.TEMPORARY,
    )
    is_active = models.BooleanField('Активен', default=True)
    note = models.CharField('Заметка', max_length=300, blank=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Редирект'
        verbose_name_plural = 'Редиректы'
        ordering = ['path']
        indexes = [
            models.Index(fields=['is_active', 'path']),
        ]

    def __str__(self):
        return f'{self.path} → {self.destination} ({self.redirect_type})'
