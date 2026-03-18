import logging
from decimal import Decimal
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import ProductSize, Stock
from .cart import Cart, Favorites
from .emails import send_order_created_email
from .forms import CheckoutForm
from .gateways import get_gateway, get_gateway_by_code
from .models import Order, OrderItem
from .serializers import (
    CartAddSerializer, CartRemoveSerializer, CartUpdateSerializer,
    FavoriteToggleSerializer, CheckoutSerializer, OrderSerializer,
)

logger = logging.getLogger(__name__)


# ─── Корзина ───

class CartView(APIView):
    """GET — содержимое корзины."""

    @extend_schema(summary='Получить корзину')
    def get(self, request):
        cart = Cart(request)
        items = cart.get_items()
        cart_total = Decimal('0')
        cart_old_total = Decimal('0')
        serialized = []
        for item in items:
            cart_total += item['subtotal']
            old_p = item['old_price'] or item['price']
            cart_old_total += old_p * item['qty']
            s = {
                'size_id': item['size_id'],
                'qty': item['qty'],
                'name': item['name'],
                'size_name': item['size_name'],
                'sku': item['sku'],
                'price': str(item['price']),
                'old_price': str(item['old_price']) if item['old_price'] else None,
                'subtotal': str(item['subtotal']),
                'image_url': item['image_url'],
                'product_url': item['product_url'],
            }
            if 'payment_price' in item:
                s['payment_price'] = str(item['payment_price'])
                s['payment_subtotal'] = str(item['payment_subtotal'])
            serialized.append(s)

        resp = {
            'ok': True,
            'items': serialized,
            'cart_total': str(cart_total),
            'cart_old_total': str(cart_old_total),
            'cart_count': len(cart),
        }
        payment_total = cart.get_payment_total()
        if payment_total != cart_total:
            resp['payment_total'] = str(payment_total)
        return Response(resp)


class CartAddView(APIView):
    """POST — добавить товар в корзину."""

    @extend_schema(summary='Добавить в корзину', request=CartAddSerializer)
    def post(self, request):
        serializer = CartAddSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'ok': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        size_id = serializer.validated_data['size_id']
        qty = serializer.validated_data['qty']

        if not ProductSize.objects.filter(pk=size_id).exists():
            return Response({'ok': False, 'error': 'Размер не найден'}, status=status.HTTP_404_NOT_FOUND)

        cart = Cart(request)
        cart.add(size_id, qty)

        return Response({
            'ok': True,
            'cart_count': len(cart),
            'item': cart.get_item(size_id),
        })


class CartRemoveView(APIView):
    """POST — удалить товар из корзины."""

    @extend_schema(summary='Удалить из корзины', request=CartRemoveSerializer)
    def post(self, request):
        serializer = CartRemoveSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'ok': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        cart = Cart(request)
        cart.remove(serializer.validated_data['size_id'])

        return Response({'ok': True, 'cart_count': len(cart)})


class CartUpdateView(APIView):
    """POST — обновить количество."""

    @extend_schema(summary='Обновить количество', request=CartUpdateSerializer)
    def post(self, request):
        serializer = CartUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'ok': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        size_id = serializer.validated_data['size_id']
        qty = serializer.validated_data['qty']

        cart = Cart(request)
        cart.update(size_id, qty)

        items = cart.get_items()
        cart_total = sum(i['subtotal'] for i in items)

        return Response({
            'ok': True,
            'cart_count': len(cart),
            'item': cart.get_item(size_id),
            'cart_total': str(cart_total),
        })


# ─── Избранное ───

class FavoritesView(APIView):
    """GET — список избранного."""

    @extend_schema(summary='Получить избранное')
    def get(self, request):
        favs = Favorites(request)
        items = favs.get_items()
        serialized = []
        for item in items:
            s = {
                'product_id': item['product_id'],
                'name': item['name'],
                'slug': item['slug'],
                'price': str(item['price']) if item['price'] is not None else None,
                'old_price': str(item['old_price']) if item['old_price'] is not None else None,
                'image_url': item['image_url'],
                'product_url': item['product_url'],
                'first_size_id': item['first_size_id'],
            }
            if 'payment_price' in item and item['payment_price'] is not None:
                s['payment_price'] = str(item['payment_price'])
            serialized.append(s)
        return Response({
            'ok': True,
            'items': serialized,
            'fav_count': len(favs),
        })


