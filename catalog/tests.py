"""Тесты каталога."""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from catalog.models import Category, Product, ProductSize, Stock
from regions.models import Region


class BuyStateTests(TestCase):
    """Состояние кнопки покупки: подпись, стиль и показ цены (product_detail)."""

    def setUp(self):
        self.category = Category.objects.create(name='Тест', slug='test-cat')
        self.product = Product.objects.create(
            name='Товар', slug='test-product', category=self.category, is_active=True,
        )

    def _state(self, **size_kwargs):
        ProductSize.objects.create(product=self.product, name='M', sku='SKU-M', **size_kwargs)
        response = self.client.get(self.product.get_absolute_url())
        return response.context['buy_state'], response.content.decode()

    def test_available(self):
        state, html = self._state(price=Decimal('1000'))
        self.assertEqual(state, 'available')
        self.assertNotIn('btn-cat--out', html)
        self.assertNotIn('btn-cat--soon', html)

    def test_coming_soon(self):
        state, html = self._state(price=Decimal('1000'), coming_soon=True)
        self.assertEqual(state, 'coming_soon')
        self.assertIn('btn-cat--soon', html)

    def test_no_price_is_out_of_stock(self):
        state, html = self._state(price=Decimal('0'))
        self.assertEqual(state, 'out_of_stock')
        self.assertIn('btn-cat--out', html)

    def test_zero_stock_is_out_of_stock(self):
        """Цена есть, остатка нет — раньше кнопка звала «Добавить в корзину»."""
        size = ProductSize.objects.create(product=self.product, name='L', sku='SKU-L',
                                          price=Decimal('1000'))
        # Остаток нужен именно в регионе запроса: без cookie это регион по умолчанию,
        # а по чужому региону in_stock отдаёт фолбэк «в наличии»
        region = Region.get_default() or Region.objects.create(
            code='kz', name='Казахстан', is_default=True,
        )
        Stock.objects.create(size=size, region=region, quantity=0)
        response = self.client.get(self.product.get_absolute_url())
        self.assertEqual(response.context['buy_state'], 'out_of_stock')
        self.assertIn('btn-cat--out', response.content.decode())


class CatalogCardStateTests(TestCase):
    """Карточка каталога: цена только у того, что можно купить."""

    COMING_SOON = 'Скоро в продаже'
    OUT_OF_STOCK = 'Нет в наличии'

    def setUp(self):
        self.category = Category.objects.create(name='Тест', slug='test-cat')
        self.product = Product.objects.create(
            name='Товар', slug='test-product', category=self.category, is_active=True,
        )
        self.region = Region.get_default() or Region.objects.create(
            code='kz', name='Казахстан', is_default=True,
        )

    def catalog_html(self):
        return self.client.get(reverse('catalog:catalog')).content.decode()

    def test_coming_soon_instead_of_price(self):
        """Цена у «скоро в продаже» стояла рядом с недоступной покупкой."""
        ProductSize.objects.create(product=self.product, name='M', sku='SKU-M',
                                   price=Decimal('1000'), coming_soon=True)
        html = self.catalog_html()
        self.assertIn(self.COMING_SOON, html)
        self.assertNotIn('1 000', html)

    def test_zero_stock_is_out_of_stock(self):
        """Цена есть, остатка в регионе запроса нет — «Нет в наличии»."""
        size = ProductSize.objects.create(product=self.product, name='L', sku='SKU-L',
                                          price=Decimal('1000'))
        Stock.objects.create(size=size, region=self.region, quantity=0)
        html = self.catalog_html()
        self.assertIn(self.OUT_OF_STOCK, html)
        self.assertNotIn(self.COMING_SOON, html)

    def test_available_shows_price(self):
        ProductSize.objects.create(product=self.product, name='M', sku='SKU-M',
                                   price=Decimal('1000'))
        html = self.catalog_html()
        self.assertIn('1 000', html)
        self.assertNotIn(self.COMING_SOON, html)
        self.assertNotIn(self.OUT_OF_STOCK, html)

    def test_price_of_purchasable_size_not_of_first(self):
        """Первый размер «скоро», второй покупаемый — карточка печатает цену
        второго, как default_size на странице товара."""
        ProductSize.objects.create(product=self.product, name='M', sku='SKU-M',
                                   price=Decimal('1000'), coming_soon=True, order=1)
        ProductSize.objects.create(product=self.product, name='L', sku='SKU-L',
                                   price=Decimal('2000'), order=2)
        html = self.catalog_html()
        self.assertIn('2 000', html)
        self.assertNotIn('1 000', html)
        self.assertNotIn(self.COMING_SOON, html)


class ProductHelpLinksTests(TestCase):
    """Справка на странице товара: настройки категории из бэкофиса."""

    def setUp(self):
        self.category = Category.objects.create(name='Тест', slug='help-cat')
        self.product = Product.objects.create(
            name='Товар', slug='help-product', category=self.category, is_active=True,
        )
        ProductSize.objects.create(product=self.product, name='M', sku='H-M',
                                   price=Decimal('1000'))

    def test_no_settings_no_links(self):
        """Пустые поля категории — ни гида по размеру, ни мёртвых href."""
        html = self.client.get(self.product.get_absolute_url()).content.decode()
        self.assertNotIn('Как выбрать размер?', html)
        self.assertNotIn('href=""', html)

    def test_size_guide_modal_wins_over_page(self):
        from modals.models import InteractiveModal, ModalStep
        from pages.models import Page
        modal = InteractiveModal.objects.create(slug='size-guide', title='Размер')
        ModalStep.objects.create(modal=modal, order=1, step_type='content', text='Шаг')
        page = Page.objects.create(slug='size-page', title='Размеры', body='т')
        self.category.size_guide_modal = modal
        self.category.size_guide_page = page
        self.category.save()

        html = self.client.get(self.product.get_absolute_url()).content.decode()
        self.assertIn('data-open-modal="size-guide"', html)
        self.assertIn('id="modal-size-guide"', html)
        self.assertNotIn('/size-page/', html)
        # Единственный контентный шаг — он же последний: кнопка закрытия, а не «Далее».
        # Закрытие висит на [data-modal-close] — его ловит делегированный слушатель
        # lib/modal-core.js (класс .modal-close сюда нельзя: он несёт стили крестика)
        self.assertIn('data-modal-close>Закрыть', html.replace('\n', ''))
        self.assertNotIn('data-next-step', html)

    def test_help_pages_linked_by_category(self):
        from pages.models import Page
        self.category.size_guide_page = Page.objects.create(
            slug='size-page', title='Размеры', body='т')
        self.category.usage_page = Page.objects.create(
            slug='usage', title='Инструкция', body='т')
        self.category.contraindications_page = Page.objects.create(
            slug='contra', title='Противопоказания', body='т', is_published=False)
        self.category.save()

        html = self.client.get(self.product.get_absolute_url()).content.decode()
        self.assertIn('/size-page/', html)
        self.assertIn('/usage/', html)
        # Неопубликованная страница — как пустое поле
        self.assertNotIn('/contra/', html)
