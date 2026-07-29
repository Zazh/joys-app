"""Ограничение частоты запросов по IP.

Счётчики живут в кеше (Redis на проде), ключ — scope + IP клиента.
"""
from django.conf import settings
from django.core.cache import cache

# Сколько наших прокси стоит перед Django. У нас один nginx, который
# дописывает реальный IP в конец X-Forwarded-For.
TRUSTED_PROXY_DEPTH = getattr(settings, 'TRUSTED_PROXY_DEPTH', 1)


def get_client_ip(request):
    """IP клиента с учётом того, что заголовок XFF подделывается.

    nginx настроен как `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for`,
    то есть ДОПИСЫВАЕТ реальный адрес в конец того, что прислал клиент.
    Первый элемент полностью контролируется клиентом — если брать его,
    любой лимит обходится подстановкой случайного значения в заголовок.
    Доверять можно только элементу, который добавил наш прокси.
    """
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        parts = [p.strip() for p in xff.split(',') if p.strip()]
        if parts:
            idx = max(0, len(parts) - TRUSTED_PROXY_DEPTH)
            return parts[idx]
    return request.META.get('REMOTE_ADDR', '')


def _key(scope, request, ident=None):
    return f'ratelimit:{scope}:{ident or get_client_ip(request)}'


def is_rate_limited(request, scope='login', max_attempts=5, window=300, ident=None):
    """Проверить, превышен ли лимит попыток.

    Args:
        scope: префикс ключа кеша (login, admin, register, ...)
        max_attempts: макс. попыток за окно
        window: окно в секундах (по умолчанию 5 минут)
        ident: чем считать вместо IP (например, email) — опционально

    Returns:
        (is_limited: bool, remaining_seconds: int)
    """
    key = _key(scope, request, ident)
    attempts = cache.get(key, 0)

    if attempts >= max_attempts:
        ttl = cache.ttl(key) if hasattr(cache, 'ttl') else window
        return True, ttl or window

    return False, 0


def record_attempt(request, scope='login', window=300, ident=None):
    """Засчитать обращение в счётчик лимита.

    Пара к `is_rate_limited`, когда «проверить» и «засчитать» разнесены во
    времени: у формы заявки квоту списывает только принятая заявка, а не
    каждый POST (иначе пять опечаток оставят человека без формы на час).
    """
    key = _key(scope, request, ident)
    attempts = cache.get(key, 0)
    cache.set(key, attempts + 1, window)


def record_failed_attempt(request, scope='login', max_attempts=5, window=300, ident=None):
    """Записать неудачную попытку (логины, вход в бэкофис)."""
    record_attempt(request, scope, window, ident)


def clear_attempts(request, scope='login', ident=None):
    """Сбросить счётчик после успешного действия."""
    cache.delete(_key(scope, request, ident))


def hit(request, scope, max_attempts, window, ident=None):
    """Учесть обращение и сказать, исчерпан ли лимит.

    В отличие от record_failed_attempt считает КАЖДЫЙ вызов, а не только
    неудачный — для действий, которые дорого стоят сами по себе
    (отправка письма, создание заявки).

    Returns:
        (is_limited: bool, remaining_seconds: int)
    """
    limited, remaining = is_rate_limited(request, scope, max_attempts, window, ident)
    if limited:
        return True, remaining
    record_failed_attempt(request, scope, max_attempts, window, ident)
    return False, 0