class FavoritesAddView(APIView):
    """POST — добавить в избранное."""

    @extend_schema(summary='Добавить в избранное', request=FavoriteToggleSerializer)
    def post(self, request):
        serializer = FavoriteToggleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'ok': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        favs = Favorites(request)
        favs.add(serializer.validated_data['product_id'])
        return Response({'ok': True, 'fav_count': len(favs)})


class FavoritesRemoveView(APIView):
    """POST — удалить из избранного."""

    @extend_schema(summary='Удалить из избранного', request=FavoriteToggleSerializer)
    def post(self, request):
        serializer = FavoriteToggleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'ok': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        favs = Favorites(request)
        favs.remove(serializer.validated_data['product_id'])
        return Response({'ok': True, 'fav_count': len(favs)})


class FavoritesToggleView(APIView):
    """POST — toggle избранного."""

    @extend_schema(summary='Toggle избранного', request=FavoriteToggleSerializer)
    def post(self, request):
        serializer = FavoriteToggleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'ok': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        favs = Favorites(request)
        added = favs.toggle(serializer.validated_data['product_id'])
        return Response({'ok': True, 'added': added, 'fav_count': len(favs)})


# ─── История заказов ───

class OrderHistoryView(APIView):
    """GET — история заказов текущего пользователя."""

    @extend_schema(summary='История заказов', responses={200: OrderSerializer(many=True)})
    def get(self, request):
        if not request.user.is_authenticated:
            return Response(
                {'ok': False, 'error': 'Требуется авторизация.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        orders = (
            Order.objects
            .filter(user=request.user)
            .exclude(status=Order.Status.EXPIRED)
            .select_related('region')
            .prefetch_related('items')
            .order_by('-created_at')
        )
        return Response({
            'ok': True,
            'orders': OrderSerializer(orders, many=True).data,
        })


# ─── Оформление заказа ───

class CheckoutView(View):
    """GET — страница оформления.
    POST — создать заказ (form или JSON API).
    """

    def get(self, request):
        cart = Cart(request)
        if not cart:
            return redirect(reverse('catalog:catalog'))

        cart_items = cart.get_items()
        cart_total = sum(i['subtotal'] for i in cart_items)
        cart_old_total = sum(
            (i['old_price'] or i['price']) * i['qty'] for i in cart_items
        )

        initial = {}
        if request.user.is_authenticated:
            user = request.user
            initial = {
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone': getattr(user, 'phone', ''),
                'email': user.email,
                'country': request.region.code if request.region else '',
            }

        form = CheckoutForm(initial=initial)

        ctx = {
            'form': form,
            'cart_items': cart_items,
            'cart_total': cart_total,
            'cart_old_total': cart_old_total,
            'is_authenticated': request.user.is_authenticated,
        }
        if request.region and request.region.needs_conversion:
            ctx['payment_total'] = cart.get_payment_total()
        return render(request, 'orders/checkout.html', ctx)

    def post(self, request):
        if 'application/json' in (request.content_type or ''):
            return self._handle_json_checkout(request)
        return self._handle_form_checkout(request)

    def _handle_form_checkout(self, request):
        cart = Cart(request)
        cart_items = cart.get_items()
        cart_total = sum(i['subtotal'] for i in cart_items)
        cart_old_total = sum(
            (i['old_price'] or i['price']) * i['qty'] for i in cart_items
        )

        def _render_with_error(form, error_message=None):
            return render(request, 'orders/checkout.html', {
                'form': form,
                'cart_items': cart_items,
                'cart_total': cart_total,
                'cart_old_total': cart_old_total,
                'is_authenticated': request.user.is_authenticated,
                'error_message': error_message,
            })

        if not request.user.is_authenticated:
            return redirect('/orders/checkout/')

        if not cart:
            return redirect(reverse('catalog:catalog'))

        form = CheckoutForm(request.POST)
        if not form.is_valid():
            return _render_with_error(form)

        region = request.region
        if not region:
            return _render_with_error(form, 'Регион не определён')

        if not cart_items:
            return _render_with_error(form, 'Товары в корзине не найдены')

        cd = form.cleaned_data
        first_name = cd['first_name']
        last_name = cd['last_name']
        phone = cd['phone']
        email = cd.get('email', '')
        city = cd['city']
        address = form.get_address()
        total = cart_total

        try:
            order = self._create_order(
                request, region, first_name, last_name, phone, email,
                city, address, total, cart_items,
            )
        except ValueError as e:
            return _render_with_error(form, str(e))

        self._update_user_profile(request.user, first_name, last_name, phone)

        payment_url = self._register_payment(request, order, cart)
        if payment_url is None:
            return _render_with_error(form, 'Ошибка платёжной системы. Попробуйте позже.')
        elif payment_url:
            return redirect(payment_url)
        else:
            cart.clear()
            send_order_created_email(order)
            return redirect(reverse(
                'orders:checkout_success',
                kwargs={'order_number': order.number},
            ))

    def _handle_json_checkout(self, request):
        """POST JSON API."""
        import json

        if not request.user.is_authenticated:
            from django.http import JsonResponse
            return JsonResponse({'ok': False, 'error': 'auth_required'}, status=401)

        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            from django.http import JsonResponse
            return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

        serializer = CheckoutSerializer(data=data)
        if not serializer.is_valid():
            from django.http import JsonResponse
            return JsonResponse({'ok': False, 'errors': serializer.errors}, status=400)

        cart = Cart(request)
        if not cart:
            from django.http import JsonResponse
            return JsonResponse({'ok': False, 'error': 'Корзина пуста'}, status=400)

        d = serializer.validated_data
        region = request.region
        if not region:
            from django.http import JsonResponse
            return JsonResponse({'ok': False, 'error': 'Регион не определён'}, status=400)

        cart_items = cart.get_items()
        if not cart_items:
            from django.http import JsonResponse
            return JsonResponse({'ok': False, 'error': 'Товары в корзине не найдены'}, status=400)

        total = sum(i['subtotal'] for i in cart_items)

        try:
            order = self._create_order(
                request, region, d['first_name'], d['last_name'], d['phone'],
                d.get('email', ''), d['city'], d['address'], total, cart_items,
            )
        except ValueError as e:
            from django.http import JsonResponse
            return JsonResponse({'ok': False, 'error': str(e)}, status=400)

        self._update_user_profile(request.user, d['first_name'], d['last_name'], d['phone'])

        payment_url = self._register_payment(request, order, cart)
        from django.http import JsonResponse
        if payment_url is None:
            return JsonResponse({
                'ok': False,
                'error': 'Ошибка платёжной системы. Попробуйте позже.',
            }, status=502)
        elif payment_url:
            return JsonResponse({
                'ok': True,
                'order_number': order.number,
                'total': str(total),
                'payment_url': payment_url,
            })
        else:
            cart.clear()
            send_order_created_email(order)
            return JsonResponse({
                'ok': True,
                'order_number': order.number,
                'total': str(total),
            })

    # ─── Общие helpers ───

    def _create_order(self, request, region, first_name, last_name,
                      phone, email, city, address, total, cart_items):
        order_kwargs = {
            'region': region,
            'user': request.user,
            'customer_name': f'{first_name} {last_name}',
            'customer_phone': phone,
            'customer_email': email or request.user.email,
            'city': city,
            'address': address,
            'expires_at': timezone.now() + timedelta(minutes=30),
        }

        if region.needs_conversion:
            from regions.models import ExchangeRate, convert_to_kzt
            payment_total = convert_to_kzt(total, region.currency_code)
            rate_obj = ExchangeRate.objects.get(currency_code=region.currency_code)
            order_kwargs['total_amount'] = payment_total
            order_kwargs['display_amount'] = total
            order_kwargs['display_currency_code'] = region.currency_code
            order_kwargs['exchange_rate_snapshot'] = rate_obj.rate / rate_obj.quant
        else:
            order_kwargs['total_amount'] = total

        with transaction.atomic():
            order = Order.objects.create(**order_kwargs)

            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    size_id=item['size_id'],
                    product_name=item['name'],
                    size_name=item['size_name'],
                    quantity=item['qty'],
                    price=item['price'],
                )

            for item in cart_items:
                try:
                    stock = Stock.objects.select_for_update().get(
                        size_id=item['size_id'], region=region,
                    )
                except Stock.DoesNotExist:
                    raise ValueError(
                        f'{item["name"]} ({item["size_name"]}) — нет в наличии'
                    )
                if stock.available < item['qty']:
                    raise ValueError(
                        f'{item["name"]} ({item["size_name"]}) — недостаточно на складе'
                    )
                stock.reserved += item['qty']
                stock.save(update_fields=['reserved', 'updated_at'])

        return order

    def _update_user_profile(self, user, first_name, last_name, phone):
        updated = []
        if first_name and not user.first_name:
            user.first_name = first_name
            updated.append('first_name')
        if last_name and not user.last_name:
            user.last_name = last_name
            updated.append('last_name')
        if phone and not getattr(user, 'phone', None):
            user.phone = phone
            updated.append('phone')
        if updated:
            user.save(update_fields=updated)

    def _register_payment(self, request, order, cart):
        region = order.region
        gateway = get_gateway(region)
        if not gateway:
            return ''

        base = settings.PAYMENT_BASE_URL or ''
        if base:
            return_url = base.rstrip('/') + '/orders/payment/return/'
            callback_url = base.rstrip('/') + f'/orders/payment/callback/{gateway.code}/'
        else:
            return_url = request.build_absolute_uri('/orders/payment/return/')
            callback_url = request.build_absolute_uri(
                f'/orders/payment/callback/{gateway.code}/'
            )

        result = gateway.create_payment(order, return_url, callback_url)

        if result.success:
            order.payment_gateway = gateway.code
            order.payment_id = result.payment_id

            if result.payment_url == '__halyk__':
                request.session['halyk_payment'] = result._payment_object
                payment_url = request.build_absolute_uri(
                    f'/orders/payment/halyk-pay/{order.number}/'
                )
            else:
                payment_url = result.payment_url

            order.payment_url = payment_url
            order.save(update_fields=[
                'payment_gateway', 'payment_id', 'payment_url',
            ])
            cart.clear()
            send_order_created_email(order)
            return payment_url

        logger.error(
            'Payment failed for order %s (%s): %s',
            order.number, gateway.code, result.error_message,
        )
        order.cancel()
        return None


