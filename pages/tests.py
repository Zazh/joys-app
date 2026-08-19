"""Тесты ContactSettings: форматирование, кеш контекст-процессора, переводы,
и то, как контакты доезжают до шаблонов и до JSON-LD."""

import json
import re
from decimal import Decimal
from io import StringIO

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import translation

from .context_processors import CONTACTS_CACHE_KEY, contacts
from .management.commands.import_offline_stores import parse_partner_body
from .models import City, ContactSettings, OfflineStore, Page


class ContactSettingsFormatTests(TestCase):
    """phone_display, ссылки мессенджеров, address_line, social_links."""

    def setUp(self):
        self.settings = ContactSettings.load()

    def test_phone_display_kz(self):
        """Казахстанский номер разбивается на группы."""
        self.settings.phone = '+77766103836'
        self.assertEqual(self.settings.phone_display, '+7 776 610 38 36')

    def test_phone_display_foreign_as_is(self):
        """Иностранный номер отдаём как есть — правил его страны мы не знаем."""
        self.settings.phone = '+44 20 7946 0958'
        self.assertEqual(self.settings.phone_display, '+44 20 7946 0958')

    def test_phone_display_empty(self):
        self.settings.phone = ''
        self.assertEqual(self.settings.phone_display, '')

    def test_phone_e164(self):
        """`tel:` собирается из чистого номера, что бы ни лежало в колонке:
        пробел в `tel:` URI недопустим по RFC 3966, а до формы Сессии 3
        заказчик правит контакты в админке без всякой валидации. Иностранный
        номер тоже приводим — «как есть» обещано показу, а не ссылке.
        Без цифр ссылки нет: по этому же признаку шаблон прячет канал."""
        for stored, expected in (
            ('+7 (776) 610-38-36', '+77766103836'),
            ('+7 776 610 38 36', '+77766103836'),
            ('+77766103836', '+77766103836'),
            ('+44 20 7946 0958', '+442079460958'),
            ('', ''),
            ('   ', ''),
            ('нет', ''),
        ):
            with self.subTest(stored=stored):
                self.settings.phone = stored
                self.assertEqual(self.settings.phone_e164, expected)

    def test_whatsapp_url_falls_back_to_phone(self):
        self.settings.phone = '+77766103836'
        self.settings.whatsapp_phone = ''
        self.assertEqual(self.settings.whatsapp_url, 'https://wa.me/77766103836')

    def test_whatsapp_url_uses_own_number(self):
        self.settings.phone = '+77766103836'
        self.settings.whatsapp_phone = '+7 701 124 45 96'
        self.assertEqual(self.settings.whatsapp_url, 'https://wa.me/77011244596')

    def test_whatsapp_url_empty_without_numbers(self):
        self.settings.phone = ''
        self.settings.whatsapp_phone = ''
        self.assertEqual(self.settings.whatsapp_url, '')

    def test_whatsapp_card_and_link_agree(self):
        """Карточка и ссылка выбирают номер одинаково. Если бы карточка
        смотрела на непустую строку, а ссылка на наличие цифр, то на значении
        без цифр карточка показала бы одно, а ссылка повела на другое."""
        self.settings.phone = '+77766103836'
        for whatsapp in ('', '   ', 'уточняется'):
            with self.subTest(whatsapp=whatsapp):
                self.settings.whatsapp_phone = whatsapp
                self.assertEqual(self.settings.whatsapp_display, '+7 776 610 38 36')
                self.assertEqual(self.settings.whatsapp_url, 'https://wa.me/77766103836')

        self.settings.whatsapp_phone = '+7 701 124 45 96'
        self.assertEqual(self.settings.whatsapp_display, '+7 701 124 45 96')
        self.assertEqual(self.settings.whatsapp_url, 'https://wa.me/77011244596')

    def test_telegram_links(self):
        self.settings.telegram_username = 'drjoysoriginal'
        self.assertEqual(self.settings.telegram_url, 'https://t.me/drjoysoriginal')
        self.assertEqual(self.settings.telegram_display, '@drjoysoriginal')

    def test_telegram_links_empty(self):
        self.settings.telegram_username = ''
        self.assertEqual(self.settings.telegram_url, '')
        self.assertEqual(self.settings.telegram_display, '')

    def test_telegram_username_normalized(self):
        """Заказчик вставит как удобно — ссылка всё равно должна собраться."""
        for raw in ('@drjoysoriginal', 't.me/drjoysoriginal', 'https://t.me/drjoysoriginal',
                    'https://www.telegram.me/drjoysoriginal/', '  drjoysoriginal  '):
            with self.subTest(raw=raw):
                self.settings.telegram_username = raw
                self.assertEqual(self.settings.telegram_url, 'https://t.me/drjoysoriginal')
                self.assertEqual(self.settings.telegram_display, '@drjoysoriginal')

    def test_telegram_link_survives_dirty_column(self):
        """Чистка на чтении, поэтому ссылка цела даже если в колонку записали в обход
        save() — например `queryset.update()` или перенос базы с прода."""
        ContactSettings.objects.filter(pk=1).update(telegram_username='@drjoysoriginal')
        self.assertEqual(ContactSettings.load().telegram_url, 'https://t.me/drjoysoriginal')

    def test_telegram_broken_handle_reads_as_empty_channel(self):
        """Из имени, с которым t.me не работает, битую ссылку не собираем.

        Тот же инвариант, что у `tel:`: колонку можно заполнить в обход формы
        (`queryset.update()`, перенос базы с прода), а в футер и в `sameAs`
        уйти должна либо рабочая ссылка, либо ничего.
        """
        for raw in ('др джойс', 'dr joys', 'др', 't.me/joinchat/AbCdEf'):
            with self.subTest(raw=raw):
                ContactSettings.objects.filter(pk=1).update(telegram_username=raw)
                fresh = ContactSettings.load()
                self.assertEqual(fresh.telegram_url, '')
                self.assertEqual(fresh.telegram_display, '')
                self.assertNotIn(raw, fresh.social_links)

    def test_address_line_with_hours(self):
        self.assertEqual(
            self.settings.address_line,
            'Астана, р-н Байконыр, ул. А. Бараева, д. 13, н.п. 5, Пн–Пт 10:00–19:00',
        )

    def test_address_line_without_hours(self):
        """Часы не заполнены — строка адреса не тащит за собой лишнюю запятую."""
        self.settings.work_hours = ''
        self.assertEqual(
            self.settings.address_line,
            'Астана, р-н Байконыр, ул. А. Бараева, д. 13, н.п. 5',
        )

    def test_whatsapp_display_falls_back_to_phone(self):
        self.settings.whatsapp_phone = ''
        self.assertEqual(self.settings.whatsapp_display, '+7 776 610 38 36')

    def test_whatsapp_display_uses_own_number(self):
        """Дистрибьюторский номер показываем его же, а не основной: в карточке
        текст должен совпадать с тем, куда ведёт ссылка."""
        self.settings.whatsapp_phone = '+77011244596'
        self.assertEqual(self.settings.whatsapp_display, '+7 701 124 45 96')
        self.assertEqual(self.settings.whatsapp_url, 'https://wa.me/77011244596')

    def test_geo_returns_floats(self):
        """float, а не Decimal: json.dumps Decimal не сериализует, а в шаблоне
        Decimal печатается с незначащими нулями (51.158240)."""
        geo = self.settings.geo
        self.assertEqual(geo, {'lat': 51.15824, 'lng': 71.43576})
        self.assertIsInstance(geo['lat'], float)

    def test_geo_none_without_coords(self):
        """Одна проверка на карту и на три deep-link'а маршрутов."""
        for lat, lng in ((None, None), (None, Decimal('71.43576')), (Decimal('51.15824'), None)):
            with self.subTest(lat=lat, lng=lng):
                self.settings.office_lat, self.settings.office_lng = lat, lng
                self.assertIsNone(self.settings.geo)

    def test_social_links_skip_empty(self):
        """Пустой канал не попадает в sameAs."""
        self.settings.tiktok_url = ''
        self.assertEqual(self.settings.social_links, [
            'https://www.instagram.com/drjoysoriginal/',
            'https://www.youtube.com/@drjoysoriginal',
            'https://t.me/drjoysoriginal',
        ])

    def test_singleton_always_pk_1(self):
        """Второй объект не создаётся — save() прибивает pk=1."""
        ContactSettings(phone='+70000000000').save()
        self.assertEqual(ContactSettings.objects.count(), 1)
        self.assertEqual(ContactSettings.load().phone, '+70000000000')

    def test_singleton_not_bypassed_by_create(self):
        """objects.create() второй строки не даёт: save() прибивает pk=1, и вставка
        падает дублем ключа. Заводить контакты нужно через load() — как у
        QuizResultText, идиома синглтона в проекте одна."""
        with self.assertRaises(IntegrityError), transaction.atomic():
            ContactSettings.objects.create(phone='+70000000000')
        self.assertEqual(ContactSettings.objects.count(), 1)

    def test_required_fields_cannot_be_emptied(self):
        """Телефон, юрлицо, БИН и адрес обязательны: заказчик не обнулит их молча."""
        for field in ('phone', 'bin', 'legal_name', 'bin_label',
                      'address_locality', 'address_street'):
            with self.subTest(field=field):
                obj = ContactSettings.load()
                setattr(obj, field, '')
                with self.assertRaises(ValidationError) as cm:
                    obj.full_clean()
                self.assertIn(field, cm.exception.message_dict)

    def test_optional_fields_may_be_empty(self):
        """А необязательные — можно: канала просто не будет (§3.1)."""
        obj = ContactSettings.load()
        for field in ('whatsapp_phone', 'telegram_username', 'email', 'instagram_url',
                      'tiktok_url', 'youtube_url', 'marketplace_url', 'work_hours'):
            setattr(obj, field, '')
        obj.full_clean()  # не должно бросить


