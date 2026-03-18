from django import template

from quiz.models import QuizQuestion, QuizResultText

register = template.Library()


@register.simple_tag
def get_quiz_questions():
    """Все активные вопросы с вариантами ответов."""
    return list(
        QuizQuestion.objects
        .filter(is_active=True)
        .prefetch_related('options')
        .order_by('order')
    )


@register.simple_tag
def get_quiz_result_text():
    """Тексты экрана результата."""
    return QuizResultText.load()
