from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import QRCode
from .utils import generate_preview, transliterate


@admin.register(QRCode)
class QRCodeAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'content_short', 'qr_preview', 'download_link', 'created_at')
    search_fields = ('title', 'content')
    readonly_fields = ('qr_preview_large', 'download_button', 'created_at')
    fieldsets = (
        (None, {
            'fields': ('title', 'content'),
        }),
        ('QR-код', {
            'fields': ('qr_preview_large', 'download_button'),
        }),
    )

    def content_short(self, obj):
        return obj.content[:80] + '…' if len(obj.content) > 80 else obj.content
    content_short.short_description = 'Содержимое'

    def qr_preview(self, obj):
        if obj.preview:
            return format_html('<img src="{}" width="60" height="60">', obj.preview.url)
        return '—'
    qr_preview.short_description = 'QR'

    def qr_preview_large(self, obj):
        if obj.preview:
            return format_html(
                '<img src="{}" width="200" height="200" style="image-rendering:pixelated;">',
                obj.preview.url,
            )
        return 'QR сгенерируется при сохранении'
    qr_preview_large.short_description = 'Превью'

    def download_link(self, obj):
        if not obj.pk:
            return '—'
        url = reverse('qrcodes:download_zip', args=[obj.pk])
        return format_html('<a href="{}">ZIP</a>', url)
    download_link.short_description = 'Скачать'

    def download_button(self, obj):
        if not obj.pk:
            return 'Сохраните запись, чтобы скачать QR-коды'
        url = reverse('qrcodes:download_zip', args=[obj.pk])
        return format_html(
            '<a href="{}" class="button" style="padding:6px 16px;">Скачать ZIP</a>'
            '<p class="help">PNG (256, 512, 1024px) × белый/прозрачный + SVG белый/прозрачный</p>',
            url,
        )
    download_button.short_description = 'Архив'

    def save_model(self, request, obj, form, change):
        if not change or 'content' in form.changed_data:
            preview_file = generate_preview(obj.content)
            slug = transliterate(obj.title or 'qr')
            obj.preview.save(f'{slug}-preview.png', preview_file, save=False)
        super().save_model(request, obj, form, change)
