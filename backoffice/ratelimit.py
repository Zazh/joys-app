"""Реэкспорт общего rate-limit из core.

Логика переехала в core/ratelimit.py — ею пользуются также accounts
и inquiries. Здесь оставлены прежние имена, чтобы не трогать вызовы
в backoffice.
"""
from core.ratelimit import (  # noqa: F401
    clear_attempts,
    get_client_ip,
    hit,
    is_rate_limited,
    record_failed_attempt,
)

# Старое приватное имя — на случай внешних импортов
_get_client_ip = get_client_ip