class ContactSettingsTranslationTests(TestCase):
    """Переводимые поля отдаются по активному языку."""

    def test_legal_name_and_address_by_language(self):
        expected = {
            'ru': ('ТОО «DR JOYS»', 'БИН', 'Астана', 'Пн–Пт 10:00–19:00'),
            'kk': ('«DR JOYS» ЖШС', 'БСН', 'Астана', 'Дс–Жм 10:00–19:00'),
            'en': ('DR JOYS LLP', 'BIN', 'Astana', 'Mon–Fri 10:00–19:00'),
        }
        for lang, (legal, label, city, hours) in expected.items():
            with self.subTest(lang=lang), translation.override(lang):
                obj = ContactSettings.load()
                self.assertEqual(obj.legal_name, legal)
                self.assertEqual(obj.bin_label, label)
                self.assertEqual(obj.address_locality, city)
                self.assertEqual(obj.work_hours, hours)

    def test_cached_object_translates_per_language(self):
        """Кеш общий на все языки, поэтому в нём объект, а не готовые строки:
        прогрев на ru не должен утащить русский на /kk/."""
        cache.delete(CONTACTS_CACHE_KEY)
        with translation.override('ru'):
            self.assertEqual(contacts(None)['contacts'].legal_name, 'ТОО «DR JOYS»')
        with translation.override('kk'):
            self.assertEqual(contacts(None)['contacts'].legal_name, '«DR JOYS» ЖШС')
        with translation.override('en'):
            self.assertEqual(contacts(None)['contacts'].legal_name, 'DR JOYS LLP')


