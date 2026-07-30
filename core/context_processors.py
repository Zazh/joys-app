from urllib.parse import urlencode

from django.conf import settings


def analytics(request):
    return {'GA_MEASUREMENT_ID': settings.GA_MEASUREMENT_ID}


def canonical(request):
    """Канонический адрес страницы — путь без мусора в query-строке.

    build_absolute_uri() тащит всё, что пришло в ссылке: utm_*, gclid, fbclid,
    ?region=. Каждая рекламная ссылка каноникализировалась сама на себя, и для
    поисковика это отдельная страница-дубль вместо одной канонической.

    Единственный параметр, который оставляем, — page: у страниц пагинации
    канонический адрес это они сами, а не первая страница (рекомендация Google).
    page=1 отбрасываем: он отдаёт тот же контент, что и адрес без параметра.
    """
    url = request.build_absolute_uri(request.path)
    page = request.GET.get('page', '')
    if page.isdigit() and page != '1':
        url = f'{url}?{urlencode({"page": page})}'
    return {'canonical_url': url}
