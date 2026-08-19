from modeltranslation.translator import register, TranslationOptions

from .models import PageCategory, Page, BlogCategory, BlogPost, MenuItem, HeroSection, FeatureSlide, PromoBlock, ServicePage, ContactSettings, City


@register(PageCategory)
class PageCategoryTO(TranslationOptions):
    fields = ('name', 'description')


@register(Page)
class PageTO(TranslationOptions):
    fields = ('title', 'body', 'meta_title', 'meta_description')


@register(BlogCategory)
class BlogCategoryTO(TranslationOptions):
    fields = ('name',)


@register(BlogPost)
class BlogPostTO(TranslationOptions):
    fields = ('title', 'excerpt', 'body', 'meta_title', 'meta_description')


@register(MenuItem)
class MenuItemTO(TranslationOptions):
    fields = ('title',)


@register(HeroSection)
class HeroSectionTO(TranslationOptions):
    fields = ('title', 'subtitle', 'button_catalog_text', 'button_buy_text')


@register(FeatureSlide)
class FeatureSlideTO(TranslationOptions):
    fields = ('title', 'text', 'button_text')


@register(PromoBlock)
class PromoBlockTO(TranslationOptions):
    fields = ('title', 'subtitle', 'text', 'button_text')


@register(ServicePage)
class ServicePageTO(TranslationOptions):
    fields = ('title', 'description', 'button_text')


@register(ContactSettings)
class ContactSettingsTO(TranslationOptions):
    fields = ('legal_name', 'bin_label', 'address_locality', 'address_street', 'work_hours')


@register(City)
class CityTO(TranslationOptions):
    fields = ('name',)
