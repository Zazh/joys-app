from django import template

from modals.models import InteractiveModal

register = template.Library()


@register.simple_tag
def get_interactive_modal(slug):
    """Загрузить интерактивную модалку по slug."""
    try:
        return InteractiveModal.objects.prefetch_related(
            'steps', 'steps__inquiry_form', 'steps__inquiry_form__fields'
        ).get(slug=slug, is_active=True)
    except InteractiveModal.DoesNotExist:
        return None