class ContactSettingsCacheTests(TestCase):
    """Кеш контекст-процессора и его сброс сигналом."""

    def setUp(self):
        cache.delete(CONTACTS_CACHE_KEY)

    def test_context_processor_caches_object(self):
        contacts(None)
        self.assertIsInstance(cache.get(CONTACTS_CACHE_KEY), ContactSettings)

    def test_save_clears_cache(self):
        """Правка в бэкофисе видна сразу, а не через 10 минут."""
        contacts(None)
        obj = ContactSettings.load()
        obj.phone = '+77011244596'
        obj.save()

        self.assertIsNone(cache.get(CONTACTS_CACHE_KEY))
        self.assertEqual(contacts(None)['contacts'].phone, '+77011244596')

    def test_delete_clears_cache(self):
        """Удаление строки тоже сбрасывает кеш — иначе сайт 10 минут отдаёт удалённое."""
        contacts(None)
        ContactSettings.objects.filter(pk=1).delete()
        self.assertIsNone(cache.get(CONTACTS_CACHE_KEY))


class ContactsPageRenderTests(TestCase):
    """Страница контактов и футер: контакты доезжают из модели в разметку.

    Сессия 2 (docs/contact_settings.md §5) — переезд шаблонов и JSON-LD на модель.
    """

    @classmethod
    def setUpTestData(cls):
        cls.page = Page.objects.create(
            slug='contacts', title='Контакты', body='',
            meta_title='Контакты — DR.JOYS',
        )

    def setUp(self):
        cache.delete(CONTACTS_CACHE_KEY)

    def _get(self, lang):
        """Страница контактов на заданном языке (get_absolute_url уже с префиксом)."""
        with translation.override(lang):
            url = self.page.get_absolute_url()
        return self.client.get(url)

    def _jsonld(self, response, type_):
        """Блок JSON-LD нужного @type со страницы."""
        for raw in re.findall(
            rb'<script type="application/ld\+json">(.*?)</script>',
            response.content, re.S,
        ):
            # Разметка отдаётся с <-экранированием, json.loads его разворачивает
            data = json.loads(raw.decode('utf-8'))
            if data.get('@type') == type_:
                return data
        self.fail(f'блок JSON-LD @type={type_} на странице не найден')

    def test_coordinates_not_localized(self):
        """На /ru/ float печатается как «51,15824», и parseFloat в contacts.js даёт 51 —
        карта уезжает в степь, а три deep-link'а маршрутов ведут не туда.
        Отсюда unlocalize в шаблоне; тест не даёт запятой вернуться."""
        response = self._get('ru')
        self.assertContains(response, 'data-lat="51.15824"')
        self.assertContains(response, 'data-lng="71.43576"')
        self.assertNotContains(response, 'data-lat="51,15824"')
        # Те же координаты в deep-link'ах маршрутов — точкой, а не запятой
        self.assertContains(response, 'destination=51.15824,71.43576')

    def test_tel_href_is_clean_on_dirty_column(self):
        """Заказчик вставил номер «как удобно» — ссылка всё равно собирается
        валидной: и в футере (он на каждой странице), и в карточке канала,
        и в JSON-LD. Показываем при этом по-прежнему сгруппированный номер."""
        obj = ContactSettings.load()
        obj.phone = '+7 (776) 610-38-36'
        obj.save()

        response = self._get('ru')
        self.assertContains(response, 'href="tel:+77766103836"')
        self.assertNotContains(response, 'tel:+7 (776)')
        # Человеку — по-прежнему группами, а не слитно
        self.assertContains(response, '+7 776 610 38 36')

        org = self._jsonld(response, 'ContactPage')['mainEntity']
        self.assertEqual(org['telephone'], '+77766103836')
        self.assertEqual(org['contactPoint']['telephone'], '+77766103836')
        self.assertEqual(self._jsonld(response, 'Organization')['telephone'],
                         '+77766103836')

    def test_footer_legal_line_from_model(self):
        """Юрлицо и подпись БИН переводятся: на /kk/ не проступает русский."""
        response = self._get('kk')
        self.assertContains(response, '«DR JOYS» ЖШС')
        self.assertContains(response, 'БСН')
        self.assertNotContains(response, 'ТОО «DR JOYS»')

    def test_jsonld_uses_model_values(self):
        response = self._get('en')
        org = self._jsonld(response, 'ContactPage')['mainEntity']

        self.assertEqual(org['legalName'], 'DR JOYS LLP')
        self.assertEqual(org['telephone'], '+77766103836')
        self.assertEqual(org['taxID'], '220140017355')
        self.assertEqual(org['identifier']['name'], 'BIN')
        self.assertEqual(org['address']['addressLocality'], 'Astana')
        self.assertEqual(org['location']['geo']['latitude'], 51.15824)
        self.assertIn('https://t.me/drjoysoriginal', org['sameAs'])

    def test_jsonld_organization_id_shared_with_global_block(self):
        """@id общий — иначе парсер сочтёт развёрнутый и глобальный блок
        двумя разными компаниями."""
        response = self._get('ru')
        page_org = self._jsonld(response, 'ContactPage')['mainEntity']
        global_org = self._jsonld(response, 'Organization')
        self.assertEqual(page_org['@id'], global_org['@id'])
        # Глобальный блок есть на каждой странице: телефон и sameAs в нём, реквизитов нет
        self.assertEqual(global_org['telephone'], '+77766103836')
        self.assertNotIn('address', global_org)
        self.assertNotIn('taxID', global_org)

    def test_empty_channel_disappears_everywhere(self):
        """Пустой канал не рисуем ни иконкой, ни карточкой, ни пустой строкой в sameAs."""
        obj = ContactSettings.load()
        obj.tiktok_url = ''
        obj.email = ''
        obj.save()

        response = self._get('ru')
        self.assertNotContains(response, 'tiktok.com')
        self.assertNotContains(response, 'mailto:')

        org = self._jsonld(response, 'ContactPage')['mainEntity']
        self.assertNotIn('email', org)
        self.assertNotIn('email', org['contactPoint'])
        self.assertNotIn('', org['sameAs'])
        self.assertTrue(all('tiktok' not in link for link in org['sameAs']))

    def test_no_coordinates_hides_map_data_and_routes(self):
        """Без координат маршруты не рисуем, geo в разметку не уходит,
        а фолбэк с адресом остаётся — карта и так подставляет его без JS."""
        obj = ContactSettings.load()
        obj.office_lat = obj.office_lng = None
        obj.save()

        response = self._get('ru')
        self.assertNotContains(response, 'data-lat')
        self.assertNotContains(response, 'route-link')
        self.assertContains(response, 'map-fallback')
        self.assertContains(response, 'р-н Байконыр')

        location = self._jsonld(response, 'ContactPage')['mainEntity']['location']
        self.assertNotIn('geo', location)


