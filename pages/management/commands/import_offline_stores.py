"""Разовый перенос оффлайн-точек из body страницы partners в OfflineStore.

Источник — HTML из Quill: города в <h3>, названия магазинов в <strong>,
режим («Самовывоз и доставка» / «Только самовывоз») в <em>, адреса — ссылками
на 2ГИС, у большинства которых координаты зашиты прямо в URL. После переноса
точки правятся в бэкофисе, body страницы больше не читается.
"""

import html
import re
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from pages.models import OfflineStore, Page

# Токены в порядке документа. <a> внутри <strong> достаётся из содержимого
# strong отдельным проходом: альтернатива срабатывает по позиции, и вложенную
# ссылку внешний токен съедает целиком
_TOKEN = re.compile(
    r'<h3[^>]*>(?P<h3>.*?)</h3>'
    r'|<strong[^>]*>(?P<strong>.*?)</strong>'
    r'|<a\s[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<atext>.*?)</a>',
    re.S | re.I,
)
_EM = re.compile(r'<em[^>]*>(.*?)</em>', re.S | re.I)
_LINK = re.compile(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S | re.I)
_TAG = re.compile(r'<[^>]+>')

# Правки координат по точкам, которым ссылка 2ГИС ничего не даёт:
# либо в URL нет координат (/geo/…, /inside/…), либо ссылка повторяет соседний
# филиал той же сети. Дома найдены в OSM (Nominatim, июль 2026); None — точного
# дома в OSM нет, координаты доставляются в бэкофисе ссылкой 2ГИС.
# Формат: (город, подстрока адреса, lat, lng); для точки берётся первое совпадение.
MANUAL_FIXES = [
    ('Алматы', 'Керемет', None, None),  # ссылка дублирует Назарбаева, 77
    ('Караганда', 'Язева', Decimal('49.775963'), Decimal('73.134061')),  # ссылка дублирует ТЦ «Умай»
    ('Атырау', 'Курмангазы', Decimal('47.095435'), Decimal('51.873855')),
    ('Атырау', 'Гурьевская', Decimal('47.103093'), Decimal('51.926487')),
    ('Атырау', 'Абая', None, None),
    ('Уральск', 'Абая, 88/1', None, None),
    ('Усть-Каменогорск', 'Кабанбай', Decimal('49.949878'), Decimal('82.636078')),
    ('Усть-Каменогорск', 'Протозанова, 89', Decimal('49.950821'), Decimal('82.606877')),
]


def _clean(text):
    """Видимый текст из куска HTML: без тегов, сущностей и невидимых знаков."""
    text = _TAG.sub('', text)
    text = html.unescape(text)
    text = text.replace('​', '').replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', text).strip()


def parse_partner_body(body):
    """Список точек из HTML страницы: [{city, name, address, url, fulfillment}].

    Линейный проход по токенам. Город — <h3> с двоеточием на конце («Алматы:»),
    он же сбрасывает магазин и режим. <strong> может нести сразу всё: маркер
    режима в <em>, название магазина остатком текста, адрес вложенной ссылкой.
    """
    points = []
    city = shop = None
    mode = OfflineStore.Fulfillment.PICKUP_DELIVERY

    def add_point(href, text):
        address = _clean(text)
        if city and shop and address:
            points.append({
                'city': city, 'name': shop, 'address': address,
                'url': html.unescape(href.strip()), 'fulfillment': mode,
            })

    for token in _TOKEN.finditer(body):
        if token['h3'] is not None:
            heading = _clean(token['h3'])
            if heading.endswith(':'):
                city = heading.rstrip(':').strip().title()
                shop = None
                mode = OfflineStore.Fulfillment.PICKUP_DELIVERY
        elif token['strong'] is not None:
            content = token['strong']
            for marker in _EM.findall(content):
                marker = _clean(marker)
                if 'Только самовывоз' in marker:
                    mode = OfflineStore.Fulfillment.PICKUP
                elif 'Самовывоз' in marker:
                    mode = OfflineStore.Fulfillment.PICKUP_DELIVERY
            for href, text in _LINK.findall(content):
                add_point(href, text)
            residual = _clean(_LINK.sub('', _EM.sub('', content)))
            if residual and not residual.endswith(':'):
                shop = residual
        else:
            add_point(token['href'], token['atext'])

    return points


class Command(BaseCommand):
    help = 'Переносит оффлайн-точки из body страницы partners в модель OfflineStore'

    def add_arguments(self, parser):
        parser.add_argument(
            '--replace', action='store_true',
            help='Удалить существующие точки перед импортом (иначе при непустой таблице — отказ)',
        )

    def handle(self, *args, **options):
        page = Page.objects.filter(slug='partners').first()
        if not page or not page.body_ru:
            raise CommandError('Страница partners не найдена или body пуст.')
        if OfflineStore.objects.exists() and not options['replace']:
            raise CommandError(
                'Точки уже импортированы. Повторный запуск с --replace сотрёт '
                'правки, сделанные в бэкофисе.'
            )

        points = parse_partner_body(page.body_ru)
        if not points:
            raise CommandError('В body страницы не нашлось ни одной точки.')

        stores, no_coords = [], []
        order_in_city = {}
        for point in points:
            lat = lng = None
            pair = OfflineStore.coords_from_2gis(point['url'])
            if pair:
                lat, lng = Decimal(str(pair[0])), Decimal(str(pair[1]))
            for fix_city, fix_addr, fix_lat, fix_lng in MANUAL_FIXES:
                if point['city'] == fix_city and fix_addr in point['address']:
                    lat, lng = fix_lat, fix_lng
                    break
            if lat is None:
                no_coords.append(point)
            order_in_city[point['city']] = order_in_city.get(point['city'], 0) + 10
            stores.append(OfflineStore(
                city=point['city'], name=point['name'], address=point['address'],
                lat=lat, lng=lng, map_url=point['url'],
                fulfillment=point['fulfillment'], order=order_in_city[point['city']],
            ))

        with transaction.atomic():
            OfflineStore.objects.all().delete()
            OfflineStore.objects.bulk_create(stores)

        cities = {}
        for store in stores:
            cities[store.city] = cities.get(store.city, 0) + 1
        self.stdout.write(self.style.SUCCESS(f'Импортировано точек: {len(stores)}'))
        for city_name, count in sorted(cities.items(), key=lambda kv: -kv[1]):
            self.stdout.write(f'  {city_name}: {count}')
        if no_coords:
            self.stdout.write(self.style.WARNING(
                f'Без координат ({len(no_coords)}) — уточнить ссылку 2ГИС в бэкофисе:'
            ))
            for point in no_coords:
                self.stdout.write(f'  {point["city"]}: {point["name"]} — {point["address"]}')
