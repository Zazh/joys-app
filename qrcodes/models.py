from django.db import models


class QRCode(models.Model):
    """Сохранённый QR-код."""
    title = models.CharField('Название', max_length=300, blank=True)
    content = models.TextField(
        'Содержимое',
        help_text='Текст, URL или любая строка для кодирования в QR',
    )
    preview = models.ImageField('Превью', upload_to='qrcodes/previews/', blank=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'QR-код'
        verbose_name_plural = 'QR-коды'
        ordering = ['-created_at']

    def __str__(self):
        return self.title or self.content[:50]
