from decimal import Decimal

from django.contrib import admin
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import Category, Product, ProductSize, RegionPrice, Stock

from .admin import RegionAdmin
from .context_processors import region_context
from .middleware import RegionMiddleware
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


class RegionCacheTest(RegionTestBase):
    """PH-08: кеш middleware общий и сбрасывается сигналами.

    Каждый запрос идёт через НОВЫЙ экземпляр middleware — иначе тест прошёл бы
    и на старом словаре в памяти инстанса, ради ухода от которого задача и
    делалась.
    """

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()

    def _process(self, cookie=None):
        request = self.factory.get('/')
        if cookie is not None:
            request.COOKIES['drjoys_region'] = cookie
        RegionMiddleware(lambda req: HttpResponse())(request)
        return request

    def test_region_from_cookie_is_cached(self):
        with self.assertNumQueries(1):
            first = self._process('ru')
        with self.assertNumQueries(0):
            second = self._process('ru')

        self.assertEqual(first.region, self.region_ru)
        self.assertEqual(second.region, self.region_ru)
        self.assertFalse(second.show_region_modal)

    def test_save_invalidates_cache(self):
        """Главный тест задачи: правка региона видна следующему запросу."""
        self._process('ru')

        self.region_ru.payment_gateway = 'halyk'
        self.region_ru.save()

        self.assertEqual(self._process('ru').region.payment_gateway, 'halyk')

    def test_save_invalidates_default_region_cache(self):
        """Тот же сброс для САМОГО дефолта — у него отдельный ключ кеша.

        Ключ `region:default` отдаётся посетителю без cookie, то есть каждому,
        кто пришёл на сайт впервые. Без этого теста набор оставался зелёным,
        даже если убрать `DEFAULT_CACHE_KEY` из сигнала: правку дефолтного
        региона покупатели видели бы через 10 минут TTL (проверено мутацией,
        критик блока 3).
        """
        self._process()

        self.region_kz.payment_gateway = 'vtb'
        self.region_kz.save()

        self.assertEqual(self._process().region.payment_gateway, 'vtb')

    def test_delete_invalidates_cache(self):
        self._process('ru')

        self.region_ru.delete()

        request = self._process('ru')
        self.assertEqual(request.region, self.region_kz)
        self.assertTrue(request.show_region_modal)

    def test_default_region_is_cached(self):
        with self.assertNumQueries(1):
            self._process()
        with self.assertNumQueries(0):
            request = self._process()

        self.assertEqual(request.region, self.region_kz)

    def test_unknown_code_is_cached_by_sentinel(self):
        """Битый cookie не должен ходить в БД на каждом запросе."""
        first = self._process('zz')
        with self.assertNumQueries(0):
            second = self._process('zz')

        for request in (first, second):
            self.assertEqual(request.region, self.region_kz)
            self.assertTrue(request.show_region_modal)

    def test_oversized_code_does_not_reach_db(self):
        """Код длиннее поля и код с переводом строки — не регион и не ключ
        кеша: до БД такой cookie не доходит вовсе."""
        for junk in ('kz' * 40, 'a b', 'kz\nx'):
            with self.subTest(code=junk):
                cache.clear()
                # Единственный запрос — дефолтный регион
                with self.assertNumQueries(1):
                    request = self._process(junk)
                self.assertEqual(request.region, self.region_kz)
                self.assertTrue(request.show_region_modal)

    def test_all_regions_updates_after_save(self):
        """Вторая половина той же проблемы — список регионов в селекте."""
        request = self._process('kz')
        self.assertEqual(len(region_context(request)['all_regions']), 2)

        Region.objects.create(
            code='uz', name='Узбекистан',
            currency_code='UZS', currency_symbol='сум', order=3,
        )

        self.assertEqual(len(region_context(request)['all_regions']), 3)


