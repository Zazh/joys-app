"""JSON-LD страницы контактов: ContactPage + развёрнутая Organization.

Реквизиты берутся из `ContactSettings` — того же объекта, что рисует футер и
карточки каналов, через тот же кеш (`get_contacts()`). Шаблоны показывают эти
данные человеку, здесь те же данные уходят поисковикам; второго источника правды
больше нет, всё правится в бэкофисе (docs/contact_settings.md §5).

Развёрнутый блок — только тут: адрес, БИН и координаты относятся к одной
канонической странице. Глобальная Organization на всех страницах ограничена
телефоном и sameAs (см. catalog/jsonld.py).
"""

from django.utils.translation import get_language

from catalog.jsonld import logo_url, organization_id
from core.seo import absolute_url, plain_text

from .context_processors import get_contacts


def _without_empty(block):
    """Убрать ключи с пустым значением.

    Пустой канал — не пустая строка в разметке, а отсутствующий ключ: пустой
    email, telephone или sameAs поисковик прочитает как заявленный и сломанный
    (docs/contact_settings.md §5). Фильтруем блок целиком, а не перечисляем
    ключи по именам: иначе новое необязательное поле про это правило забудет.
    """
    return {key: value for key, value in block.items() if value != '' and value != []}


def build_contact_page_jsonld(request, page, description=''):
    page_url = absolute_url(page.get_absolute_url())
    contacts = get_contacts()

    address = {
        '@type': 'PostalAddress',
        'addressCountry': 'KZ',
        'addressLocality': contacts.address_locality,
        'streetAddress': contacts.address_street,
    }

    # Место офиса — отдельным Place: geo у schema.org есть только у Place,
    # у Organization его нет. Без координат Place не нужен вовсе.
    location = {
        '@type': 'Place',
        'name': contacts.legal_name,
        'address': address,
    }
    if contacts.geo:
        location['geo'] = {
            '@type': 'GeoCoordinates',
            'latitude': contacts.geo['lat'],
            'longitude': contacts.geo['lng'],
        }

    contact_point = _without_empty({
        '@type': 'ContactPoint',
        'contactType': 'customer support',
        'telephone': contacts.phone_e164,
        'email': contacts.email,
        'areaServed': 'KZ',
        'availableLanguage': ['ru', 'kk', 'en'],
    })

    organization = _without_empty({
        '@type': 'Organization',
        '@id': organization_id(request),
        'name': 'DR.JOYS',
        'legalName': contacts.legal_name,
        'url': absolute_url('/'),
        'logo': logo_url(),
        # taxID читают агрегаторы, identifier — Google: даём БИН обоими способами
        'taxID': contacts.bin,
        'identifier': {
            '@type': 'PropertyValue',
            'name': contacts.bin_label,
            'value': contacts.bin,
        },
        'telephone': contacts.phone_e164,
        'email': contacts.email,
        'address': address,
        'location': location,
        'contactPoint': contact_point,
        'sameAs': contacts.social_links,
    })

    result = {
        '@context': 'https://schema.org',
        '@type': 'ContactPage',
        '@id': page_url,
        'url': page_url,
        'name': page.meta_title or page.title,
        'inLanguage': get_language(),
        'mainEntity': organization,
    }
    if description:
        result['description'] = description
    return result


def build_blog_list_jsonld(request, posts):
    """Список статей — Blog + ItemList, по образцу каталога.

    Карточки в вёрстке были размечены как BlogPosting, но без publisher, author
    и dateModified: для Google это невалидные статьи, а не список ссылок.
    Список ссылок и надо размечать списком — сами статьи описывает страница
    статьи (`build_blogposting_jsonld`).
    """
    items = []
    for i, post in enumerate(posts, 1):
        item = {
            '@type': 'ListItem',
            'position': i,
            'url': absolute_url(post.get_absolute_url()),
            'name': post.title,
        }
        items.append(item)

    return {
        '@context': 'https://schema.org',
        '@type': 'Blog',
        '@id': absolute_url(request.path) + '#blog',
        'name': 'DR.JOYS',
        'inLanguage': get_language(),
        'mainEntity': {
            '@type': 'ItemList',
            'itemListElement': items,
            'numberOfItems': len(items),
        },
    }


def build_blogposting_jsonld(request, post, description=''):
    """Разметка статьи блога.

    JSON-LD вместо микроразметки в вёрстке: Google явно рекомендует его как
    основной формат, а держать два описания одного объекта на странице — способ
    однажды их рассинхронизировать.

    `publisher` обязателен и обязан быть объектом Organization с логотипом:
    строкой «DR.JOYS», как было в itemprop, Google эту разметку не примет.
    headline режем по 110 символам — предел из документации, длиннее блок
    считается невалидным.
    """
    post_url = absolute_url(post.get_absolute_url())

    result = {
        '@context': 'https://schema.org',
        '@type': 'BlogPosting',
        '@id': post_url,
        'mainEntityOfPage': {'@type': 'WebPage', '@id': post_url},
        'url': post_url,
        'headline': plain_text(post.title, 110),
        'inLanguage': get_language(),
        'datePublished': post.published_at.isoformat(),
        'dateModified': post.updated_at.isoformat(),
        'author': {
            '@type': 'Organization' if not post.author else 'Person',
            'name': post.author or 'DR.JOYS',
            'url': absolute_url('/'),
        },
        'publisher': {
            '@type': 'Organization',
            '@id': organization_id(request),
            'name': 'DR.JOYS',
            'logo': {'@type': 'ImageObject', 'url': logo_url()},
        },
    }
    if description:
        result['description'] = description
    if post.cover_image:
        result['image'] = [absolute_url(post.cover_image.url)]
    if post.category:
        result['articleSection'] = post.category.name
    return result