class OfflineStoreCoordsTests(TestCase):
    """coords_from_2gis — единственный разбор ссылок 2ГИС: им пользуются
    и разовый импорт, и форма бэкофиса."""

    def test_point_in_path_wins_over_center(self):
        """Пара в пути карточки — сама точка; центр карты из m= игнорируется."""
        url = ('https://2gis.kz/almaty/branches/1/firm/2/76.898728%2C43.204689'
               '?m=76.893175%2C43.218359%2F12')
        self.assertEqual(OfflineStore.coords_from_2gis(url), (43.204689, 76.898728))

    def test_center_taken_only_at_close_zoom(self):
        """m= с крупным зумом центрован на точке, с мелким — это центр города."""
        close = 'https://2gis.kz/almaty/firm/1?m=76.936323%2C43.259541%2F16'
        self.assertEqual(OfflineStore.coords_from_2gis(close), (43.259541, 76.936323))
        far = 'https://2gis.kz/astana/branches/1/firm/2?m=71.443112%2C51.129661%2F11'
        self.assertIsNone(OfflineStore.coords_from_2gis(far))

    def test_no_coords_in_url(self):
        """Ссылки /geo/ и /inside/ координат не несут — None, а не выдумка."""
        self.assertIsNone(OfflineStore.coords_from_2gis('https://2gis.kz/atyrau/geo/700000010'))
        self.assertIsNone(OfflineStore.coords_from_2gis(''))

    def test_pair_outside_region_rejected(self):
        """Числа, не похожие на координаты наших краёв, точкой не считаются."""
        self.assertIsNone(OfflineStore.coords_from_2gis('https://2gis.kz/x/firm/1/10.5%2C120.5'))

    def test_kg_domain(self):
        """Бишкек живёт на 2gis.kg — разбор не привязан к домену."""
        url = 'https://2gis.kg/bishkek/firm/70000001077196217/74.599509%2C42.872003'
        self.assertEqual(OfflineStore.coords_from_2gis(url), (42.872003, 74.599509))


