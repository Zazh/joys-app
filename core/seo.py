"""SEO-инфраструктура: базовый адрес сайта, robots.txt, llms.txt.

Единственный источник домена — settings.SITE_URL. Ни request.get_host(),
ни таблица django_site: при переезде app.dr-joys.com → dr-joys.com меняется
одна переменная в .env, и вместе с ней едут карта сайта, canonical, hreflang
и ссылки в robots.txt/llms.txt.

Пока сайт отвечает сразу на двух доменах, это же спасает от дублей: копия на
техническом адресе канонизируется на боевой, а не сама на себя.
"""
from html import unescape
from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpResponse
from django.utils import translation
from django.utils.html import strip_tags
from django.views.decorators.cache import cache_page


def site_base_url():
    """`https://dr-joys.com` — схема и домен без завершающего слэша."""
    parts = urlsplit(settings.SITE_URL)
    return f'{parts.scheme}://{parts.netloc}'


def absolute_url(path):
    return f'{site_base_url()}{path}'


# ─── Мета-теги ───

BRAND = 'DR.JOYS'
DESCRIPTION_LIMIT = 160  # столько Google показывает в сниппете


def plain_text(text, limit=DESCRIPTION_LIMIT):
    """Однострочный текст без HTML, обрезанный по границе слова.

    Контент приходит из визуального редактора бэкофиса, то есть с тегами
    и html-сущностями внутри: в атрибут `content` они попадать не должны.
    Обрыв на середине слова в сниппете выглядит как ошибка, поэтому режем
    по последнему пробелу.
    """
    if not text:
        return ''
    text = ' '.join(strip_tags(unescape(str(text))).split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if ' ' in cut:
        cut = cut[:cut.rindex(' ')]
    return cut.rstrip(' ,.;:—-') + '…'


def first_filled(*candidates, limit=DESCRIPTION_LIMIT):
    """Первое непустое описание из списка кандидатов."""
    for candidate in candidates:
        text = plain_text(candidate, limit)
        if text:
            return text
    return ''


def with_brand(title, section=''):
    """`Название — Раздел DR.JOYS`, без повторов внутри строки.

    Заголовок из бэкофиса часто уже содержит и бренд, и название раздела
    («О компании DR.JOYS»), а шаблон дописывал их вторым слоем —
    получалось «О компании DR.JOYS — DR.JOYS». Дописываем только то,
    чего в строке ещё нет.
    """
    title = ' '.join(str(title).split())
    lowered = title.lower()
    tail = [part for part in (section, BRAND) if part and part.lower() not in lowered]
    return f'{title} — {" ".join(tail)}' if tail else title


def category_suffix(category_name, subject):
    """Название категории для хвоста заголовка — или пусто, если оно уже в тексте.

    «Смазка на водной основе» в категории «Смазки» дала бы заголовок
    «Смазка на водной основе — Смазки DR.JOYS»: одно слово дважды подряд.
    Сравниваем по грубой основе (первые 5 букв) — падежей и чисел в русском
    больше, чем стоит разбирать ради строки в заголовке.
    """
    if not category_name:
        return ''
    stem = category_name.lower()[:5]
    return '' if stem and stem in subject.lower() else category_name


# ─── robots.txt ───

def robots_txt(request):
    """Директивы для поисковых роботов.

    SITE_INDEXABLE=False (staging, превью) закрывает сайт целиком: копия
    каталога на техническом домене в индексе — это дубли боевых страниц.

    Служебные разделы закрыты, а рекламные параметры (utm_*, gclid) — нет:
    закрытый в robots.txt адрес робот не скачивает и потому не видит на нём
    rel=canonical, из-за чего URL всё равно попадает в индекс, но без
    склейки с основным. За склейку отвечает canonical (core.context_processors),
    Яндексу дополнительно помогает Clean-param в его собственной группе.
    """
    if not settings.SITE_INDEXABLE:
        body = 'User-agent: *\nDisallow: /\n'
        return HttpResponse(body, content_type='text/plain; charset=utf-8')

    # Разделы без языкового префикса.
    # ADMIN_URL здесь намеренно нет: robots.txt читает кто угодно, и строка с
    # секретным адресом админки раздавала бы его всем желающим. Ссылок на него
    # на сайте нет — робот его и не найдёт.
    disallow = [
        '/backoffice/',              # бэкофис
        '/api/',                     # внутренний API
        '/accounts/',                # OAuth-коллбэки allauth
        '/orders/',                  # корзина, избранное, оформление, оплата
        '/region/',                  # смена региона
        '/qrcodes/',                 # короткие ссылки с UTM-метками
        '/silk/',                    # профайлер
    ]
    # Те же разделы внутри i18n_patterns отвечают ещё и по /ru/, /kk/, /en/
    for lang_code, _name in settings.LANGUAGES:
        disallow += [f'/{lang_code}/accounts/', f'/{lang_code}/quiz/']

    # Две группы с одним и тем же списком закрытого. Отдельная группа Яндексу
    # нужна из-за Clean-param: директиву понимает только он, а в общей группе
    # Google печатал на неё предупреждение в Search Console («правило, которое
    # не учитывается Googlebot»). Раз у Яндекса есть своя группа, он читает
    # только её — поэтому Disallow в ней те же, из одного списка
    groups = []
    for agent in ('*', 'Yandex'):
        lines = [f'User-agent: {agent}']
        lines += [f'Disallow: {path}' for path in disallow]
        if agent == 'Yandex':
            # Рекламные метки склеиваем для Яндекса — иначе один товар попадает
            # в индекс десятком адресов из рассылок и рекламных кабинетов.
            lines.append(
                'Clean-param: utm_source&utm_medium&utm_campaign&utm_term'
                '&utm_content&gclid&yclid&fbclid&from&region'
            )
        groups.append('\n'.join(lines))

    body = '\n\n'.join(groups) + f'\n\nSitemap: {absolute_url("/sitemap.xml")}\n'
    return HttpResponse(body, content_type='text/plain; charset=utf-8')


# ─── llms.txt ───

_LLMS_SUMMARY = (
    'Официальный сайт бренда DR.JOYS — производителя ультратонких презервативов '
    'толщиной 0,02 мм. Интернет-магазин с доставкой по Казахстану и России, '
    'цены и наличие зависят от выбранного региона.'
)

_LLMS_FACTS = [
    'Бренд: DR.JOYS.',
    'Категория товаров: презервативы и средства личной гигиены (18+).',
    'Ключевая характеристика: толщина 0,02 мм, «неощутимые на 95%».',
    'Языки сайта: русский (/ru/), казахский (/kk/), английский (/en/). '
    'Языковой префикс обязателен для всех страниц.',
    'Регионы доставки: Казахстан и Россия. Регион хранится в cookie '
    '`drjoys_region` и влияет на цену, валюту и наличие.',
    'Контент, закрытый для индексации и обхода: /backoffice/, /api/, '
    '/accounts/, /orders/, админка.',
]


def _md_link(title, path, note=''):
    line = f'- [{title}]({absolute_url(path)})'
    return f'{line}: {note}' if note else line


@cache_page(60 * 60)
def llms_txt(request):
    """Карта сайта для языковых моделей — формат llmstxt.org.

    Ссылки собираются из тех же моделей, что и sitemap.xml, поэтому файл не
    расходится с сайтом при добавлении товаров и статей. Язык — русский:
    он основной, остальные версии отличаются только префиксом в адресе.
    """
    from catalog.models import Category, Product
    from pages.models import BlogPost, Page

    with translation.override(settings.LANGUAGE_CODE):
        lines = [
            '# DR.JOYS',
            '',
            f'> {_LLMS_SUMMARY}',
            '',
        ]
        lines += [f'- {fact}' for fact in _LLMS_FACTS]
        lines += ['', '## Основные страницы', '']
        lines += [
            _md_link('Главная', '/ru/', 'о бренде, технология, отзывы покупателей'),
            _md_link('Каталог', '/ru/catalog/', 'все товары DR.JOYS'),
            _md_link('Блог', '/ru/blog/', 'статьи о здоровье, отношениях и продукте'),
        ]

        categories = list(Category.objects.filter(is_active=True))
        if categories:
            lines += ['', '## Категории каталога', '']
            lines += [
                _md_link(c.name, c.get_absolute_url(), plain_text(c.description))
                for c in categories
            ]

        products = list(
            Product.objects
            .filter(is_active=True)
            .select_related('category')
            .order_by('category__order', 'name')
        )
        if products:
            lines += ['', '## Товары', '']
            lines += [
                _md_link(
                    p.name,
                    p.get_absolute_url(),
                    plain_text(p.tagline or p.description),
                )
                for p in products
            ]

        pages = list(
            Page.objects
            .filter(is_published=True)
            .select_related('category')
            .order_by('order', 'title')
        )
        if pages:
            lines += ['', '## Информация о компании', '']
            lines += [
                _md_link(p.title, p.get_absolute_url(), plain_text(p.meta_description))
                for p in pages
            ]

        posts = list(
            BlogPost.objects
            .filter(is_published=True)
            .order_by('-published_at')[:50]
        )
        if posts:
            lines += ['', '## Блог', '']
            lines += [
                _md_link(
                    post.title,
                    post.get_absolute_url(),
                    plain_text(post.meta_description or post.excerpt),
                )
                for post in posts
            ]

        lines += [
            '',
            '## Optional',
            '',
            _md_link('Карта сайта (XML)', '/sitemap.xml', 'все адреса с hreflang'),
            '- Контакты: info@dr-joys.com',
            '',
        ]

    return HttpResponse('\n'.join(lines), content_type='text/plain; charset=utf-8')
