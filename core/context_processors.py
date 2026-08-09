from urllib.parse import urlencode

from django.conf import settings
from django.urls import translate_url
from django.utils.translation import get_language_from_path

from core.seo import site_base_url


def analytics(request):
    return {
        'GA_MEASUREMENT_ID': settings.GA_MEASUREMENT_ID,
        'YM_COUNTER_IDS': settings.YM_COUNTER_IDS,
    }


def seo(request):
    """canonical, hreflang и флаг индексируемости для <head>.

    Домен берём из SITE_URL, а не из запроса: пока сайт отвечает и на
    app.dr-joys.com, и на dr-joys.com, каждый хост канонизировался бы сам на
    себя — для поисковика это две копии одного каталога. Переезд на боевой
    домен после этого сводится к правке SITE_URL в .env.
    """
    return {
        # Префикс для og:image и прочих абсолютных ссылок в <head>
        'site_url': site_base_url(),
        'canonical_url': _canonical_url(request),
        'hreflang_links': _hreflang_links(request),
        'site_indexable': settings.SITE_INDEXABLE,
        'google_site_verification': settings.GOOGLE_SITE_VERIFICATION,
    }


def _canonical_url(request):
    """Канонический адрес страницы — путь без мусора в query-строке.

    build_absolute_uri() тащит всё, что пришло в ссылке: utm_*, gclid, fbclid,
    ?region=. Каждая рекламная ссылка каноникализировалась сама на себя, и для
    поисковика это отдельная страница-дубль вместо одной канонической.

    Единственный параметр, который оставляем, — page: у страниц пагинации
    канонический адрес это они сами, а не первая страница (рекомендация Google).
    page=1 отбрасываем: он отдаёт тот же контент, что и адрес без параметра.
    """
    url = f'{site_base_url()}{request.path}'
    page = request.GET.get('page', '')
    if page.isdigit() and page != '1':
        url = f'{url}?{urlencode({"page": page})}'
    return url


def _hreflang_links(request):
    """Адреса той же страницы на других языках.

    translate_url разбирает текущий адрес и собирает его заново на нужном
    языке — в отличие от подмены первых трёх символов пути, это не ломается
    на страницах вне i18n_patterns (/orders/, /accounts/) и на неизвестных
    адресах: там языкового префикса нет либо resolve() не находит маршрут,
    переводы совпадают между собой, и hreflang не выводится вовсе.

    x-default указывает на русскую версию, а не на адрес без префикса:
    при prefix_default_language=True такой адрес только редиректит на /ru/.
    """
    if not get_language_from_path(request.path):
        return []

    base = site_base_url()
    links = [
        {'lang': code, 'url': f'{base}{translate_url(request.path, code)}'}
        for code, _name in settings.LANGUAGES
    ]
    if len({link['url'] for link in links}) != len(links):
        return []

    default = next(
        (link for link in links if link['lang'] == settings.LANGUAGE_CODE), None,
    )
    if default:
        links.append({'lang': 'x-default', 'url': default['url']})
    return links
