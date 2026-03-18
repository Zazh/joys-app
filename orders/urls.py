from django.urls import path

from . import views

app_name = 'orders'

urlpatterns = [
    # Корзина
    path('cart/', views.CartView.as_view(), name='cart'),
    path('cart/add/', views.CartAddView.as_view(), name='cart_add'),
    path('cart/remove/', views.CartRemoveView.as_view(), name='cart_remove'),
    path('cart/update/', views.CartUpdateView.as_view(), name='cart_update'),
    # Избранное
    path('favorites/', views.FavoritesView.as_view(), name='favorites'),
    path('favorites/add/', views.FavoritesAddView.as_view(), name='favorites_add'),
    path('favorites/remove/', views.FavoritesRemoveView.as_view(), name='favorites_remove'),
    path('favorites/toggle/', views.FavoritesToggleView.as_view(), name='favorites_toggle'),
    # История заказов
    path('history/', views.OrderHistoryView.as_view(), name='order_history'),
    # Оформление заказа
    path('checkout/', views.CheckoutView.as_view(), name='checkout'),
    path('checkout/success/<str:order_number>/', views.CheckoutSuccessView.as_view(), name='checkout_success'),
    # Оплата
    path('payment/return/', views.PaymentReturnView.as_view(), name='payment_return'),
    path('payment/callback/<str:gateway_code>/', views.PaymentCallbackView.as_view(), name='payment_callback'),
    path('payment/halyk-pay/<str:order_number>/', views.HalykPayView.as_view(), name='halyk_pay'),
]
