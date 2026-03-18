from modeltranslation.translator import register, TranslationOptions

from .models import InquiryForm, InquiryField


@register(InquiryForm)
class InquiryFormTO(TranslationOptions):
    fields = ('title', 'description', 'success_title', 'success_text', 'submit_text')


@register(InquiryField)
class InquiryFieldTO(TranslationOptions):
    fields = ('label', 'placeholder', 'choices_text')
