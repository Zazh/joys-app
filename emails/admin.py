from django.contrib import admin
from modeltranslation.admin import TabbedTranslationAdmin

from .models import EmailTemplate, EmailLog


@admin.register(EmailTemplate)
class EmailTemplateAdmin(TabbedTranslationAdmin):
    list_display = ('slug', 'subject', 'description')
    search_fields = ('slug', 'subject')
    readonly_fields = ('slug',)
    fieldsets = (
        (None, {
            'fields': ('slug', 'subject', 'body'),
        }),
        ('Справка', {
            'classes': ('collapse',),
            'fields': ('description',),
        }),
    )


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ('template_slug', 'to_email', 'status', 'attempts', 'created_at', 'sent_at')
    list_filter = ('status', 'template_slug')
    search_fields = ('to_email', 'subject')
    readonly_fields = (
        'to_email', 'template_slug', 'subject', 'body',
        'status', 'attempts', 'next_retry_at', 'error',
        'created_at', 'sent_at',
    )
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return True
