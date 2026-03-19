from modeltranslation.translator import register, TranslationOptions

from .models import EmailTemplate


@register(EmailTemplate)
class EmailTemplateTO(TranslationOptions):
    fields = ('subject', 'body')
