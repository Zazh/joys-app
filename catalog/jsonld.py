import json

from django.utils.translation import gettext as _


def _get_region_price(size, region):
    """Достаёт цену размера для региона из prefetched _region_prices."""
    if region:
        region_prices = getattr(size, '_region_prices', None)
        if region_prices is not None:
            for rp in region_prices:
                if rp.region_id == region.pk:
                    return rp.price
    return size.price


def _absolute_url(request, path):
    return request.build_absolute_uri(path)


def _image_url(request, image_field):
    if image_field and image_field.name:
        return request.build_absolute_uri(image_field.url)
    return None


# ─── BreadcrumbList ───

def build_breadcrumb_jsonld(request, breadcrumbs):
    items = []
    for i, crumb in enumerate(breadcrumbs, 1):
        item = {
            '@type': 'ListItem',
            'position': i,
            'name': crumb['name'],
        }
        if crumb['url']:
            item['item'] = _absolute_url(request, crumb['url'])
        items.append(item)

    return {
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        'itemListElement': items,
    }


# ─── Product ───

def build_product_jsonld(request, product, sizes, cover_image, main_images, characteristics, region=None):
    product_url = _absolute_url(request, product.get_absolute_url())

    # Картинки: cover первый, потом остальные
    images = []
    if cover_image:
        url = _image_url(request, cover_image.image)
        if url:
            images.append(url)
    for img in main_images:
        if cover_image and img.pk == cover_image.pk:
            continue
        url = _image_url(request, img.image)
        if url:
            images.append(url)
    if not images:
        images.append(_absolute_url(request, '/static/dist/images/placeholder.svg'))

    # Offers из размеров
    currency_code = region.currency_code if region else 'KZT'
    offers_list = []
    prices = []
    for size in sizes:
        price = _get_region_price(size, region)
        offers_list.append({
            '@type': 'Offer',
            'name': f'{product.name} {size.name}',
            'sku': size.sku,
            'price': str(price),
            'priceCurrency': currency_code,
            'availability': (
                'https://schema.org/PreOrder' if size.coming_soon
                else 'https://schema.org/InStock' if size.in_stock and price
                else 'https://schema.org/OutOfStock'
            ),
            'itemCondition': 'https://schema.org/NewCondition',
            'url': product_url,
        })
        prices.append(price)

    if len(offers_list) > 1:
        offers_block = {
            '@type': 'AggregateOffer',
            'lowPrice': str(min(prices)),
            'highPrice': str(max(prices)),
            'priceCurrency': currency_code,
            'offerCount': len(offers_list),
            'offers': offers_list,
        }
    elif len(offers_list) == 1:
        offers_block = offers_list[0]
    else:
        offers_block = None

    # Характеристики → additionalProperty
    additional = []
    for pc in characteristics:
        prop = {
            '@type': 'PropertyValue',
            'name': pc.characteristic.name,
            'value': pc.value,
        }
        if pc.characteristic.unit:
            prop['unitText'] = pc.characteristic.unit.abbr
        additional.append(prop)

    result = {
        '@context': 'https://schema.org',
        '@type': 'Product',
        'name': product.name,
        'url': product_url,
        'image': images,
        'description': product.description or product.name,
        'brand': {'@type': 'Brand', 'name': 'DR.JOYS'},
        'category': product.category.name,
        'sku': sizes[0].sku if sizes else None,
        'datePublished': product.created_at.isoformat(),
    }
    if offers_block:
        result['offers'] = offers_block
    if additional:
        result['additionalProperty'] = additional

    return {k: v for k, v in result.items() if v is not None}


# ─── CollectionPage + ItemList (каталог) ───

