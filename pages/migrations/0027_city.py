"""Справочник городов: модель City с колонками переводов modeltranslation.

Отдельным файлом от перевода точек на FK (0028): здесь только создание
таблицы, туда — перенос данных. Так data-шаг читается сам по себе.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0026_featureslide_lube_button'),
    ]

    operations = [
        migrations.CreateModel(
            name='City',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='Название')),
                ('name_ru', models.CharField(max_length=100, null=True, unique=True, verbose_name='Название')),
                ('name_kk', models.CharField(max_length=100, null=True, unique=True, verbose_name='Название')),
                ('name_en', models.CharField(max_length=100, null=True, unique=True, verbose_name='Название')),
            ],
            options={
                'verbose_name': 'Город',
                'verbose_name_plural': 'Города',
                'ordering': ['name'],
            },
        ),
    ]
