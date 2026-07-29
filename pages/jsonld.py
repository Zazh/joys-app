"""JSON-LD страницы контактов: ContactPage + развёрнутая Organization.

Реквизиты продублированы из шаблонов (`base/components/_contact_links.html` —
ссылки каналов, `base/footer/_footer.html` — юрлицо и БИН, `pages/contacts.html` —
адрес и координаты карты): там данные для человека, здесь те же данные для
поисковиков. Меняются контакты — править оба места.
"""

from django.templatetags.static import static
from django.utils.translation import get_language, gettext as _

from catalog.jsonld import organization_id

PHONE = '+77766103836'
EMAIL = 'drjoysoriginal@gmail.com'
BIN = '220140017355'

# Координаты офиса — те же, что у карты Leaflet (data-lat/data-lng в contacts.html)
OFFICE_LAT = 51.15824
OFFICE_LNG = 71.43576

# Профили компании — те же ссылки, что в _contact_links.html
SAME_AS = [
    'https://www.instagram.com/drjoysoriginal/',
    'https://www.tiktok.com/@drjoysoriginal',
    'https://www.youtube.com/@drjoysoriginal',
    'https://t.me/drjoysoriginal',
]


def build_contact_page_jsonld(request, page, description=''):
    page_url = request.build_absolute_uri(page.get_absolute_url())

    address = {
        '@type': 'PostalAddress',
        'addressCountry': 'KZ',
        'addressLocality': _('Астана'),
        'streetAddress': _('р-н Байконыр, ул. А. Бараева, д. 13, н.п. 5'),
    }

    organization = {
        '@type': 'Organization',
        '@id': organization_id(request),
        'name': 'DR.JOYS',
        'legalName': _('ТОО «DR JOYS»'),
        'url': request.build_absolute_uri('/'),
        'logo': request.build_absolute_uri(static('dist/images/svgs/logo.svg')),
        # taxID читают агрегаторы, identifier — Google: даём БИН обоими способами
        'taxID': BIN,
        'identifier': {
            '@type': 'PropertyValue',
            'name': _('БИН'),
            'value': BIN,
        },
        'telephone': PHONE,
        'email': EMAIL,
        'address': address,
        # Координаты — на Place: geo у schema.org есть только у Place, у Organization нет
        'location': {
            '@type': 'Place',
            'name': _('ТОО «DR JOYS»'),
            'address': address,
            'geo': {
                '@type': 'GeoCoordinates',
                'latitude': OFFICE_LAT,
                'longitude': OFFICE_LNG,
            },
        },
        'contactPoint': {
            '@type': 'ContactPoint',
            'contactType': 'customer support',
            'telephone': PHONE,
            'email': EMAIL,
            'areaServed': 'KZ',
            'availableLanguage': ['ru', 'kk', 'en'],
        },
        'sameAs': SAME_AS,
    }

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