class CityModelTests(TestCase):
    """Справочник городов: печать имени и уникальность названия."""

    def test_str_is_name(self):
        """__str__ точки печатает город через City — «Flirtshop — Алматы, …»."""
        city = City.objects.create(name='Алматы')
        self.assertEqual(str(city), 'Алматы')
        store = OfflineStore.objects.create(
            city=city, name='Flirtshop', address='Ермека Серкебаева, 287Б')
        self.assertEqual(str(store), 'Flirtshop — Алматы, Ермека Серкебаева, 287Б')

    def test_name_is_unique(self):
        """Два города с одним названием — два одинаковых чипа на /partners/."""
        City.objects.create(name='Алматы')
        with self.assertRaises(IntegrityError), transaction.atomic():
            City.objects.create(name='Алматы')

    def test_empty_translation_falls_back_to_russian(self):
        """Р-6: незаполненный перевод не прячет город — отдаётся русское имя."""
        city = City.objects.create(name='Алматы')
        city.name_kk = 'Алматы қаласы'
        city.save()
        with translation.override('kk'):
            self.assertEqual(City.objects.get(pk=city.pk).name, 'Алматы қаласы')
        with translation.override('en'):
            self.assertEqual(City.objects.get(pk=city.pk).name, 'Алматы')


PARTNER_BODY_SAMPLE = '''
<h3><strong>Адреса наших партнеров</strong></h3>
<h3><strong>Алматы:</strong></h3>
<p><strong><em>Самовывоз и доставка:</em><br></strong></p>
<table><tbody><tr><td><strong>Flirtshop</strong></td></tr>
<tr><td><ul>
<li><a href="https://2gis.kz/almaty/branches/1/firm/2/76.898728%2C43.204689?m=76.893175%2C43.218359%2F12">Ермека Серкебаева, 287Б</a></li>
</ul></td></tr></tbody></table>
<p><br><strong><em>Только самовывоз:</em></strong><br><br><strong>EliteFuel</strong></p>
<ul><li><a href="https://2gis.kz/almaty/firm/3?m=76.937769%2C43.218734%2F16">Зеина Шашкина, 29/1</a></li></ul>
<h3>АКТАУ:</h3>
<p><strong><em>Самовывоз и доставка:</em><br><br>Flirtshop<br></strong></p>
<ul><li><strong><a href="https://2gis.kz/aktau/search/f/firm/4/51.161956%2C43.642168?m=51.168271%2C43.635705%2F11">5 мкр-н,&nbsp;дом 7</a></strong></li></ul>
'''


