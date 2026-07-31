from django.conf import settings

from .base import BaseGateway, CallbackRejected, PaymentResult, PaymentStatus


def get_gateway(region):
    """Получить шлюз для региона. None если шлюз не настроен.

    None — это не ошибка, а «онлайн-оплаты нет»: заказ создаётся, уходит
    менеджеру в бэкофис, покупатель видит «Спасибо» вместо редиректа на оплату.
    """
    code = getattr(region, 'payment_gateway', '') or ''
    if not code:
        return None
    # Временный костыль до боевого токена Халыка: без флага регион с halyk
    # ведёт себя как регион без эквайринга — иначе покупатель попадал бы
    # в тестовый контур банка. Callback'и флаг не трогает (get_gateway_by_code):
    # если оплата всё же пришла, отклонять её нельзя.
    if code == 'halyk' and not settings.HALYK_ENABLED:
        return None
    return get_gateway_by_code(code)


def get_gateway_by_code(code):
    """Получить шлюз по коду. Raises KeyError если не найден."""
    from .vtb import VTBGateway
    from .halyk import HalykGateway

    registry = {
        'vtb': VTBGateway,
        'halyk': HalykGateway,
    }
    cls = registry[code]
    return cls()
