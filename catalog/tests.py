"""Тесты каталога."""

from decimal import Decimal

from django.test import TestCase

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
