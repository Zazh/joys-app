from decimal import Decimal

from django.utils.translation import gettext as _

from catalog.models import ProductSize, RegionPrice, Product, Stock


CART_SESSION_KEY = 'cart'
FAVORITES_SESSION_KEY = 'favorites'


class Cart:
    """Корзина: БД для авторизованных, сессия для анонимов."""

    def __init__(self, request):
        self.session = request.session
        self.region = getattr(request, 'region', None)
        self.user = request.user if request.user.is_authenticated else None

        if not self.user:
            # Не пишем в сессию при чтении — иначе каждый аноним (и бот)
            # получает INSERT в django_session на первом же просмотре
            self._session_cart = self.session.get(CART_SESSION_KEY) or {}

    # ─── Мутации ───

    def add(self, size_id, qty=1):
        if self.user:
            from .models import CartItem
            obj, created = CartItem.objects.get_or_create(
                user=self.user, size_id=size_id,
                defaults={'qty': qty},
            )
            if not created:
                obj.qty += qty
                obj.save(update_fields=['qty', 'updated_at'])
        else:
            key = str(size_id)
            self._session_cart[key] = self._session_cart.get(key, 0) + qty
            self._save_session()

    def remove(self, size_id):
        if self.user:
            from .models import CartItem
            CartItem.objects.filter(user=self.user, size_id=size_id).delete()
        else:
            key = str(size_id)
            if key in self._session_cart:
                del self._session_cart[key]
                self._save_session()

    def update(self, size_id, qty):
        if self.user:
            from .models import CartItem
            if qty > 0:
                CartItem.objects.update_or_create(
                    user=self.user, size_id=size_id,
                    defaults={'qty': qty},
                )
            else:
                CartItem.objects.filter(user=self.user, size_id=size_id).delete()
        else:
            key = str(size_id)
            if qty > 0:
                self._session_cart[key] = qty
            else:
                self._session_cart.pop(key, None)
            self._save_session()

    def clear(self):
        if self.user:
            from .models import CartItem
            CartItem.objects.filter(user=self.user).delete()
        else:
            self._session_cart.clear()
            self._save_session()

    def _save_session(self):
        self.session[CART_SESSION_KEY] = self._session_cart
        self.session.modified = True

    # ─── Чтение ───

    def _get_raw(self):
        """Возвращает dict {size_id (int): qty (int)}."""
        if self.user:
            from .models import CartItem
            return {
                ci.size_id: ci.qty
                for ci in CartItem.objects.filter(user=self.user)
            }
        return {int(k): v for k, v in self._session_cart.items()}

    def __len__(self):
        if self.user:
            from .models import CartItem
            result = CartItem.objects.filter(user=self.user).values_list('qty', flat=True)
            return sum(result)
        return sum(self._session_cart.values())

    def __bool__(self):
        if self.user:
            from .models import CartItem
            return CartItem.objects.filter(user=self.user).exists()
        return bool(self._session_cart)

    def get_items(self):
        """Загрузить данные о товарах из БД с региональными ценами."""
        raw = self._get_raw()
        if not raw:
            return []

        size_ids = list(raw.keys())
        sizes = (
            ProductSize.objects
            .filter(pk__in=size_ids)
            .select_related('product', 'product__category')
            .prefetch_related('product__main_images')
        )
        sizes_map = {s.pk: s for s in sizes}

        prices_map = {}
        stocks_map = {}
        if self.region:
            region_prices = RegionPrice.objects.filter(
                size_id__in=size_ids, region=self.region,
            )
            prices_map = {rp.size_id: rp for rp in region_prices}
            stocks_map = {
                s.size_id: s
                for s in Stock.objects.filter(
                    size_id__in=size_ids, region=self.region,
                )
            }

        needs_conv = self.region and self.region.needs_conversion
        if needs_conv:
            from regions.models import convert_to_kzt

        items = []
        orphaned = []
        for size_id, qty in raw.items():
            size = sizes_map.get(size_id)
            if not size:
                orphaned.append(size_id)
                continue

            rp = prices_map.get(size_id)
            price = rp.price if rp else size.price
            old_price = (rp.old_price if rp else size.old_price) or None

            cover = size.product.get_cover_image()
            image_url = cover.thumbnail.url if cover and cover.thumbnail else (
                cover.image.url if cover else ''
            )

            item_data = {
                'size_id': size_id,
                'qty': qty,
                'name': str(size.product.name),
                'size_name': size.name,
                'sku': size.sku,
                'price': price,
                'old_price': old_price,
                'subtotal': price * qty,
                'image_url': image_url,
                'product_url': size.product.get_absolute_url(),
                'unavailable_label': self._unavailable_label(size, stocks_map),
            }

            # Двойная валюта
            if needs_conv:
                item_data['payment_price'] = convert_to_kzt(price, self.region.currency_code)
                item_data['payment_subtotal'] = convert_to_kzt(price * qty, self.region.currency_code)

            items.append(item_data)

        # Очистка orphaned items
        if orphaned and self.user:
            from .models import CartItem
            CartItem.objects.filter(user=self.user, size_id__in=orphaned).delete()

        return items

    def _unavailable_label(self, size, stocks_map):
        """Готовая переведённая метка недоступности — или '' для обычной позиции.

        Формулировки повторяют страницу товара; зеркалит guard `_create_order`:
        всё, что помечено здесь, там не оформится (и наоборот — отсутствие
        строки Stock у региона чекаут тоже валит «нет в наличии»).
        """
        if not size.product.is_active:
            return _('Снят с продажи')
        if size.coming_soon:
            return _('Скоро в продаже')
        if self.region:
            stock = stocks_map.get(size.pk)
            if stock is None or stock.available <= 0:
                return _('Нет в наличии')
        return ''

    def get_total(self):
        items = self.get_items()
        return sum(i['subtotal'] for i in items)

    def get_old_total(self):
        items = self.get_items()
        total = Decimal('0')
        for i in items:
            p = i['old_price'] or i['price']
            total += p * i['qty']
        return total

    def get_payment_total(self, total=None):
        """Итого в валюте оплаты (KZT если конвертация).

        total — уже посчитанная сумма, чтобы не перечитывать позиции из БД.
        """
        if total is None:
            total = self.get_total()
        if self.region and self.region.needs_conversion:
            from regions.models import convert_to_kzt
            return convert_to_kzt(total, self.region.currency_code)
        return total

    def get_item(self, size_id):
        """Одна позиция для ответа add/update."""
        raw = self._get_raw()
        qty = raw.get(int(size_id), 0)
        if not qty:
            return None

        size = (
            ProductSize.objects
            .filter(pk=size_id)
            .select_related('product')
            .first()
        )
        if not size:
            return None

        rp = None
        if self.region:
            rp = RegionPrice.objects.filter(
                size=size, region=self.region,
            ).first()

        price = rp.price if rp else size.price
        old_price = (rp.old_price if rp else size.old_price) or None

        return {
            'size_id': size_id,
            'qty': qty,
            'name': str(size.product.name),
            'size_name': size.name,
            'price': str(price),
            'old_price': str(old_price) if old_price else None,
            'subtotal': str(price * qty),
        }