class RegionAdminHookTest(RegionTestBase):
    """PH-09: сохранение активного региона заводит цены и остатки.

    `save_model` зовём напрямую: хук не использует ни request, ни form.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.category = Category.objects.create(name='Презервативы', slug='condoms')
        cls.product = Product.objects.create(
            name='DR.JOYS классические', slug='classic',
            category=cls.category, pack_quantity=5,
        )
        cls.size_m = ProductSize.objects.create(
            product=cls.product, name='M', sku='DJ-CL-M', price=Decimal('2500'),
        )
        cls.size_l = ProductSize.objects.create(
            product=cls.product, name='L', sku='DJ-CL-L', price=Decimal('2700'),
        )

    def setUp(self):
        super().setUp()
        self.region_admin = RegionAdmin(Region, admin.site)

    def _save(self, region, change=False):
        self.region_admin.save_model(
            request=None, obj=region, form=None, change=change,
        )

    def _new_region(self, is_active=True):
        return Region(
            code='uz', name='Узбекистан',
            currency_code='UZS', currency_symbol='сум',
            is_active=is_active, order=3,
        )

    def test_new_active_region_gets_prices_and_stocks(self):
        region = self._new_region()

        self._save(region)

        prices = RegionPrice.objects.filter(region=region)
        self.assertEqual(prices.count(), 2)
        self.assertEqual({p.price for p in prices}, {Decimal('0')})
        self.assertEqual(Stock.objects.filter(region=region).count(), 2)

    def test_repeated_save_does_not_overwrite_prices(self):
        region = self._new_region()
        self._save(region)
        price = RegionPrice.objects.filter(region=region).first()
        price.price = Decimal('1234')
        price.save()

        self._save(region, change=True)

        self.assertEqual(RegionPrice.objects.filter(region=region).count(), 2)
        self.assertEqual(Stock.objects.filter(region=region).count(), 2)
        price.refresh_from_db()
        self.assertEqual(price.price, Decimal('1234'))

    def test_inactive_region_creates_nothing_until_activated(self):
        region = self._new_region(is_active=False)

        self._save(region)

        self.assertFalse(RegionPrice.objects.filter(region=region).exists())
        self.assertFalse(Stock.objects.filter(region=region).exists())

        region.is_active = True
        self._save(region, change=True)

        self.assertEqual(RegionPrice.objects.filter(region=region).count(), 2)
        self.assertEqual(Stock.objects.filter(region=region).count(), 2)


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


class SetRegionNoDefaultTest(RegionTestBase):
    """Окно «дефолта нет вовсе» — вторая половина той же мины.

    PH-07 закрыл «дефолт + неактивен», но состояние «дефолта нет» остаётся
    достижимым и, больше того, **неизбежным**: constraint `unique_default_region`
    не даёт держать два дефолта сразу, поэтому смена дефолта — это ровно два
    сохранения, и между ними дефолта нет. В этом окне `SetRegionView` падал на
    `region.code` у `None` — 500 посетителю с чужим кодом региона (тот же вход,
    что у исходного бага Н-2). Найдено критиком блока 3, судьбу назначил
    владелец.
    """

    def setUp(self):
        super().setUp()
        # Первая половина легитимной смены дефолта. `update()` минует сигналы,
        # поэтому кеш чистим руками — иначе `region:default` держал бы старое
        Region.objects.filter(pk=self.region_kz.pk).update(is_default=False)
        cache.clear()

    def test_unknown_code_without_default_does_not_crash(self):
        response = self.client.post('/region/set/', {
            'region': 'zz', 'next': '/',
        })

        self.assertEqual(response.status_code, 302)
        self.assertNotIn('drjoys_region', response.cookies)

    def test_known_code_still_switches_without_default(self):
        """Самовосстановление: посетитель выбирает страну в модалке — и это
        обязано работать, пока владелец не назначил новый дефолт."""
        response = self.client.post('/region/set/', {
            'region': 'ru', 'next': '/',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.cookies['drjoys_region'].value, 'ru')


class RegionModalNoDefaultTest(RegionTestBase):
    """PP-07: в окне «ноль дефолтов» регион не выбирается за посетителя.

    До правки middleware подставлял в `request.region_code` хардкод `'kz'`
    (жил с первого коммита), и кнопка «ДА, ВСЁ ВЕРНО» модалки «подтверждала»
    регион, которого посетителю даже не показали (название гасил
    `{% if current_region %}`). Решение Р-4: оба лечения сразу — пустой
    `region_code` при `region is None` И скрытая форма подтверждения.
    """

    CONFIRM_TEXT = 'ДА, ВСЁ ВЕРНО'
    CHOOSE_TEXT = 'ВЫБРАТЬ ДРУГОЙ'

    def _drop_default(self):
        # Первая половина легитимной смены дефолта; `update()` минует сигналы,
        # поэтому кеш чистим руками (образец — SetRegionNoDefaultTest)
        Region.objects.filter(pk=self.region_kz.pk).update(is_default=False)
        cache.clear()

    def test_no_default_window_hides_confirm_button(self):
        self._drop_default()

        response = self.client.get(reverse('catalog:catalog'))

        self.assertNotContains(response, self.CONFIRM_TEXT)
        self.assertContains(response, self.CHOOSE_TEXT)
        self.assertEqual(response.context['region_code'], '')

    def test_default_alive_renders_confirm_form_with_default_code(self):
        response = self.client.get(reverse('catalog:catalog'))

        self.assertContains(response, self.CONFIRM_TEXT)
        self.assertContains(response, 'name="region" value="kz"')
        self.assertEqual(response.context['region_code'], 'kz')

    def test_middleware_region_code_is_empty_without_region(self):
        """Мутация «вернуть `'kz'`» обязана ронять этот тест."""
        self._drop_default()
        request = RequestFactory().get('/')

        RegionMiddleware(lambda req: HttpResponse())(request)

        self.assertIsNone(request.region)
        self.assertEqual(request.region_code, '')
