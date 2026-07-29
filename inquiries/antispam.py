"""Антиспам публичных форм заявок: honeypot и time-trap.

Скрытые поля рендерит один тег `{% inquiry_antispam %}` — он стоит во всех
формах заявок (страница контактов, партнёрская и тату-модалки), проверка
живёт в `InquirySubmitView`. Третий рубеж — лимит заявок по IP там же.
"""
from django.core import signing

# Поле-приманка: человек его не видит, бот заполняет всё, что нашёл в форме.
# Имя нарочно мимо эвристик автозаполнения (name/email/phone/url/company) —
# иначе менеджер паролей подставил бы значение и заявка живого человека пропала
HONEYPOT_FIELD = 'subject_note'
# Подписанная сервером метка времени рендера формы — клиент её не подделает
TIMESTAMP_FIELD = 'form_ts'
# Быстрее этого форму не заполнит и очень быстрый человек
MIN_FILL_SECONDS = 3

_signer = signing.TimestampSigner(salt='inquiries.antispam')


def make_timestamp_token():
    """Метка времени рендера формы для скрытого поля."""
    return _signer.sign('inquiry')


def collect_fields(request):
    """Антиспам-поля из тела запроса.

    Клиент собирает форму одним FormData и кладёт всё в `data`, поэтому
    смотрим и в `data`, и в корень payload — вдруг клиент шлёт иначе.
    """
    payload = request.data if isinstance(request.data, dict) else {}
    nested = payload.get('data')
    if not isinstance(nested, dict):
        nested = {}
    return {**payload, **nested}


def is_honeypot_filled(fields):
    """Приманка заполнена — заявку молча выбрасываем."""
    return bool(str(fields.get(HONEYPOT_FIELD) or '').strip())


def is_too_fast(fields):
    """Форма отправлена раньше MIN_FILL_SECONDS после рендера."""
    token = fields.get(TIMESTAMP_FIELD)
    if not token:
        # Метки нет: страница из кеша браузера, старый бандл или прямой
        # вызов API — не режем, такие запросы держит лимит по IP
        return False
    try:
        # unsign отдаёт подпись, только пока она моложе max_age. Значит
        # успех = форме меньше 3 секунд = бот, а SignatureExpired =
        # прошло больше 3 секунд = живой человек
        _signer.unsign(token, max_age=MIN_FILL_SECONDS)
    except signing.SignatureExpired:
        return False
    except signing.BadSignature:
        # Подпись не наша — метку подставили руками
        return True
    return True
