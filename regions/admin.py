from django.contrib import admin
from modeltranslation.admin import TabbedTranslationAdmin

from catalog.models import ProductSize, RegionPrice, Stock

from .models import Region, ExchangeRate


@admin.register(Region)
class RegionAdmin(TabbedTranslationAdmin):
    list_display = (
        'code', 'name', 'flag_emoji', 'currency_code',
        'currency_symbol', 'payment_currency_code',
        'default_language', 'is_active', 'is_default', 'order',
    )
    list_editable = ('is_active', 'is_default', 'order')
    search_fields = ('code', 'name')
    list_filter = ('is_active',)
    fieldsets = (
        (None, {'fields': (
            'code', 'name', 'flag_emoji', 'order',
            'is_active', 'is_default',
        )}),
        ('Валюта', {'fields': (
            'currency_code', 'currency_symbol',
            'payment_currency_code', 'payment_currency_symbol',
        )}),
        ('Прочее', {'fields': (
            'default_language', 'phone_code', 'payment_gateway',
        )}),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Зеркало ProductAdmin.save_related: там цены и остатки заводятся при
        # сохранении товара, здесь — при сохранении региона. Без этого новый
        # регион приходил в каталог без RegionPrice, витрина откатывалась к
        # базовой (тенговой) цене размера и печатала её под чужим символом.
        # Инлайнов у RegionAdmin нет, поэтому место хука — save_model: его
        # зовёт и обычная форма, и галка «Активен» в списке.
        if not obj.is_active:
            return
        for size in ProductSize.objects.all():
            RegionPrice.objects.get_or_create(
                size=size,
                region=obj,
                defaults={'price': 0},
            )
            Stock.objects.get_or_create(
                size=size,
                region=obj,
            )


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ('currency_code', 'rate', 'quant', 'fetched_at')
    readonly_fields = ('fetched_at',)