def build_catalog_itemlist_jsonld(request, products, current_category=None, region=None):
    currency_code = region.currency_code if region else 'KZT'
    items = []
    for i, product in enumerate(products, 1):
        cover = product.get_cover_image()

        image_url = _image_url(request, cover.image) if cover else None

        # Минимальная цена для текущего региона
        product_sizes = list(product.sizes.all())
        region_prices = [_get_region_price(s, region) for s in product_sizes]
        lowest_price = min(region_prices, default=None)

        list_item = {
            '@type': 'ListItem',
            'position': i,
            'item': {
                '@type': 'Product',
                'name': product.name,
                'url': _absolute_url(request, product.get_absolute_url()),
            },
        }
        if image_url:
            list_item['item']['image'] = image_url
        if lowest_price is not None:
            list_item['item']['offers'] = {
                '@type': 'Offer',
                'price': str(lowest_price),
                'priceCurrency': currency_code,
            }
        items.append(list_item)

    return {
        '@context': 'https://schema.org',
        '@type': 'CollectionPage',
        'name': current_category.name if current_category else _('Каталог презервативов DR.JOYS'),
        'mainEntity': {
            '@type': 'ItemList',
            'itemListElement': items,
            'numberOfItems': len(items),
        },
    }


# ─── FAQPage ───

def build_faq_jsonld(faqs):
    if not faqs:
        return None

    valid_faqs = [faq for faq in faqs if faq.question and faq.answer]
    if not valid_faqs:
        return None

    return {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        'mainEntity': [
            {
                '@type': 'Question',
                'name': faq.question,
                'acceptedAnswer': {
                    '@type': 'Answer',
                    'text': faq.answer,
                },
            }
            for faq in valid_faqs
        ],
    }


# ─── Organization ───

def organization_id(request):
    """Стабильный @id организации.

    Глобальный блок и развёрнутая разметка на странице контактов описывают одно
    юрлицо — по этому идентификатору парсеры склеивают их, а не считают двумя
    разными компаниями.
    """
    return _absolute_url(request, '/') + '#organization'


def build_organization_jsonld(request):
    """Глобальный блок организации — он есть на каждой странице сайта.

    Телефон и sameAs здесь, а адрес, БИН и координаты — нет (решение Сессии 2,
    docs/contact_settings.md §5). sameAs — то, чем Google связывает соцпрофили с
    компанией, и до этого он лежал только на /contacts/: на главной, куда парсер
    приходит первым делом, у организации не было ни одного такого признака.
    Адрес и реквизиты, наоборот, относятся к одной канонической странице —
    дублировать их в каталоге и в каждой карточке товара незачем.

    Второго источника правды не появляется: значения те же, из ContactSettings,
    из того же кеша, что уже читает футер на этой же странице.
    """
    from pages.context_processors import get_contacts

    contacts = get_contacts()
    result = {
        '@context': 'https://schema.org',
        '@type': 'Organization',
        '@id': organization_id(request),
        'name': 'DR.JOYS',
        'url': _absolute_url(request, '/'),
        'logo': _absolute_url(request, '/static/dist/images/svgs/logo.svg'),
    }
    if contacts.phone:
        result['telephone'] = contacts.phone
    if contacts.social_links:
        result['sameAs'] = contacts.social_links
    return result


# ─── WebSite ───

def build_website_jsonld(request):
    return {
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        'name': 'DR.JOYS',
        'url': _absolute_url(request, '/'),
    }


# ─── Сериализация ───

def _escape_for_script_tag(payload):
    """Экранировать символы, которыми можно выйти из <script>.

    json.dumps не трогает `</script>`, поэтому название товара вида
    `</script><script>...` вырвалось бы из блока JSON-LD и выполнилось.
    \\uXXXX остаётся валидным JSON и корректно читается парсерами.
    """
    return (
        payload
        .replace('<', '\\u003c')
        .replace('>', '\\u003e')
        .replace('&', '\\u0026')
    )


def serialize_jsonld(*dicts):
    return [
        _escape_for_script_tag(json.dumps(d, ensure_ascii=False))
        for d in dicts if d is not None
    ]
