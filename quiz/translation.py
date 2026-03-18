from modeltranslation.translator import register, TranslationOptions

from .models import QuizQuestion, QuizOption, QuizResultText


@register(QuizQuestion)
class QuizQuestionTO(TranslationOptions):
    fields = ('text',)


@register(QuizOption)
class QuizOptionTO(TranslationOptions):
    fields = ('label',)


@register(QuizResultText)
class QuizResultTextTO(TranslationOptions):
    fields = ('title', 'button_text', 'more_text')
