from django.utils.functional import SimpleLazyObject

from .cart import Cart, Favorites


def cart_context(request):
    # Лениво: SQL-запросы уходят только если шаблон реально выводит счётчики
    return {
        'cart_count': SimpleLazyObject(lambda: len(Cart(request))),
        'fav_count': SimpleLazyObject(lambda: len(Favorites(request))),
    }
