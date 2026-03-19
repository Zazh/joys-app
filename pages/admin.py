from django.contrib import admin
from modeltranslation.admin import TabbedTranslationAdmin, TranslationStackedInline

from .models import PageCategory, Page, BlogCategory, BlogPost, MenuItem, HeroSection, HeroCard, FeatureSlide, PromoBlock, PromoImage, EmailTemplate, ServicePage


@admin.register(PageCategory)
class PageCategoryAdmin(TabbedTranslationAdmin):
    list_display = ('name', 'slug', 'order')
    list_editable = ('order',)
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Page)
class PageAdmin(TabbedTranslationAdmin):
    list_display = ('title', 'slug', 'category', 'is_published', 'order', 'updated_at')
    list_filter = ('is_published', 'category')
    list_editable = ('order',)
    search_fields = ('title', 'slug')
    prepopulated_fields = {'slug': ('title',)}
    autocomplete_fields = ['category']
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'category', 'body'),
        }),
        ('SEO', {
            'classes': ('collapse',),
            'fields': ('meta_title', 'meta_description', 'og_image'),
        }),
        ('Настройки', {
            'fields': ('is_published', 'order'),
        }),
    )


@admin.register(BlogCategory)
class BlogCategoryAdmin(TabbedTranslationAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(BlogPost)
class BlogPostAdmin(TabbedTranslationAdmin):
    list_display = ('title', 'category', 'author', 'is_published', 'published_at')
    list_filter = ('is_published', 'category')
    search_fields = ('title', 'slug')
    prepopulated_fields = {'slug': ('title',)}
    autocomplete_fields = ['category']
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'excerpt', 'body'),
        }),
        ('Медиа и автор', {
            'fields': ('cover_image', 'author', 'category', 'published_at'),
        }),
        ('SEO', {
            'classes': ('collapse',),
            'fields': ('meta_title', 'meta_description'),
        }),
        ('Настройки', {
            'fields': ('is_published',),
        }),
    )


@admin.register(MenuItem)
class MenuItemAdmin(TabbedTranslationAdmin):
    list_display = ('title', 'link_type', 'order', 'is_active')
    list_filter = ('link_type', 'is_active')
    list_editable = ('order', 'is_active')
    autocomplete_fields = ['page', 'page_category']
    fieldsets = (
        (None, {
            'fields': ('title', 'order', 'is_active'),
        }),
        ('Ссылка', {
            'fields': ('link_type', 'named_url', 'page', 'page_category', 'external_url', 'open_in_new_tab'),
        }),
    )


class HeroCardInline(admin.StackedInline):
    model = HeroCard
    extra = 0
    fields = ('order', 'image', 'count_image')
    ordering = ('order',)


@admin.register(HeroSection)
class HeroSectionAdmin(TabbedTranslationAdmin):
    list_display = ('__str__', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    fieldsets = (
        (None, {
            'fields': ('title', 'subtitle'),
        }),
        ('Кнопки', {
            'fields': ('button_catalog_text', 'button_buy_text', 'button_buy_url'),
        }),
        ('Настройки', {
            'fields': ('is_active',),
        }),
    )
    inlines = [HeroCardInline]


@admin.register(FeatureSlide)
class FeatureSlideAdmin(TabbedTranslationAdmin):
    list_display = ('title', 'media_type', 'order', 'is_active')
    list_filter = ('media_type', 'is_active')
    list_editable = ('order', 'is_active')
    fieldsets = (
        (None, {
            'fields': ('title', 'text', 'order', 'is_active'),
        }),
        ('Медиа', {
            'fields': ('media_type', 'image', 'video', 'video_poster'),
        }),
    )


class PromoImageInline(admin.StackedInline):
    model = PromoImage
    extra = 0
    max_num = 8
    fields = ('order', 'image')
    ordering = ('order',)


@admin.register(PromoBlock)
class PromoBlockAdmin(TabbedTranslationAdmin):
    list_display = ('slug', 'title', 'is_active')
    list_filter = ('is_active',)
    prepopulated_fields = {'slug': ('title',)}
    fieldsets = (
        (None, {
            'fields': ('slug', 'title', 'subtitle', 'text'),
        }),
        ('Кнопка', {
            'fields': ('button_text', 'button_url'),
        }),
        ('Медиа', {
            'fields': ('image',),
        }),
        ('Настройки', {
            'fields': ('is_active',),
        }),
    )
    inlines = [PromoImageInline]


@admin.register(ServicePage)
class ServicePageAdmin(TabbedTranslationAdmin):
    list_display = ('slug', 'title')
    search_fields = ('slug', 'title')
    readonly_fields = ('slug',)
    fieldsets = (
        (None, {
            'fields': ('slug', 'title', 'description'),
        }),
        ('Кнопка', {
            'fields': ('button_text', 'button_url'),
        }),
    )


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
