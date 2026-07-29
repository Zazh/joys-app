"""Проверка CSRF внутри DRF-вьюх.

`APIView.as_view()` помечает вьюху `csrf_exempt`, поэтому `CsrfViewMiddleware`
её пропускает, а `SessionAuthentication` проверяет токен только у авторизованных.
Для публичных POST-эндпоинтов (форма заявки) это значит «проверки нет вовсе» —
любой сторонний сайт может слать запросы браузером посетителя.

Берём готовый `CSRFCheck` из DRF (тот же класс, что в `SessionAuthentication`):
он отдаёт причину отказа вместо HTML-страницы 403, а вьюха превращает её в JSON.
"""
from rest_framework.authentication import CSRFCheck


def csrf_failure_reason(request):
    """None, если CSRF-токен на месте; иначе строка с причиной отказа."""
    # DRF Request проксирует атрибуты, но middleware ждёт настоящий HttpRequest.
    # process_request звать не нужно: секрет из куки достаёт сам process_view
    http_request = getattr(request, '_request', request)
    return CSRFCheck(lambda r: None).process_view(http_request, None, (), {})
