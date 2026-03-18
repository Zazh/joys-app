from .cart import Cart, Favorites


def cart_context(request):
    cart = Cart(request)
    favs = Favorites(request)
    return {
        'cart_count': len(cart),
        'fav_count': len(favs),
    }
