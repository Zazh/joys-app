from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .models import Region


class RegionTestBase(TestCase):
    """Общие фикстуры регионов: дефолтный kz + обычный ru.

    `cache.clear()` в `setUp` обязателен: `all_regions` в контекст-процессоре
    живёт 600 секунд, а локальный кеш общий на весь прогон (образец —
    `CheckoutRegionTest` в `orders/tests.py`).
    """

    @classmethod
    def setUpTestData(cls):
        cls.region_kz = Region.objects.create(
            code='kz', name='Казахстан',
            currency_code='KZT', currency_symbol='₸',
            payment_gateway='halyk', is_default=True, order=1,
        )
        cls.region_ru = Region.objects.create(
            code='ru', name='Россия',
            currency_code='RUB', currency_symbol='₽',
            payment_currency_code='KZT', payment_currency_symbol='₸',
            payment_gateway='vtb', order=2,
        )

    def setUp(self):
        cache.clear()


class RegionCleanTest(RegionTestBase):
    """PH-07: дефолтный регион не деактивировать.

    Исходный баг (ревью `regions`, Н-2): снятая галка «Активен» у дефолта →
    `get_default()` отдаёт None → `SetRegionView` на неизвестном коде падает
    в 500 на `region.code`.
    """

    def test_deactivating_default_region_is_rejected(self):
        self.region_kz.is_active = False

        with self.assertRaises(ValidationError):
            self.region_kz.full_clean()

    def test_deactivating_ordinary_region_is_allowed(self):
        self.region_ru.is_active = False

        self.region_ru.full_clean()  # не должно бросать

    def test_active_default_region_passes(self):
        self.region_kz.full_clean()  # не должно бросать

    def test_default_can_be_moved_in_two_saves(self):
        """Смена дефолта легитимна и идёт двумя сохранениями — clean() её
        не блокирует (условный constraint ноль дефолтов не запрещает)."""
        self.region_kz.is_default = False
        self.region_kz.full_clean()
        self.region_kz.save()

        self.region_ru.is_default = True
        self.region_ru.full_clean()
        self.region_ru.save()

        self.assertEqual(Region.get_default(), self.region_ru)


class RegionAdminChangelistTest(RegionTestBase):
    """Тот же запрет через форму админки: галки правятся прямо в списке
    (`RegionAdmin.list_editable`), и именно этот путь давал 500 одним кликом.
    """

    ERROR_TEXT = 'нельзя деактивировать'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.admin_user = User.objects.create_superuser(
            email='admin@example.com', password='admin12345',
        )

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin_user)
        self.changelist_url = reverse('admin:regions_region_changelist')

    def _changelist_post_data(self, response, inactive_pks=()):
        """Данные formset-а списка по факту отрисованных строк.

        Снятый чекбокс = отсутствующий ключ, поэтому регионы из
        `inactive_pks` просто не получают `is_active`.
        """
        rows = list(response.context['cl'].result_list)
        data = {
            'form-TOTAL_FORMS': str(len(rows)),
            'form-INITIAL_FORMS': str(len(rows)),
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': str(len(rows)),
            '_save': 'Сохранить',
        }
        for i, region in enumerate(rows):
            data[f'form-{i}-id'] = str(region.pk)
            data[f'form-{i}-order'] = str(region.order)
            if region.is_active and region.pk not in inactive_pks:
                data[f'form-{i}-is_active'] = 'on'
            if region.is_default:
                data[f'form-{i}-is_default'] = 'on'
        return data

    def test_changelist_rejects_deactivating_default(self):
        changelist = self.client.get(self.changelist_url)
        data = self._changelist_post_data(
            changelist, inactive_pks={self.region_kz.pk},
        )

        response = self.client.post(self.changelist_url, data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.ERROR_TEXT)
        self.region_kz.refresh_from_db()
        self.assertTrue(self.region_kz.is_active)

    def test_changelist_allows_deactivating_ordinary_region(self):
        changelist = self.client.get(self.changelist_url)
        data = self._changelist_post_data(
            changelist, inactive_pks={self.region_ru.pk},
        )

        response = self.client.post(self.changelist_url, data)

        self.assertEqual(response.status_code, 302)
        self.region_ru.refresh_from_db()
        self.assertFalse(self.region_ru.is_active)
        self.region_kz.refresh_from_db()
        self.assertTrue(self.region_kz.is_active)


class SetRegionUnknownCodeTest(RegionTestBase):
    """Регресс исходного сценария: чужой код региона при живом дефолте.

    Остальные тесты `SetRegionView` (переключение, проверка `next`) живут в
    `orders/tests.py::CheckoutRegionTest` — здесь только ветка отката к
    дефолту, ровно та, что падала в 500.
    """

    def test_unknown_code_falls_back_to_default(self):
        response = self.client.post('/region/set/', {
            'region': 'zz', 'next': '/',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.cookies['drjoys_region'].value, 'kz')
