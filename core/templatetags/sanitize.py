"""Вывод HTML из бэкофиса без риска XSS.

Тексты страниц, блога, описаний товаров и модалок редактируются в WYSIWYG
и раньше выводились через |safe — то есть менеджер мог вставить <script>
и снять сессию владельца. Фильтр |sanitize оставляет разметку, но убирает
скрипты, обработчики событий и javascript:-ссылки.
"""
import nh3
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

ALLOWED_TAGS = {
    'p', 'br', 'hr', 'div', 'span',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'strong', 'b', 'em', 'i', 'u', 's', 'sub', 'sup', 'mark', 'small',
    'ul', 'ol', 'li', 'dl', 'dt', 'dd',
    'a', 'img', 'figure', 'figcaption',
    'blockquote', 'pre', 'code',
    'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td', 'caption',
    'iframe',  # встроенные видео (YouTube/Vimeo)
}

ALLOWED_ATTRIBUTES = {
    '*': {'class', 'id', 'style', 'title', 'dir', 'lang'},
    # rel не указываем: его проставляет сам nh3 через link_rel
    'a': {'href', 'target'},
    'img': {'src', 'alt', 'width', 'height', 'loading', 'srcset', 'sizes'},
    'iframe': {
        'src', 'width', 'height', 'allow', 'allowfullscreen',
        'frameborder', 'title', 'loading',
    },
    'td': {'colspan', 'rowspan'},
    'th': {'colspan', 'rowspan', 'scope'},
    'ol': {'start', 'type'},
}

# Схемы ссылок: javascript: и data: сюда сознательно не входят
ALLOWED_SCHEMES = {'http', 'https', 'mailto', 'tel'}


@register.filter(name='sanitize')
def sanitize(value):
    """Очистить HTML и отдать его как безопасный для вывода."""
    if not value:
        return ''
    return mark_safe(nh3.clean(
        str(value),
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_SCHEMES,
        link_rel='noopener noreferrer',
    ))