class ImportOfflineStoresTests(TestCase):
    """Парсер body страницы partners и сама команда импорта."""

    def test_parse_partner_body(self):
        """Города по <h3> с двоеточием, режим по <em>, магазин остатком <strong>,
        адрес ссылкой — в том числе вложенной в <strong> (случай Актау)."""
        points = parse_partner_body(PARTNER_BODY_SAMPLE)
        self.assertEqual(
            [(p['city'], p['name'], p['address'], p['fulfillment']) for p in points],
            [
                ('Алматы', 'Flirtshop', 'Ермека Серкебаева, 287Б',
                 OfflineStore.Fulfillment.PICKUP_DELIVERY),
                ('Алматы', 'EliteFuel', 'Зеина Шашкина, 29/1',
                 OfflineStore.Fulfillment.PICKUP),
                # Новый город сбрасывает режим «только самовывоз»
                ('Актау', 'Flirtshop', '5 мкр-н, дом 7',
                 OfflineStore.Fulfillment.PICKUP_DELIVERY),
            ],
        )

    def test_command_imports_with_coords(self):
        Page.objects.create(slug='partners', title='Оффлайн магазины',
                            body=PARTNER_BODY_SAMPLE)
        call_command('import_offline_stores', stdout=StringIO())
        self.assertEqual(OfflineStore.objects.count(), 3)
        store = OfflineStore.objects.get(address='Ермека Серкебаева, 287Б')
        self.assertEqual((float(store.lat), float(store.lng)), (43.204689, 76.898728))
        # Города импорт заводит сам — по одной записи на <h3>, не по точке
        self.assertEqual(store.city.name, 'Алматы')
        self.assertEqual(
            sorted(City.objects.values_list('name', flat=True)), ['Актау', 'Алматы'])

    def test_command_refuses_second_run_without_replace(self):
        """Повторный запуск затёр бы правки бэкофиса — без --replace отказ."""
        Page.objects.create(slug='partners', title='Оффлайн магазины',
                            body=PARTNER_BODY_SAMPLE)
        call_command('import_offline_stores', stdout=StringIO())
        with self.assertRaises(CommandError):
            call_command('import_offline_stores', stdout=StringIO())
        call_command('import_offline_stores', '--replace', stdout=StringIO())
        self.assertEqual(OfflineStore.objects.count(), 3)


