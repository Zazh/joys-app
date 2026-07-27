import logging
import time

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