class CheckoutSuccessView(View):
    def get(self, request, order_number):
        try:
            order = Order.objects.select_related('region').get(number=order_number)
        except Order.DoesNotExist:
            return redirect('/')

        if request.user.is_authenticated and order.user_id and order.user != request.user:
            return redirect('/')

        return render(request, 'orders/checkout_success.html', {
            'order': order,
            'currency_symbol': order.region.currency_symbol,
        })


# ─── Оплата (остаётся vanilla — gateway-специфичные views) ───

class PaymentReturnView(View):
    def get(self, request):
        payment_id = (
            request.GET.get('orderId')
            or request.GET.get('invoiceId', '')
        )

        if not payment_id:
            return render(request, 'orders/payment_result.html', {
                'success': False,
                'error_message': 'Некорректная ссылка',
            })

        try:
            order = Order.objects.select_related('region').get(payment_id=payment_id)
        except Order.DoesNotExist:
            return render(request, 'orders/payment_result.html', {
                'success': False,
                'error_message': 'Заказ не найден',
            })

        if order.payment_gateway and order.status == Order.Status.PENDING:
            try:
                gateway = get_gateway_by_code(order.payment_gateway)
                result = gateway.check_status(order.payment_id)
                if result.paid:
                    order.confirm_payment()
            except (KeyError, Exception) as e:
                logger.error('Payment return check failed: %s', e)

        return render(request, 'orders/payment_result.html', {
            'success': order.status == Order.Status.PAID,
            'order': order,
            'currency_symbol': order.region.currency_symbol,
        })


@method_decorator(csrf_exempt, name='dispatch')
class PaymentCallbackView(View):
    def post(self, request, gateway_code):
        return self._handle(request, gateway_code)

    def get(self, request, gateway_code):
        return self._handle(request, gateway_code)

    def _handle(self, request, gateway_code):
        try:
            gateway = get_gateway_by_code(gateway_code)
        except KeyError:
            return HttpResponse('unknown gateway', status=404)

        order, paid = gateway.process_callback(request)

        if order and paid and order.status == Order.Status.PENDING:
            order.confirm_payment()
            logger.info('Callback confirmed: order %s via %s', order.number, gateway_code)

        return HttpResponse('OK', status=200)


class HalykPayView(View):
    def get(self, request, order_number):
        payment_object = request.session.pop('halyk_payment', None)
        if not payment_object:
            return render(request, 'orders/payment_result.html', {
                'success': False,
                'error_message': 'Сессия оплаты истекла. Попробуйте оформить заказ заново.',
            })

        return render(request, 'orders/halyk_redirect.html', {
            'payment_object_json': payment_object,
            'halyk_js_url': settings.HALYK_PAYMENT_URL.rstrip('/') + '/payform/payment-api.js',
        })