class PartnersPageTests(TestCase):
    """Страница /partners/: свой шаблон, группировка по городам, JSON-LD."""

    @classmethod
    def setUpTestData(cls):
        cls.page = Page.objects.create(slug='partners', title='Оффлайн магазины', body='')
        cls.almaty = City.objects.create(name='Алматы')
        cls.atyrau = City.objects.create(name='Атырау')
        cls.astana = City.objects.create(name='Астана')
        OfflineStore.objects.create(
            city=cls.almaty, name='Flirtshop', address='Ермека Серкебаева, 287Б',
            lat=Decimal('43.204689'), lng=Decimal('76.898728'),
            map_url='https://2gis.kz/almaty/firm/2',
        )
        OfflineStore.objects.create(
            city=cls.almaty, name='Joys Toys', address='Байтурсынова, 169',
            lat=Decimal('43.231812'), lng=Decimal('76.933591'),
        )
        # Без координат: в списке есть, на карте нет, geo в JSON-LD не уходит
        OfflineStore.objects.create(city=cls.atyrau, name='LOVE MARKET', address='Абая, 131')
        OfflineStore.objects.create(
            city=cls.astana, name='Скрытая', address='Никуда, 1', is_active=False,
        )

    def _get(self, lang='ru'):
        with translation.override(lang):
            url = self.page.get_absolute_url()
        return self.client.get(url)

    def _jsonld(self, response, type_):
        for raw in re.findall(
            rb'<script type="application/ld\+json">(.*?)</script>',
            response.content, re.S,
        ):
            data = json.loads(raw.decode('utf-8'))
            if data.get('@type') == type_:
                return data
        self.fail(f'блок JSON-LD @type={type_} на странице не найден')

    def test_uses_partners_template(self):
        response = self._get()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pages/partners.html')

    def test_city_groups_ordered_by_count_and_skip_inactive(self):
        """Больше точек — выше чип; выключенная точка не попадает никуда."""
        response = self._get()
        groups = response.context['city_groups']
        self.assertEqual([g['name'] for g in groups], ['Алматы', 'Атырау'])
        self.assertEqual(groups[0]['count'], 2)
        ids = {s['id'] for s in response.context['stores_json']}
        self.assertNotIn(
            OfflineStore.objects.get(name='Скрытая').pk, ids,
        )

    def test_stores_json_carries_map_data(self):
        """JS собирает карту из json_script: координаты числа, у точки без
        координат — null, а не отсутствующий ключ."""
        response = self._get()
        by_name = {s['name']: s for s in response.context['stores_json']}
        self.assertEqual(by_name['Flirtshop']['lat'], 43.204689)
        self.assertIsNone(by_name['LOVE MARKET']['lat'])
        self.assertContains(response, 'id="storesData"')

    def test_jsonld_itemlist_of_stores(self):
        response = self._get()
        block = self._jsonld(response, 'WebPage')
        items = block['mainEntity']['itemListElement']
        self.assertEqual(block['mainEntity']['numberOfItems'], 3)
        first = items[0]['item']
        self.assertEqual(first['@type'], 'Store')
        self.assertEqual(first['address']['addressLocality'], 'Алматы')
        self.assertEqual(first['geo']['latitude'], 43.204689)
        # Точка без координат — без geo, а не с нулями
        no_geo = [i['item'] for i in items if i['item']['name'] == 'LOVE MARKET'][0]
        self.assertNotIn('geo', no_geo)

    def test_meta_description_fallback(self):
        """body шаблон не читает — сниппет собирается из фолбэка вьюхи."""
        self.assertContains(self._get(), 'Оффлайн магазины с товарами DR.JOYS')
