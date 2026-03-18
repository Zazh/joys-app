from django.contrib import admin
from django.utils.html import format_html

from .models import FeaturedReview, Review


class ReviewAdminMixin:
    """Общие методы для обоих admin-классов."""

    @admin.display(description='Оценка', ordering='rating')
    def rating_stars(self, obj):
        return '★' * obj.rating + '☆' * (5 - obj.rating)

    @admin.display(description='Текст')
    def short_text(self, obj):
        text = obj.text or obj.pros or obj.cons or '—'
        return text[:80] + '...' if len(text) > 80 else text

    @admin.display(description='Товар')
    def product_name_short(self, obj):
        if obj.product_name:
            return obj.product_name[:40] + '...' if len(obj.product_name) > 40 else obj.product_name
        return '—'

    @admin.display(description='Фото')
    def photos_preview(self, obj):
        if not obj.photos:
            return '—'
        html = ''
        for photo in obj.photos[:5]:
            url = photo.get('miniSize') or photo.get('fullSize', '')
            if url:
                html += f'<img src="{url}" style="max-height:100px;margin:4px;border-radius:4px;">'
        return format_html(html) if html else '—'


@admin.register(Review)
class ReviewAdmin(ReviewAdminMixin, admin.ModelAdmin):
    list_display = (
        'user_name', 'rating_stars', 'short_text', 'product_name_short',
        'is_pinned', 'is_featured', 'wb_created_at',
    )
    list_filter = ('is_pinned', 'is_featured', 'rating', 'wb_created_at')
    list_editable = ('is_pinned',)
    search_fields = ('user_name', 'text', 'pros', 'cons', 'product_name')
    readonly_fields = (
        'wb_id', 'nm_id', 'product_name', 'supplier_article',
        'user_name', 'rating', 'text', 'pros', 'cons', 'tags',
        'photos_preview', 'answer_text', 'wb_created_at', 'synced_at',
    )
    fieldsets = (
        ('Отзыв', {
            'fields': (
                'user_name', 'rating', 'text', 'pros', 'cons', 'tags',
                'photos_preview', 'answer_text',
            ),
        }),
        ('Товар WB', {
            'fields': ('wb_id', 'nm_id', 'product_name', 'supplier_article'),
        }),
        ('Управление', {
            'description': (
                '«Закреплён вручную» — всегда на сайте, не участвует в ротации. '
                '«Показать на сайте» — управляется командой rotate_featured_reviews.'
            ),
            'fields': ('is_pinned', 'is_featured', 'product'),
        }),
        ('Даты', {
            'fields': ('wb_created_at', 'synced_at'),
        }),
    )
    list_per_page = 50
    actions = ['pin_reviews', 'unpin_reviews']

    @admin.action(description='Закрепить на сайте (вручную)')
    def pin_reviews(self, request, queryset):
        updated = queryset.update(is_pinned=True, is_featured=True)
        self.message_user(request, f'{updated} отзывов закреплено.')

    @admin.action(description='Открепить с сайта')
    def unpin_reviews(self, request, queryset):
        updated = queryset.update(is_pinned=False, is_featured=False)
        self.message_user(request, f'{updated} отзывов откреплено.')


@admin.register(FeaturedReview)
class FeaturedReviewAdmin(ReviewAdminMixin, admin.ModelAdmin):
    """Только опубликованные отзывы — отдельный раздел в админке."""

    list_display = (
        'user_name', 'rating_stars', 'card_type_display',
        'is_pinned', 'short_text', 'product_name_short', 'wb_created_at',
    )
    list_filter = ('is_pinned', 'rating', 'wb_created_at')
    search_fields = ('user_name', 'text', 'pros', 'cons', 'product_name')
    readonly_fields = (
        'wb_id', 'nm_id', 'product_name', 'supplier_article',
        'user_name', 'rating', 'text', 'pros', 'cons', 'tags',
        'photos_preview', 'answer_text', 'wb_created_at', 'synced_at',
        'card_type_display',
    )
    fieldsets = (
        ('Отзыв', {
            'fields': (
                'user_name', 'rating', 'card_type_display',
                'text', 'pros', 'cons', 'tags',
                'photos_preview', 'answer_text',
            ),
        }),
        ('Товар WB', {
            'fields': ('wb_id', 'nm_id', 'product_name', 'supplier_article'),
        }),
        ('Управление', {
            'fields': ('is_pinned', 'is_featured', 'product'),
        }),
        ('Даты', {
            'fields': ('wb_created_at', 'synced_at'),
        }),
    )
    list_per_page = 30
    actions = ['unpin_and_remove']

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_featured=True)

    @admin.display(description='Тип карточки')
    def card_type_display(self, obj):
        labels = dict(Review.CARD_TYPE_CHOICES)
        return labels.get(obj.card_type, obj.card_type)

    @admin.action(description='Убрать с сайта и открепить')
    def unpin_and_remove(self, request, queryset):
        updated = queryset.update(is_pinned=False, is_featured=False)
        self.message_user(request, f'{updated} отзывов убрано с сайта.')
