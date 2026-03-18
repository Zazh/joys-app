from django.contrib import admin
from modeltranslation.admin import TabbedTranslationAdmin, TranslationStackedInline

from .models import InteractiveModal, ModalStep


class ModalStepInline(TranslationStackedInline):
    model = ModalStep
    extra = 1
    ordering = ('order',)
    fieldsets = (
        (None, {'fields': ('order', 'step_type')}),
        ('Контент', {'fields': ('image', 'text', 'button_text', 'badge_text'), 'classes': ('collapse',)}),
        ('Форма', {'fields': ('inquiry_form',), 'classes': ('collapse',)}),
        ('CTA', {'fields': ('cta_text', 'cta_url'), 'classes': ('collapse',)}),
    )


@admin.register(InteractiveModal)
class InteractiveModalAdmin(TabbedTranslationAdmin):
    list_display = ('title', 'slug', 'theme', 'is_active', 'step_count')
    list_filter = ('is_active', 'theme')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ModalStepInline]

    @admin.display(description='Шагов')
    def step_count(self, obj):
        return obj.steps.count()
