from .base import BaseGateway, PaymentResult, PaymentStatus


def get_gateway(region):
    """Получить шлюз для региона. None если шлюз не настроен."""
    code = getattr(region, 'payment_gateway', '') or ''
    if not code:
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
