from django.contrib import admin

from .models import Redirect


@admin.register(Redirect)
class RedirectAdmin(admin.ModelAdmin):
    list_display = ('path', 'destination', 'redirect_type', 'is_active', 'created_at')
    list_filter = ('redirect_type', 'is_active')
    list_editable = ('is_active',)
    search_fields = ('path', 'destination', 'note')
    fieldsets = (
        (None, {
            'fields': ('path', 'destination', 'redirect_type'),
        }),
        ('Настройки', {
            'fields': ('is_active', 'note'),
        }),
    )
