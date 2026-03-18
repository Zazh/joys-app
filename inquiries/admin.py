from django.contrib import admin
from django.utils.html import format_html
from modeltranslation.admin import TabbedTranslationAdmin, TranslationTabularInline

from .models import InquiryForm, InquiryField, InquirySubmission, InquiryFieldValue


class InquiryFieldInline(TranslationTabularInline):
    model = InquiryField
    extra = 1
    ordering = ('order',)
    fields = ('order', 'key', 'field_type', 'label', 'placeholder', 'choices_text', 'is_required', 'min_value', 'max_value')


@admin.register(InquiryForm)
class InquiryFormAdmin(TabbedTranslationAdmin):
    list_display = ('title', 'slug', 'is_active', 'submissions_count', 'created_at')
    list_filter = ('is_active',)
    prepopulated_fields = {'slug': ('title_ru',)}
    inlines = [InquiryFieldInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        from django.db.models import Count
        return qs.annotate(_submissions_count=Count('submissions'))

    @admin.display(description='Заявок', ordering='_submissions_count')
    def submissions_count(self, obj):
        return obj._submissions_count


class InquiryFieldValueInline(admin.TabularInline):
    model = InquiryFieldValue
    extra = 0
    readonly_fields = ('field', 'display_value_html')
    fields = ('field', 'display_value_html')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description='Значение')
    def display_value_html(self, obj):
        return obj.display_value


@admin.register(InquirySubmission)
class InquirySubmissionAdmin(admin.ModelAdmin):
    list_display = ('form', 'summary', 'ip_address', 'is_processed', 'created_at')
    list_filter = ('form', 'is_processed', 'created_at')
    list_editable = ('is_processed',)
    readonly_fields = ('form', 'ip_address', 'created_at')
    inlines = [InquiryFieldValueInline]
    list_per_page = 50

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('values__field')

    @admin.display(description='Данные')
    def summary(self, obj):
        parts = []
        for fv in obj.values.all()[:3]:
            parts.append(f'{fv.field.label}: {fv.display_value[:30]}')
        text = ' | '.join(parts)
        if obj.values.count() > 3:
            text += ' ...'
        return text or '—'
