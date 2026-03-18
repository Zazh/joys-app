from modeltranslation.translator import register, TranslationOptions

from .models import Region


@register(Region)
class RegionTO(TranslationOptions):
    fields = ('name',)
