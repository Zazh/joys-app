from django.core.cache import cache


def _get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def is_rate_limited(request, scope='login', max_attempts=5, window=300):
    """Проверить, превышен ли лимит попыток.

    Args:
        scope: префикс ключа кеша (login, admin)
        max_attempts: макс. попыток за окно
        window: окно в секундах (по умолчанию 5 минут)

    Returns:
        (is_limited: bool, remaining_seconds: int)
    """
    ip = _get_client_ip(request)
    key = f'ratelimit:{scope}:{ip}'
    attempts = cache.get(key, 0)

    if attempts >= max_attempts:
        ttl = cache.ttl(key) if hasattr(cache, 'ttl') else window
        return True, ttl

    return False, 0


def record_failed_attempt(request, scope='login', max_attempts=5, window=300):
    """Записать неудачную попытку входа."""
    ip = _get_client_ip(request)
    key = f'ratelimit:{scope}:{ip}'
    attempts = cache.get(key, 0)
    cache.set(key, attempts + 1, window)


def clear_attempts(request, scope='login'):
    """Сбросить счётчик после успешного входа."""
    ip = _get_client_ip(request)
    key = f'ratelimit:{scope}:{ip}'
    cache.delete(key)
