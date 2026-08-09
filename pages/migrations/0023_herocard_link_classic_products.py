import re

from django.db import migrations


def link_products(apps, schema_editor):
    """Привязать существующие карточки hero к товарам «Классика».

    На карточках изображены пачки «Классики» на 5/17/30 штук; число берём
    из имени SVG-счётчика (hero/counter/5.svg → classic-5). Если товара
    с таким slug нет — карточка остаётся без товара и ведёт в каталог.
    """
    HeroCard = apps.get_model('pages', 'HeroCard')
    Product = apps.get_model('catalog', 'Product')
    for card in HeroCard.objects.filter(product__isnull=True):
        match = re.search(r'(\d+)\D*$', card.count_image.name or '')
        if not match:
            continue
        product = Product.objects.filter(slug=f'classic-{match.group(1)}').first()
        if product:
            card.product_id = product.pk
            card.save(update_fields=['product'])


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0022_herocard_product'),
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(link_products, migrations.RunPython.noop),
    ]
