from django.db import migrations


def add_lube_button(apps, schema_editor):
    """Красная кнопка «на товар» у слайда про тройную смазку.

    Ведёт на «Тройную смазку 17 шт». URL без языкового префикса —
    LocaleMiddleware сам уводит посетителя в его языковую версию.
    Из текстов убирается висячая стрелка «↗» — псевдоссылка, роль
    которой теперь играет кнопка.
    """
    FeatureSlide = apps.get_model('pages', 'FeatureSlide')
    Product = apps.get_model('catalog', 'Product')

    slide = FeatureSlide.objects.filter(title_ru__icontains='Столько смазки').first()
    product = Product.objects.filter(slug='triple-lube-17').select_related('category').first()
    if not slide or not product:
        return

    slide.button_text_ru = 'Смотреть товар'
    slide.button_text_kk = 'Тауарды көру'
    slide.button_text_en = 'View product'
    slide.button_url = f'/catalog/{product.category.slug}/{product.slug}/'
    slide.button_color = 'red'
    for lang in ('ru', 'kk', 'en'):
        field = f'text_{lang}'
        setattr(slide, field, (getattr(slide, field) or '').replace('↗', '').rstrip())
    slide.save()


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0025_featureslide_move_links_to_buttons'),
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(add_lube_button, migrations.RunPython.noop),
    ]
