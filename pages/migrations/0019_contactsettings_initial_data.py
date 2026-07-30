"""Перенос контактов компании из шаблонов в ContactSettings.

Значения — ровно те, что были захардкожены в `_contact_links.html`,
`_footer.html`, `pages/contacts.html` и `pages/jsonld.py` на 30.07.2026,
переводы — из locale/*/LC_MESSAGES/django.po. Разовый перенос, а не
идемпотентная команда: дальше эти значения правятся из бэкофиса
(docs/contact_settings.md §3.3).
"""

from django.db import migrations

CONTACTS = {
    'phone': '+77766103836',
    'whatsapp_phone': '',
    'telegram_username': 'drjoysoriginal',
    'email': 'drjoysoriginal@gmail.com',
    'instagram_url': 'https://www.instagram.com/drjoysoriginal/',
    'tiktok_url': 'https://www.tiktok.com/@drjoysoriginal',
    'youtube_url': 'https://www.youtube.com/@drjoysoriginal',
    'marketplace_url': '',
    'bin': '220140017355',
    'office_lat': '51.158240',
    'office_lng': '71.435760',

    'legal_name_ru': 'ТОО «DR JOYS»',
    'legal_name_kk': '«DR JOYS» ЖШС',
    'legal_name_en': 'DR JOYS LLP',

    'bin_label_ru': 'БИН',
    'bin_label_kk': 'БСН',
    'bin_label_en': 'BIN',

    'address_locality_ru': 'Астана',
    'address_locality_kk': 'Астана',
    'address_locality_en': 'Astana',

    'address_street_ru': 'р-н Байконыр, ул. А. Бараева, д. 13, н.п. 5',
    'address_street_kk': 'Байқоңыр ауданы, А. Бараев к-сі, 13-үй, 5-үй-жай',
    'address_street_en': 'Baikonyr district, 13 A. Barayev St, unit 5',

    'work_hours_ru': 'Пн–Пт 10:00–19:00',
    'work_hours_kk': 'Дс–Жм 10:00–19:00',
    'work_hours_en': 'Mon–Fri 10:00–19:00',
}

# Язык по умолчанию (ru) заполняет и базовые колонки: modeltranslation читает
# `legal_name`, когда перевод на активный язык пуст.
BASE_FROM_RU = ('legal_name', 'bin_label', 'address_locality', 'address_street', 'work_hours')


def create_contacts(apps, schema_editor):
    ContactSettings = apps.get_model('pages', 'ContactSettings')
    values = dict(CONTACTS)
    for field in BASE_FROM_RU:
        values[field] = CONTACTS[f'{field}_ru']
    ContactSettings.objects.update_or_create(pk=1, defaults=values)


def delete_contacts(apps, schema_editor):
    apps.get_model('pages', 'ContactSettings').objects.filter(pk=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0018_contactsettings'),
    ]

    operations = [
        migrations.RunPython(create_contacts, delete_contacts),
    ]
