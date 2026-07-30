"""Тесты редактора контактов в бэкофисе (docs/contact_settings.md §6)."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from backoffice.forms import TRANSLATED_FIELDS, ContactSettingsForm
from pages.context_processors import CONTACTS_CACHE_KEY, get_contacts
from pages.models import ContactSettings

User = get_user_model()


def payload(**overrides):
    """POST-данные формы: текущие значения синглтона плюс правки теста."""
    obj = ContactSettings.load()
    data = {}
    for name in ContactSettingsForm.base_fields:
        value = getattr(obj, name)
        data[name] = '' if value is None else str(value)
    data.update(overrides)
    return data


class ContactsEditAccessTests(TestCase):
    def setUp(self):
        self.url = reverse('backoffice:contacts')

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f'/backoffice/login/?next={self.url}',
                             fetch_redirect_response=False)

    def test_customer_forbidden(self):
        User.objects.create_user(email='buyer@example.com', password='x',
                                 role=User.Role.CUSTOMER)
        self.client.login(email='buyer@example.com', password='x')
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_manager_allowed(self):
        User.objects.create_user(email='manager@example.com', password='x',
                                 role=User.Role.MANAGER)
        self.client.login(email='manager@example.com', password='x')
        self.assertEqual(self.client.get(self.url).status_code, 200)


class ContactsEditViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse('backoffice:contacts')
        User.objects.create_user(email='manager@example.com', password='x',
                                 role=User.Role.MANAGER)
        self.client.login(email='manager@example.com', password='x')

    def test_save_updates_and_drops_cache(self):
        """Правка видна на сайте сразу — кеш сброшен сигналом (§4).

        Кеш греем до сохранения: без сброса get_contacts() до 10 минут отдавал бы
        старый объект, и заказчик решил бы, что кнопка «Сохранить» не работает.
        """
        get_contacts()
        response = self.client.post(self.url, payload(
            phone='+7 701 124 4596',
            work_hours_ru='Пн–Сб 09:00–20:00',
            work_hours_kk='Дс–Сб 09:00–20:00',
            work_hours_en='Mon–Sat 09:00–20:00',
        ))
        self.assertRedirects(response, self.url)
        fresh = get_contacts()
        self.assertEqual(fresh.phone, '+77011244596')
        self.assertEqual(fresh.work_hours, 'Пн–Сб 09:00–20:00')

    def test_invalid_post_does_not_save(self):
        response = self.client.post(self.url, payload(phone=''))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactSettings.load().phone, '+77766103836')

    def test_no_required_attribute_on_inputs(self):
        """С атрибутом required «Сохранить» выглядит нерабочей кнопкой.

        Обязательные переводы лежат на скрытых табах, а невидимое поле браузер
        отчитать не может: он молча блокирует отправку, и до серверной валидации
        с form.error_tab дело не доходит. Проверено вживую — клик не делал ничего.
        """
        html = self.client.get(self.url).content.decode()
        self.assertNotIn('required', html)

    def test_every_field_is_rendered(self):
        """Поле формы, не попавшее в разметку, POST затрёт пустым — молча.

        Разметка раскладывает поля по четырём блокам руками, так что новое поле
        легко забыть.
        """
        html = self.client.get(self.url).content.decode()
        for name in ContactSettingsForm.base_fields:
            self.assertIn(f'name="{name}"', html, f'поле {name} не выводится в разметке')

    def test_form_covers_every_model_field(self):
        """Поле, добавленное в ContactSettings, должно доехать до редактора.

        Meta.fields перечислен руками: и новая колонка, и новое переводимое поле
        в pages/translation.py иначе молча остались бы только в модели, а на /kk/
        проступил бы русский (§4). Базовые переводимые поля в форме не участвуют —
        их заменяют языковые колонки.
        """
        columns = {f.name for f in ContactSettings._meta.fields} - {'id'}
        self.assertEqual(set(ContactSettingsForm.base_fields), columns - set(TRANSLATED_FIELDS))


class ContactSettingsFormTests(TestCase):
    def test_phone_canonicalized(self):
        """Как бы номер ни вбили, в колонке он E.164 — заказчик видит результат."""
        for entered, expected in (
            ('+7 (776) 610-38-36', '+77766103836'),
            ('8 776 610 38 36', '+77766103836'),
            ('77766103836', '+77766103836'),
            ('+44 20 7946 0958', '+442079460958'),
        ):
            with self.subTest(entered=entered):
                form = ContactSettingsForm(payload(phone=entered),
                                           instance=ContactSettings.load())
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.cleaned_data['phone'], expected)

    def test_bad_phone_rejected(self):
        """Опечатка и текст без цифр — ошибка, а не тихая запись в колонку.

        У WhatsApp поле необязательное, так что «уточняется» молча ушло бы пустой
        строкой; у основного телефона `to_e164` отдал бы пустоту, и заказчик видел
        бы у заполненного поля «Это поле не может быть пустым».
        """
        for name, entered in (('phone', '+7776610'), ('phone', 'уточняется'),
                              ('whatsapp_phone', 'уточняется')):
            with self.subTest(name=name, entered=entered):
                form = ContactSettingsForm(payload(**{name: entered}),
                                           instance=ContactSettings.load())
                self.assertFalse(form.is_valid())
                self.assertIn(name, form.errors)
        self.assertIn('цифр', ' '.join(form.errors['whatsapp_phone']))

    def test_whatsapp_phone_canonicalized_and_optional(self):
        form = ContactSettingsForm(payload(whatsapp_phone='8 701 124 45 96'),
                                   instance=ContactSettings.load())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['whatsapp_phone'], '+77011244596')

        form = ContactSettingsForm(payload(whatsapp_phone=''), instance=ContactSettings.load())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['whatsapp_phone'], '')

    def test_telegram_username_cleaned(self):
        """Вставили как удобно — в колонку уходит имя, ссылка не битая."""
        for entered in ('@drjoysoriginal', 'https://t.me/drjoysoriginal',
                        't.me/drjoysoriginal', ' drjoysoriginal '):
            with self.subTest(entered=entered):
                form = ContactSettingsForm(payload(telegram_username=entered),
                                           instance=ContactSettings.load())
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.cleaned_data['telegram_username'], 'drjoysoriginal')
                self.assertEqual(form.save().telegram_url, 'https://t.me/drjoysoriginal')

    def test_telegram_broken_handle_rejected(self):
        """Ссылка t.me с пробелом или кириллицей — битая, лучше ошибка в форме."""
        for entered in ('dr joys', 'дрджойс', 'др', 't.me/joinchat/AbCdEf'):
            with self.subTest(entered=entered):
                form = ContactSettingsForm(payload(telegram_username=entered),
                                           instance=ContactSettings.load())
                self.assertFalse(form.is_valid())
                self.assertIn('telegram_username', form.errors)

    def test_social_url_without_scheme_becomes_https(self):
        """Django 5 сама подставила бы http:// — небезопасная ссылка в sameAs."""
        form = ContactSettingsForm(payload(tiktok_url='tiktok.com/@drjoysoriginal'),
                                   instance=ContactSettings.load())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['tiktok_url'], 'https://tiktok.com/@drjoysoriginal')

    def test_bin_must_be_twelve_digits(self):
        """БИН печатается в футере и уходит в taxID разметки — «abc» там не место."""
        for entered in ('abc', '123', '220 140 017'):
            with self.subTest(entered=entered):
                form = ContactSettingsForm(payload(bin=entered), instance=ContactSettings.load())
                self.assertFalse(form.is_valid())
                self.assertIn('bin', form.errors)

    def test_translations_required(self):
        """Пустой kk/en не сохраняем: modeltranslation отдал бы вместо них русский."""
        form = ContactSettingsForm(payload(legal_name_kk='', address_street_en=''),
                                   instance=ContactSettings.load())
        self.assertFalse(form.is_valid())
        self.assertIn('legal_name_kk', form.errors)
        self.assertIn('address_street_en', form.errors)

    def test_work_hours_all_or_nothing(self):
        """Часы работы необязательны, но не «наполовину» — иначе фолбэк на русский."""
        form = ContactSettingsForm(payload(work_hours_ru='Пн–Пт 10:00–19:00',
                                           work_hours_kk='', work_hours_en=''),
                                   instance=ContactSettings.load())
        self.assertFalse(form.is_valid())
        self.assertIn('work_hours_kk', form.errors)
        self.assertIn('work_hours_en', form.errors)

        form = ContactSettingsForm(payload(work_hours_ru='', work_hours_kk='', work_hours_en=''),
                                   instance=ContactSettings.load())
        self.assertTrue(form.is_valid(), form.errors)

    def test_coordinates_required_and_comma_accepted(self):
        """Колонка nullable ради load(), но из формы координаты не обнулить (§3.1)."""
        form = ContactSettingsForm(payload(office_lat=''), instance=ContactSettings.load())
        self.assertFalse(form.is_valid())
        self.assertIn('office_lat', form.errors)

        # Из 2ГИС на русском координаты копируются через запятую
        form = ContactSettingsForm(payload(office_lat='51,158240', office_lng='71,435760'),
                                   instance=ContactSettings.load())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['office_lat'], Decimal('51.158240'))

    def test_coordinates_out_of_range_rejected(self):
        """Опечатка «851» вместо «51» не должна доехать до карты."""
        for name, entered in (('office_lat', '851.158240'), ('office_lng', '-181.435760')):
            with self.subTest(name=name):
                form = ContactSettingsForm(payload(**{name: entered}),
                                           instance=ContactSettings.load())
                self.assertFalse(form.is_valid())
                self.assertIn(name, form.errors)

    def test_error_tab_opens_language_with_error(self):
        form = ContactSettingsForm(payload(legal_name_en=''), instance=ContactSettings.load())
        self.assertFalse(form.is_valid())
        self.assertEqual(form.error_tab(), 'en')
