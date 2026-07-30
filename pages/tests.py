"""Тесты ContactSettings: форматирование, кеш контекст-процессора, переводы."""

from django.core.cache import cache
from django.test import TestCase
from django.utils import translation

from .context_processors import CONTACTS_CACHE_KEY, contacts
from .models import ContactSettings


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

    def test_telegram_links(self):
        self.settings.telegram_username = 'drjoysoriginal'
        self.assertEqual(self.settings.telegram_url, 'https://t.me/drjoysoriginal')
        self.assertEqual(self.settings.telegram_display, '@drjoysoriginal')

    def test_telegram_links_empty(self):
        self.settings.telegram_username = ''
        self.assertEqual(self.settings.telegram_url, '')
        self.assertEqual(self.settings.telegram_display, '')

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
