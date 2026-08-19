"""Город точки: текстовое поле → FK на справочник City.

Автогенерация тут не годится — она предлагает один AlterField
CharField → ForeignKey, а Postgres не приводит текст к bigint: данные бы
потерялись. Последовательность руками: nullable FK рядом со старым полем →
перенос значений → снятие старого поля и переименование FK в city.

Обратного хода у data-шага нет (noop): восстановление старых строк из
справочника технически возможно, но откат прода делается восстановлением
дампа БД — это надёжнее полуавтоматической обратной миграции.
"""

import django.db.models.deletion
from django.db import migrations, models


def link_cities(apps, schema_editor):
    """Уникальные значения старого поля → записи City, каждой точке — FK.

    Дедуп нечувствителен к регистру («Алматы» и «алматы» — один город),
    имя записи — первое встреченное написание (точки в порядке pk).
    """
    City = apps.get_model('pages', 'City')
    OfflineStore = apps.get_model('pages', 'OfflineStore')

    cities = {}
    store_ids = {}
    for pk, raw in OfflineStore.objects.order_by('pk').values_list('pk', 'city'):
        # Поле NOT NULL, но пустая строка в него влезала: без имени города
        # запись не создать, а падать посреди прод-миграции нельзя
        name = (raw or '').strip() or 'Не указан'
        key = name.lower()
        if key not in cities:
            cities[key] = City.objects.create(name=name, name_ru=name)
            store_ids[key] = []
        store_ids[key].append(pk)

    for key, city in cities.items():
        OfflineStore.objects.filter(pk__in=store_ids[key]).update(city_fk=city)


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0027_city'),
    ]

    operations = [
        # Индекс лежит на старом текстовом city — снять до его удаления
        migrations.RemoveIndex(
            model_name='offlinestore',
            name='pages_offli_is_acti_d825f2_idx',
        ),
        migrations.AddField(
            model_name='offlinestore',
            name='city_fk',
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='stores', to='pages.city', verbose_name='Город',
            ),
        ),
        migrations.RunPython(link_cities, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='offlinestore',
            name='city',
        ),
        migrations.RenameField(
            model_name='offlinestore',
            old_name='city_fk',
            new_name='city',
        ),
        migrations.AlterField(
            model_name='offlinestore',
            name='city',
            field=models.ForeignKey(
                help_text='Нет нужного города — добавьте его в разделе «Города»',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='stores', to='pages.city', verbose_name='Город',
            ),
        ),
        migrations.AlterModelOptions(
            name='offlinestore',
            options={
                'ordering': ['city__name', 'order', 'name', 'address'],
                'verbose_name': 'Оффлайн точка',
                'verbose_name_plural': 'Оффлайн точки',
            },
        ),
        migrations.AddIndex(
            model_name='offlinestore',
            index=models.Index(fields=['is_active', 'city'], name='pages_offli_is_acti_e0369a_idx'),
        ),
    ]
