import logging
import time
from urllib.parse import urlparse

from django.conf import settings
from django.db import connection

logger = logging.getLogger('core.performance')

SLOW_REQUEST_MS = 500


class PerformanceMiddleware:
    """Замер времени ответа и SQL, заголовок Server-Timing, лог медленных запросов.

    Server-Timing виден в DevTools → Network → Timing и доступен из JS через
    performance.getEntriesByType('navigation')[0].serverTiming.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        sql = {'count': 0, 'time': 0.0}

        def track_sql(execute, query, params, many, context):
            started = time.monotonic()
            try:
                return execute(query, params, many, context)
            finally:
                sql['count'] += 1
                sql['time'] += time.monotonic() - started

        started = time.monotonic()
        with connection.execute_wrapper(track_sql):
            response = self.get_response(request)
        total_ms = (time.monotonic() - started) * 1000
        db_ms = sql['time'] * 1000

        response.headers['Server-Timing'] = (
            f'app;dur={total_ms:.1f}, '
            f'db;dur={db_ms:.1f};desc="{sql["count"]}q"'
        )

        if total_ms > SLOW_REQUEST_MS:
            logger.warning(
                'Slow request: %s %s → %d за %.0f мс (SQL: %d запросов, %.0f мс)',
                request.method, request.get_full_path(), response.status_code,
                total_ms, sql['count'], db_ms,
            )
        return response


def _halyk_origin():
    """Origin платёжного виджета — он подгружает свой JS и открывает iframe."""
    url = getattr(settings, 'HALYK_PAYMENT_URL', '') or ''
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        return f'{parsed.scheme}://{parsed.netloc}'
    return ''


class ContentSecurityPolicyMiddleware:
    """Content-Security-Policy — второй рубеж на случай XSS.

    По умолчанию работает в режиме Report-Only: браузер не блокирует
    ресурсы, а только пишет нарушения в консоль. Когда список источников
    отстоится, переключить CSP_REPORT_ONLY=False в .env, и политика
    начнёт действовать.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.report_only = getattr(settings, 'CSP_REPORT_ONLY', True)
        self.policy = self._build_policy()

    def _build_policy(self):
        halyk = _halyk_origin()
        scripts = [
            "'self'", "'unsafe-inline'", "'unsafe-eval'",
            'https://cdnjs.cloudflare.com',
            'https://cdn.jsdelivr.net',
            'https://www.googletagmanager.com',
        ]
        frames = [
            "'self'",
            'https://www.youtube.com',
            'https://player.vimeo.com',
        ]
        connects = ["'self'", 'https://www.google-analytics.com']
        if halyk:
            scripts.append(halyk)
            frames.append(halyk)
            connects.append(halyk)

        directives = [
            "default-src 'self'",
            'script-src ' + ' '.join(scripts),
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net",
            "font-src 'self' data: https://fonts.gstatic.com",
            "img-src 'self' data: blob: https:",
            'frame-src ' + ' '.join(frames),
            'connect-src ' + ' '.join(connects),
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
        ]
        return '; '.join(directives)

    def __call__(self, request):
        response = self.get_response(request)
        header = (
            'Content-Security-Policy-Report-Only'
            if self.report_only
            else 'Content-Security-Policy'
        )
        response.headers.setdefault(header, self.policy)
        return response
