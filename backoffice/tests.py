"""Тесты редактора контактов в бэкофисе (docs/contact_settings.md §6)."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from backoffice.forms import TRANSLATED_FIELDS, ContactSettingsForm, ContactsPageForm
from backoffice.views.contacts import CONTACTS_PAGE_SLUG
from pages.context_processors import CONTACTS_CACHE_KEY, get_contacts
from pages.models import City, ContactSettings, OfflineStore, Page

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


def seo_payload(page, **overrides):
    """POST-данные SEO-формы страницы контактов (с префиксом seo-)."""
    data = {f'seo-{name}': getattr(page, name) or '' for name in ContactsPageForm.base_fields}
    data.update({f'seo-{k}': v for k, v in overrides.items()})
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

    def test_opens_without_cms_page(self):
        """Записи Page может не быть (свежая база) — редактор всё равно открывается."""
        self.assertFalse(Page.objects.filter(slug=CONTACTS_PAGE_SLUG).exists())
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['seo_form'])

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


class ContactsPageSeoTests(TestCase):
    """Заголовок и мета-теги страницы /contacts/ правятся в разделе «Контакты».

    Раньше это была строка в списке «Страницы» с редактором body, который шаблон
    контактов не читает (docs/contacts_page_redesign.md §8).
    """

    def setUp(self):
        cache.clear()
        self.url = reverse('backoffice:contacts')
        self.page = Page.objects.create(
            slug=CONTACTS_PAGE_SLUG, body='',
            title_ru='Контакты', title_kk='Байланыс', title_en='Contacts',
        )
        User.objects.create_user(email='manager@example.com', password='x',
                                 role=User.Role.MANAGER)
        self.client.login(email='manager@example.com', password='x')

    def test_seo_fields_rendered(self):
        html = self.client.get(self.url).content.decode()
        for name in ContactsPageForm.base_fields:
            self.assertIn(f'name="seo-{name}"', html, f'поле {name} не выводится в разметке')

    def test_saves_title_and_meta_for_all_languages(self):
        response = self.client.post(self.url, {
            **payload(),
            **seo_payload(self.page, title_kk='Байланыстар',
                          meta_title_ru='Контакты — DR.JOYS',
                          meta_title_kk='Байланыс — DR.JOYS',
                          meta_title_en='Contacts — DR.JOYS'),
        })
        self.assertRedirects(response, self.url)
        self.page.refresh_from_db()
        self.assertEqual(self.page.title_kk, 'Байланыстар')
        self.assertEqual(self.page.meta_title_en, 'Contacts — DR.JOYS')

    def test_meta_title_all_or_nothing(self):
        """Только русский мета-тег показал бы русский заголовок вкладки и на /kk/."""
        response = self.client.post(self.url, {
            **payload(),
            **seo_payload(self.page, meta_title_ru='Контакты — DR.JOYS'),
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('meta_title_kk', response.context['seo_form'].errors)
        self.page.refresh_from_db()
        # Языковые колонки modeltranslation приходят None, а не пустой строкой
        self.assertFalse(self.page.meta_title_ru)

    def test_contacts_not_saved_when_seo_invalid(self):
        """Формы две, но кнопка одна: половину сохранить нельзя."""
        response = self.client.post(self.url, {
            **payload(phone='+7 701 124 4596'),
            **seo_payload(self.page, title_kk=''),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactSettings.load().phone, '+77766103836')


class LegacyPageEditorTests(TestCase):
    """Страницы со своим разделом не редактируются общим редактором CMS-страниц."""

    def setUp(self):
        self.page = Page.objects.create(slug=CONTACTS_PAGE_SLUG, title='Контакты', body='')
        self.other = Page.objects.create(slug='about', title='О компании', body='текст')
        User.objects.create_user(email='manager@example.com', password='x',
                                 role=User.Role.MANAGER)
        self.client.login(email='manager@example.com', password='x')

    def test_hidden_from_page_list(self):
        html = self.client.get(reverse('backoffice:page_list')).content.decode()
        self.assertNotIn(reverse('backoffice:page_edit', args=[self.page.pk]), html)
        self.assertIn(reverse('backoffice:page_edit', args=[self.other.pk]), html)

    def test_direct_edit_url_redirects_to_own_section(self):
        """Ссылку убрали, но закладка на редактор могла остаться."""
        response = self.client.get(reverse('backoffice:page_edit', args=[self.page.pk]))
        self.assertRedirects(response, reverse('backoffice:contacts'))

    def test_direct_post_does_not_wipe_page(self):
        """Сохранение из общего редактора затёрло бы заголовок пустой формой."""
        response = self.client.post(reverse('backoffice:page_edit', args=[self.page.pk]), {})
        self.assertRedirects(response, reverse('backoffice:contacts'))
        self.page.refresh_from_db()
        self.assertEqual(self.page.title, 'Контакты')


class OfflineStoreCrudTests(TestCase):
    """CRUD оффлайн-точек: доступ и автозаполнение координат из ссылки 2ГИС."""

    def setUp(self):
        User.objects.create_user(email='manager@example.com', password='x',
                                 role=User.Role.MANAGER)
        self.client.login(email='manager@example.com', password='x')
        self.almaty = City.objects.create(name='Алматы')

    def payload(self, **overrides):
        data = {
            'city': str(self.almaty.pk), 'name': 'Flirtshop',
            'address': 'Ермека Серкебаева, 287Б',
            'map_url': '', 'lat': '', 'lng': '',
            'fulfillment': 'pickup_delivery', 'is_active': 'on', 'order': '0',
        }
        data.update(overrides)
        return data

    def test_anonymous_redirected_to_login(self):
        self.client.logout()
        url = reverse('backoffice:store_list')
        response = self.client.get(url)
        self.assertRedirects(response, f'/backoffice/login/?next={url}',
                             fetch_redirect_response=False)

    def test_create_takes_coords_from_2gis_url(self):
        """Пустые координаты заполняются из вставленной ссылки — тем же
        разбором, что и разовый импорт."""
        self.client.post(reverse('backoffice:store_create'), self.payload(
            map_url='https://2gis.kz/almaty/branches/1/firm/2/76.898728%2C43.204689',
        ))
        store = OfflineStore.objects.get()
        self.assertEqual((float(store.lat), float(store.lng)), (43.204689, 76.898728))

    def test_manual_coords_win_over_url(self):
        """Ручной ввод важнее ссылки: она может вести на список филиалов.
        Запятая в дроби — не ошибка, у заказчика русская раскладка."""
        self.client.post(reverse('backoffice:store_create'), self.payload(
            lat='43,5', lng='76,5',
            map_url='https://2gis.kz/almaty/firm/2/76.898728%2C43.204689',
        ))
        store = OfflineStore.objects.get()
        self.assertEqual((float(store.lat), float(store.lng)), (43.5, 76.5))

    def test_required_fields_validated(self):
        response = self.client.post(reverse('backoffice:store_create'),
                                    self.payload(city=''))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(OfflineStore.objects.count(), 0)

    def test_edit_and_delete(self):
        store = OfflineStore.objects.create(city=self.almaty, name='Shhh',
                                            address='Жамбыла, 180е')
        self.client.post(reverse('backoffice:store_edit', args=[store.pk]),
                         self.payload(name='Shhh!', address='Жамбыла, 180е'))
        store.refresh_from_db()
        self.assertEqual(store.name, 'Shhh!')
        self.client.post(reverse('backoffice:store_delete', args=[store.pk]))
        self.assertEqual(OfflineStore.objects.count(), 0)

    def test_city_bound_by_id_from_directory(self):
        """Селект шлёт id — точка привязывается к записи справочника."""
        self.client.post(reverse('backoffice:store_create'), self.payload())
        self.assertEqual(OfflineStore.objects.get().city_id, self.almaty.pk)
        self.assertEqual(City.objects.count(), 1)

    def test_city_text_no_longer_accepted(self):
        """Имя города вместо id больше не принимается: свободный ввод разводил
        «Алматы» и «алматы» по двум записям, теперь городов заводит справочник."""
        response = self.client.post(reverse('backoffice:store_create'),
                                    self.payload(city='Алматы'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(OfflineStore.objects.count(), 0)
        self.assertEqual(City.objects.count(), 1)

    def test_unknown_city_id_rejected(self):
        """Чужой id (город удалили в соседней вкладке) — ошибка, а не 500."""
        response = self.client.post(reverse('backoffice:store_create'),
                                    self.payload(city=str(self.almaty.pk + 999)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(OfflineStore.objects.count(), 0)

    def test_invalid_form_keeps_selected_city(self):
        """Ошибка валидации возвращает выбранный город в селекте."""
        response = self.client.post(reverse('backoffice:store_create'),
                                    self.payload(name=''))
        self.assertContains(response, f'value="{self.almaty.pk}" selected')

    def test_list_filter_by_city_id(self):
        """Фильтр списка ходит по id, а не по имени."""
        astana = City.objects.create(name='Астана')
        OfflineStore.objects.create(city=self.almaty, name='A', address='1')
        OfflineStore.objects.create(city=astana, name='B', address='2')
        response = self.client.get(reverse('backoffice:store_list'),
                                   {'city': str(astana.pk)})
        self.assertEqual([s.name for s in response.context['stores']], ['B'])

class CityAccessTests(TestCase):
    """Раздел городов закрыт тем же гейтом, что остальной бэкофис."""

    def setUp(self):
        self.url = reverse('backoffice:city_list')

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


class CityCrudTests(TestCase):
    """CRUD справочника городов: переводы, дубли, PROTECT на занятом городе."""

    def setUp(self):
        User.objects.create_user(email='manager@example.com', password='x',
                                 role=User.Role.MANAGER)
        self.client.login(email='manager@example.com', password='x')

    def test_create_with_three_translations(self):
        self.client.post(reverse('backoffice:city_create'), {
            'name_ru': 'Алматы', 'name_kk': 'Алматы қаласы', 'name_en': 'Almaty',
        })
        city = City.objects.get()
        self.assertEqual(
            (city.name_ru, city.name_kk, city.name_en),
            ('Алматы', 'Алматы қаласы', 'Almaty'),
        )
        # Исходная колонка синхронна с русской — по ней ищет FK и JSON-LD
        self.assertEqual(City.objects.get(name='Алматы').pk, city.pk)

    def test_empty_translations_stored_as_null(self):
        """Пустые kk/en — NULL, а не '': колонки переводов уникальны, и вторая
        пустая строка упала бы на constraint (Р-6 при этом работает на обоих)."""
        self.client.post(reverse('backoffice:city_create'),
                         {'name_ru': 'Актау', 'name_kk': '', 'name_en': ''})
        self.client.post(reverse('backoffice:city_create'),
                         {'name_ru': 'Актобе', 'name_kk': '', 'name_en': ''})
        self.assertEqual(City.objects.count(), 2)
        self.assertIsNone(City.objects.get(name_ru='Актау').name_kk)

    def test_edit_changes_translations(self):
        city = City.objects.create(name='Астана')
        self.client.post(reverse('backoffice:city_edit', args=[city.pk]), {
            'name_ru': 'Астана', 'name_kk': 'Астана қаласы', 'name_en': 'Astana',
        })
        city.refresh_from_db()
        self.assertEqual((city.name_kk, city.name_en), ('Астана қаласы', 'Astana'))

    def test_duplicate_name_in_other_case_rejected(self):
        City.objects.create(name='Алматы')
        response = self.client.post(reverse('backoffice:city_create'),
                                    {'name_ru': 'алматы'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(City.objects.count(), 1)

    def test_name_ru_required(self):
        response = self.client.post(reverse('backoffice:city_create'),
                                    {'name_ru': '', 'name_en': 'Almaty'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(City.objects.count(), 0)

    def test_empty_city_deleted(self):
        city = City.objects.create(name='Семей')
        self.client.post(reverse('backoffice:city_delete', args=[city.pk]))
        self.assertEqual(City.objects.count(), 0)

    def test_city_with_stores_protected(self):
        """Р-5: удаление города утащило бы точки — PROTECT и понятный текст."""
        city = City.objects.create(name='Алматы')
        OfflineStore.objects.create(city=city, name='Flirtshop', address='Абая, 1')
        response = self.client.post(reverse('backoffice:city_delete', args=[city.pk]),
                                    follow=True)
        self.assertEqual(City.objects.count(), 1)
        self.assertContains(response, 'привязаны точки (1 шт.)')

    def test_list_shows_store_counts(self):
        city = City.objects.create(name='Алматы')
        OfflineStore.objects.create(city=city, name='Flirtshop', address='Абая, 1')
        City.objects.create(name='Астана')
        response = self.client.get(reverse('backoffice:city_list'))
        self.assertEqual(
            {c.name_ru: c.stores_count for c in response.context['cities']},
            {'Алматы': 1, 'Астана': 0},
        )
