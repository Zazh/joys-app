"""JSON-LD страницы контактов: ContactPage + развёрнутая Organization.

Реквизиты берутся из `ContactSettings` — того же объекта, что рисует футер и
карточки каналов, через тот же кеш (`get_contacts()`). Шаблоны показывают эти
данные человеку, здесь те же данные уходят поисковикам; второго источника правды
больше нет, всё правится в бэкофисе (docs/contact_settings.md §5).

Развёрнутый блок — только тут: адрес, БИН и координаты относятся к одной
канонической странице. Глобальная Organization на всех страницах ограничена
телефоном и sameAs (см. catalog/jsonld.py).
"""

from django.templatetags.static import static
from django.utils.translation import get_language

from catalog.jsonld import organization_id

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
    page_url = request.build_absolute_uri(page.get_absolute_url())
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
        'url': request.build_absolute_uri('/'),
        'logo': request.build_absolute_uri(static('dist/images/svgs/logo.svg')),
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
