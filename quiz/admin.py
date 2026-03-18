from django.contrib import admin
from modeltranslation.admin import TabbedTranslationAdmin

from .models import QuizQuestion, QuizOption, QuizResultText, QuizRule, QuizBackground


class QuizOptionInline(admin.TabularInline):
    model = QuizOption
    extra = 1
    fields = ('order', 'value', 'label_ru', 'label_kk', 'label_en', 'bg_color', 'text_color')
    ordering = ('order',)


@admin.register(QuizQuestion)
class QuizQuestionAdmin(TabbedTranslationAdmin):
    list_display = ('key', 'text_ru', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    ordering = ('order',)
    inlines = [QuizOptionInline]


@admin.register(QuizResultText)
class QuizResultTextAdmin(TabbedTranslationAdmin):
    list_display = ('__str__',)

    def has_add_permission(self, request):
        return not QuizResultText.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(QuizRule)
class QuizRuleAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'priority', 'q1_important', 'q2_aroma', 'q3_frequency', 'q4_lube', 'product', 'is_active')
    list_display_links = ('__str__',)
    list_editable = ('priority', 'is_active')
    list_filter = ('q1_important', 'q2_aroma', 'is_active')
    autocomplete_fields = ('product',)
    ordering = ('-priority',)


@admin.register(QuizBackground)
class QuizBackgroundAdmin(admin.ModelAdmin):
    list_display = ('key', 'is_dark_theme', 'is_active')
    list_editable = ('is_dark_theme', 'is_active')
