from django.contrib import admin
from django.shortcuts import redirect
from django.utils.html import format_html
from modeltranslation.admin import TabbedTranslationAdmin, TranslationTabularInline

from regions.models import Region
from .models import (
    Category, Product, ProductSize, RegionPrice, Stock,
    UnitOfMeasure, Characteristic, ProductCharacteristic,
    ProductMainImage, ProductPackageImage, ProductIndividualImage,
    FAQ, SiteSettings,
)


# ─── Категория ───

@admin.register(Category)
class CategoryAdmin(TabbedTranslationAdmin):
    list_display = ('name', 'slug', 'is_active', 'order')
    list_editable = ('is_active', 'order')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'description', 'image', 'is_active', 'order'),
        }),
        ('SEO', {
            'classes': ('collapse',),
            'fields': ('meta_title', 'meta_description'),
        }),
    )


# ─── Характеристики ───

@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(TabbedTranslationAdmin):
    list_display = ('name', 'abbr', 'data_type')


@admin.register(Characteristic)
class CharacteristicAdmin(TabbedTranslationAdmin):
    list_display = ('name', 'unit', 'order')
    list_editable = ('order',)
    search_fields = ('name',)


# ─── Товар ───

class SizeInline(admin.TabularInline):
    model = ProductSize
    extra = 1
    fields = ('name', 'sku', 'price', 'old_price', 'order')


class CharacteristicInline(TranslationTabularInline):
    model = ProductCharacteristic
    extra = 1
    fields = ('characteristic', 'value', 'subtitle')
    autocomplete_fields = ['characteristic']


class MainImageInline(TranslationTabularInline):
    model = ProductMainImage
    extra = 1
    fields = ('image', 'image_kk', 'alt_text', 'is_cover', 'order')


class PackageImageInline(TranslationTabularInline):
    model = ProductPackageImage
    extra = 1
    fields = ('image', 'alt_text', 'order')


class IndividualImageInline(TranslationTabularInline):
    model = ProductIndividualImage
    extra = 1
    fields = ('image', 'alt_text', 'order')


@admin.register(Product)
class ProductAdmin(TabbedTranslationAdmin):
    list_display = ('name', 'category', 'badge', 'is_active', 'regional_prices_link')
    list_filter = ('category', 'badge', 'is_active')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ['category']
    inlines = [SizeInline, CharacteristicInline, MainImageInline, PackageImageInline, IndividualImageInline]
    fieldsets = (
        (None, {
            'fields': ('name', 'tagline', 'slug', 'category'),
        }),
        ('Описание', {
            'fields': ('description',),
        }),
        ('Настройки', {
            'fields': ('badge', 'is_active'),
        }),
        ('SEO', {
            'classes': ('collapse',),
            'fields': ('meta_title', 'meta_description'),
        }),
        ('Изображения', {
            'fields': ('transparent_image', 'transparent_image_kk', 'zoom_image', 'zoom_rotation_angle'),
        }),
    )

    def regional_prices_link(self, obj):
        url = f'/admin/catalog/regionprice/?q={obj.name}'
        return format_html('<a href="{}">Цены</a>', url)
    regional_prices_link.short_description = 'Рег. цены'

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # Авто-создание RegionPrice + Stock для всех размеров × активных регионов
        product = form.instance
        active_regions = Region.objects.filter(is_active=True)
        for size in product.sizes.all():
            for region in active_regions:
                RegionPrice.objects.get_or_create(
                    size=size,
                    region=region,
                    defaults={'price': 0},
                )
                Stock.objects.get_or_create(
                    size=size,
                    region=region,
                )


# ─── Региональные цены ───

@admin.register(RegionPrice)
class RegionPriceAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'size', 'region', 'price', 'old_price')
    list_filter = ('region', 'size__product__category')
    search_fields = ('size__product__name', 'size__sku')
    list_editable = ('price', 'old_price')
    list_select_related = ('size__product', 'region')
    list_per_page = 50

    @admin.display(description='Товар', ordering='size__product__name')
    def product_name(self, obj):
        return obj.size.product.name


# ─── Остатки ───

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'size', 'region', 'quantity', 'reserved', 'available_display', 'updated_at')
    list_filter = ('region', 'size__product__category')
    search_fields = ('size__product__name', 'size__sku')
    list_editable = ('quantity', 'reserved')
    list_select_related = ('size__product', 'region')
    list_per_page = 50

    @admin.display(description='Товар', ordering='size__product__name')
    def product_name(self, obj):
        return obj.size.product.name

    @admin.display(description='Доступно')
    def available_display(self, obj):
        return obj.available


# ─── FAQ ───

@admin.register(FAQ)
class FAQAdmin(TabbedTranslationAdmin):
    list_display = ('question', 'is_active', 'order')
    list_editable = ('is_active', 'order')


# ─── Настройки сайта ───

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Изображения', {
            'fields': ('placeholder_image',),
            'description': 'Плейсхолдер — изображение-заглушка для товаров без фото.',
        }),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = SiteSettings.load()
        return redirect(f'{request.path}{obj.pk}/change/')
