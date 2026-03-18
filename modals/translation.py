from modeltranslation.translator import register, TranslationOptions

from .models import InteractiveModal, ModalStep


@register(InteractiveModal)
class InteractiveModalTO(TranslationOptions):
    fields = ('trigger_text',)


@register(ModalStep)
class ModalStepTO(TranslationOptions):
    fields = ('text', 'button_text', 'badge_text', 'cta_text')