class Favorites:
    """Избранное: БД для авторизованных, сессия для анонимов."""

    def __init__(self, request):
        self.session = request.session
        self.region = getattr(request, 'region', None)
        self.user = request.user if request.user.is_authenticated else None

        if not self.user:
            # Как и в Cart — не создаём сессию при чтении
            self._session_favs = self.session.get(FAVORITES_SESSION_KEY) or []

    def add(self, product_id):
        pid = int(product_id)
        if self.user:
            from .models import FavoriteItem
            FavoriteItem.objects.get_or_create(user=self.user, product_id=pid)
        else:
            if pid not in self._session_favs:
                self._session_favs.append(pid)
                self._save_session()

    def remove(self, product_id):
        pid = int(product_id)
        if self.user:
            from .models import FavoriteItem
            FavoriteItem.objects.filter(user=self.user, product_id=pid).delete()
        else:
            if pid in self._session_favs:
                self._session_favs.remove(pid)
                self._save_session()

    def toggle(self, product_id):
        """Toggle: add/remove. Returns True if added, False if removed."""
        pid = int(product_id)
        if self.user:
            from .models import FavoriteItem
            deleted, _ = FavoriteItem.objects.filter(user=self.user, product_id=pid).delete()
            if deleted:
                return False
            FavoriteItem.objects.create(user=self.user, product_id=pid)
            return True
        else:
            if pid in self._session_favs:
                self._session_favs.remove(pid)
                self._save_session()
                return False
            else:
                self._session_favs.append(pid)
                self._save_session()
                return True

    def _save_session(self):
        self.session[FAVORITES_SESSION_KEY] = self._session_favs
        self.session.modified = True

    def _get_product_ids(self):
        if self.user:
            from .models import FavoriteItem
            return list(
                FavoriteItem.objects
                .filter(user=self.user)
                .values_list('product_id', flat=True)
            )
        return list(self._session_favs)

    def __contains__(self, product_id):
        if self.user:
            from .models import FavoriteItem
            return FavoriteItem.objects.filter(
                user=self.user, product_id=int(product_id),
            ).exists()
        return int(product_id) in self._session_favs

    def __len__(self):
        if self.user:
            from .models import FavoriteItem
            return FavoriteItem.objects.filter(user=self.user).count()
        return len(self._session_favs)

    def __bool__(self):
        if self.user:
            from .models import FavoriteItem
            return FavoriteItem.objects.filter(user=self.user).exists()
        return bool(self._session_favs)

    def get_items(self):
        """Загрузить товары из БД с ценами первого размера."""
        product_ids = self._get_product_ids()
        if not product_ids:
            return []

        products = list(
            Product.objects
            .filter(pk__in=product_ids, is_active=True)
            .select_related('category')
            .prefetch_related('sizes', 'main_images')
        )

        # Первый размер берём из prefetch-кеша (.first() сделал бы запрос),
        # региональные цены — одним запросом на все товары
        first_sizes = {}
        for product in products:
            sizes = list(product.sizes.all())
            first_sizes[product.pk] = sizes[0] if sizes else None

        prices_map = {}
        if self.region:
            size_ids = [s.pk for s in first_sizes.values() if s]
            if size_ids:
                prices_map = {
                    rp.size_id: rp
                    for rp in RegionPrice.objects.filter(
                        size_id__in=size_ids, region=self.region,
                    )
                }

        items = []
        for product in products:
            first_size = first_sizes[product.pk]
            price = None
            old_price = None

            rp = prices_map.get(first_size.pk) if first_size else None
            if rp:
                price = rp.price
                old_price = rp.old_price
            if first_size and price is None:
                price = first_size.price
                old_price = first_size.old_price

            cover = product.get_cover_image()
            image_url = cover.thumbnail.url if cover and cover.thumbnail else (
                cover.image.url if cover else ''
            )

            item_data = {
                'product_id': product.pk,
                'name': str(product.name),
                'slug': product.slug,
                'price': price,
                'old_price': old_price or None,
                'image_url': image_url,
                'product_url': product.get_absolute_url(),
                'first_size_id': first_size.pk if first_size else None,
            }

            # Двойная валюта
            if self.region and self.region.needs_conversion and price is not None:
                from regions.models import convert_to_kzt
                item_data['payment_price'] = convert_to_kzt(price, self.region.currency_code)

            items.append(item_data)
        return items


def merge_session_to_db(request):
    """Перенести сессионную корзину/избранное в БД при логине. Идемпотентно."""
    from django.db import transaction
    from .models import CartItem, FavoriteItem

    user = request.user
    if not user.is_authenticated:
        return

    session_cart = request.session.get(CART_SESSION_KEY, {})
    session_favs = request.session.get(FAVORITES_SESSION_KEY, [])

    if not session_cart and not session_favs:
        return

    valid_size_ids = set(
        ProductSize.objects.filter(
            pk__in=[int(k) for k in session_cart.keys()],
        ).values_list('pk', flat=True)
    ) if session_cart else set()

    with transaction.atomic():
        for size_id_str, qty in session_cart.items():
            size_id = int(size_id_str)
            if size_id not in valid_size_ids:
                continue
            obj, created = CartItem.objects.get_or_create(
                user=user, size_id=size_id,
                defaults={'qty': qty},
            )
            if not created:
                obj.qty += qty
                obj.save(update_fields=['qty', 'updated_at'])

        for pid in session_favs:
            FavoriteItem.objects.get_or_create(user=user, product_id=int(pid))

    request.session.pop(CART_SESSION_KEY, None)
    request.session.pop(FAVORITES_SESSION_KEY, None)
