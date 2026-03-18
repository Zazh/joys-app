from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import (
    Category, Product, ProductSize, RegionPrice, Stock,
    UnitOfMeasure, Characteristic, ProductCharacteristic,
)
from orders.models import Order
from regions.models import Region


class Command(BaseCommand):
    help = 'Заполнение каталога реальными товарами DR.JOYS'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Удалить старые товары перед загрузкой',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Удаление старых данных...')
            Order.objects.all().delete()
            Product.objects.all().delete()
            Characteristic.objects.all().delete()
            UnitOfMeasure.objects.all().delete()

        # ─── Категория ───
        cat, _ = Category.objects.update_or_create(
            slug='prezervativy',
            defaults={
                'name_ru': 'Презервативы',
                'name_kk': 'Презервативтер',
                'name_en': 'Condoms',
                'description_ru': 'Презервативы DR.JOYS — премиальное качество',
                'description_en': 'DR.JOYS Condoms — premium quality',
                'order': 1,
                'is_active': True,
                'meta_title_ru': 'Презервативы DR.JOYS — купить онлайн',
                'meta_title_en': 'DR.JOYS Condoms — buy online',
                'meta_description_ru': 'Каталог презервативов DR.JOYS — ультратонкие 0.02 мм, ароматизированные, точечно-ребристые',
                'meta_description_en': 'DR.JOYS condoms catalog — ultra-thin 0.02mm, flavored, dotted-ribbed',
            },
        )
        self.stdout.write(self.style.SUCCESS(f'Категория: {cat.name}'))

        # ─── Единицы измерения ───
        mm, _ = UnitOfMeasure.objects.update_or_create(
            abbr='мм', defaults={'name_ru': 'Миллиметр', 'name_en': 'Millimeter', 'data_type': 'decimal'},
        )
        mg, _ = UnitOfMeasure.objects.update_or_create(
            abbr='мг', defaults={'name_ru': 'Миллиграмм', 'name_en': 'Milligram', 'data_type': 'integer'},
        )
        months, _ = UnitOfMeasure.objects.update_or_create(
            abbr='мес', defaults={'name_ru': 'Месяц', 'name_en': 'Month', 'data_type': 'integer'},
        )

        # ─── Характеристики ───
        chars = {}
        char_defs = [
            ('material', 'Материал', 'Material', None, 1),
            ('aroma', 'Аромат', 'Scent', None, 2),
            ('texture', 'Текстура', 'Texture', None, 3),
            ('thickness', 'Толщина', 'Thickness', mm, 4),
            ('lube_type', 'Тип смазки', 'Lubricant type', None, 5),
            ('lube_volume', 'Объём смазки', 'Lubricant volume', mg, 6),
            ('shelf_life', 'Срок годности', 'Shelf life', months, 7),
            ('production', 'Производство', 'Made in', None, 8),
        ]
        for key, name_ru, name_en, unit, order in char_defs:
            obj, _ = Characteristic.objects.update_or_create(
                name_ru=name_ru,
                defaults={'name_en': name_en, 'unit': unit, 'order': order},
            )
            chars[key] = obj
        self.stdout.write(self.style.SUCCESS(f'Характеристики: {len(chars)}'))

        # ─── Регионы ───
        regions = {r.code: r for r in Region.objects.filter(is_active=True)}

        # ─── Размеры (физические) ───
        sizes_def = [
            {'name': 'M', 'order': 0},
            {'name': 'L', 'order': 1},
            {'name': 'XL', 'order': 2},
        ]

        # ─── Виды товаров ───
        # Каждый вид × упаковка (5, 17, 30) = отдельный товар
        types = [
            {
                'key': 'strawberry',
                'name_ru': 'Клубника',
                'name_en': 'Strawberry',
                'name_kk': 'Құлпынай',
                'tagline_ru': 'Сладкий аромат клубники',
                'tagline_en': 'Sweet strawberry scent',
                'badge': 'bestseller',
                'chars': {
                    'material': 'Натуральный латекс',
                    'aroma': 'Клубника',
                    'texture': 'Гладкая',
                    'thickness': '0.02',
                    'lube_type': '100% силиконовая',
                    'lube_volume': '850',
                    'shelf_life': '60',
                    'production': 'Китай',
                },
            },
            {
                'key': 'banana',
                'name_ru': 'Банан',
                'name_en': 'Banana',
                'name_kk': 'Банан',
                'tagline_ru': 'Тропический аромат банана',
                'tagline_en': 'Tropical banana scent',
                'badge': '',
                'chars': {
                    'material': 'Натуральный латекс',
                    'aroma': 'Банан',
                    'texture': 'Гладкая',
                    'thickness': '0.02',
                    'lube_type': '100% силиконовая',
                    'lube_volume': '850',
                    'shelf_life': '60',
                    'production': 'Китай',
                },
            },
            {
                'key': 'chocolate',
                'name_ru': 'Шоколад',
                'name_en': 'Chocolate',
                'name_kk': 'Шоколад',
                'tagline_ru': 'Шоколадный аромат для особых моментов',
                'tagline_en': 'Chocolate scent for special moments',
                'badge': '',
                'chars': {
                    'material': 'Натуральный латекс',
                    'aroma': 'Шоколад',
                    'texture': 'Гладкая',
                    'thickness': '0.02',
                    'lube_type': '100% силиконовая',
                    'lube_volume': '850',
                    'shelf_life': '60',
                    'production': 'Китай',
                },
            },
            {
                'key': 'classic',
                'name_ru': 'Классика',
                'name_en': 'Classic',
                'name_kk': 'Классика',
                'tagline_ru': 'Классическая надёжность',
                'tagline_en': 'Classic reliability',
                'badge': '',
                'chars': {
                    'material': 'Натуральный латекс',
                    'aroma': 'Без аромата',
                    'texture': 'Гладкая',
                    'thickness': '0.02',
                    'lube_type': '100% силиконовая',
                    'lube_volume': '850',
                    'shelf_life': '60',
                    'production': 'Китай',
                },
            },
            {
                'key': 'triple-lube',
                'name_ru': 'Тройная смазка',
                'name_en': 'Triple Lube',
                'name_kk': 'Үш еселенген майлау',
                'tagline_ru': 'Тройной объём смазки для максимального комфорта',
                'tagline_en': 'Triple lubricant for maximum comfort',
                'badge': 'new',
                'chars': {
                    'material': 'Натуральный латекс',
                    'aroma': 'Без аромата',
                    'texture': 'Гладкая',
                    'thickness': '0.02',
                    'lube_type': '100% силиконовая',
                    'lube_volume': '1200',
                    'shelf_life': '60',
                    'production': 'Китай',
                },
            },
            {
                'key': 'dotted-ribbed',
                'name_ru': 'Точечно-ребристые',
                'name_en': 'Dotted & Ribbed',
                'name_kk': 'Нүктелі-қырлы',
                'tagline_ru': 'Точки и рёбрышки для новых ощущений',
                'tagline_en': 'Dots and ribs for new sensations',
                'badge': '',
                'chars': {
                    'material': 'Натуральный латекс',
                    'aroma': 'Без аромата',
                    'texture': 'Точечно-ребристая',
                    'thickness': '0.04',
                    'lube_type': '100% силиконовая',
                    'lube_volume': '850',
                    'shelf_life': '60',
                    'production': 'Китай',
                },
            },
            {
                'key': 'cats-tongue',
                'name_ru': 'Кошачий язык',
                'name_en': "Cat's Tongue",
                'name_kk': 'Мысық тілі',
                'tagline_ru': 'Уникальная текстура для острых ощущений',
                'tagline_en': 'Unique texture for intense sensations',
                'badge': 'new',
                'chars': {
                    'material': 'Натуральный латекс',
                    'aroma': 'Без аромата',
                    'texture': 'Точечная (кошачий язык)',
                    'thickness': '0.04',
                    'lube_type': '100% силиконовая',
                    'lube_volume': '850',
                    'shelf_life': '60',
                    'production': 'Китай',
                },
            },
        ]

        packs = [
            {'qty': 5, 'suffix_ru': '5 шт', 'suffix_en': '5 pcs'},
            {'qty': 17, 'suffix_ru': '17 шт', 'suffix_en': '17 pcs'},
            {'qty': 30, 'suffix_ru': '30 шт', 'suffix_en': '30 pcs'},
        ]

        product_count = 0
        for t in types:
            key = t['key']
            char_values = t['chars']

            for pack in packs:
                qty = pack['qty']
                slug = f'{key}-{qty}'

                product, created = Product.objects.update_or_create(
                    slug=slug,
                    defaults={
                        'category': cat,
                        'name_ru': f'{t["name_ru"]} {pack["suffix_ru"]}',
                        'name_en': f'{t["name_en"]} {pack["suffix_en"]}',
                        'name_kk': f'{t["name_kk"]} {pack["suffix_ru"]}',
                        'tagline_ru': t['tagline_ru'],
                        'tagline_en': t['tagline_en'],
                        'description_ru': f'Презервативы DR.JOYS «{t["name_ru"]}» — упаковка {pack["suffix_ru"]}.',
                        'description_en': f'DR.JOYS «{t["name_en"]}» condoms — {pack["suffix_en"]} pack.',
                        'badge': t['badge'],
                        'is_active': True,
                    },
                )
                product_count += 1
                action = '+' if created else '~'
                self.stdout.write(f'  {action} {product.name_ru}')

                # Размеры M, L, XL
                for s in sizes_def:
                    sku = f'DJ-{key.upper()}-{qty}-{s["name"]}'
                    size_obj, _ = ProductSize.objects.update_or_create(
                        sku=sku,
                        defaults={
                            'product': product,
                            'name': s['name'],
                            'price': 0,
                            'order': s['order'],
                        },
                    )
                    for region in regions.values():
                        RegionPrice.objects.get_or_create(
                            size=size_obj, region=region,
                            defaults={'price': 0},
                        )
                        Stock.objects.get_or_create(
                            size=size_obj, region=region,
                            defaults={'quantity': 100},
                        )

                # Характеристики
                for char_key, value in char_values.items():
                    ProductCharacteristic.objects.update_or_create(
                        product=product,
                        characteristic=chars[char_key],
                        defaults={'value': value},
                    )

        # Итоги
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Товаров: {Product.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'Размеров (SKU): {ProductSize.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'Рег. цен: {RegionPrice.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'Остатков: {Stock.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'Характеристик: {ProductCharacteristic.objects.count()}'))
        self.stdout.write(self.style.SUCCESS('Готово! Цены = 0, заполните через admin.'))
