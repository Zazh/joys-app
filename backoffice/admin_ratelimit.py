from django.conf import settings
from django.http import HttpResponse

from backoffice.ratelimit import is_rate_limited, record_failed_attempt, clear_attempts


class AdminLoginRateLimitMiddleware:
    """Rate limiting для страницы входа в Django admin."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        admin_login_path = f'/{settings.ADMIN_URL}/login/'

        if request.path == admin_login_path and request.method == 'POST':
            limited, remaining = is_rate_limited(request, scope='admin', max_attempts=5, window=300)
            if limited:
                minutes = remaining // 60 + 1
                return HttpResponse(
                    f'Слишком много попыток входа. Попробуйте через {minutes} мин.',
                    status=429,
                    content_type='text/plain; charset=utf-8',
                )

        response = self.get_response(request)

        # После обработки — проверяем результат POST на admin login
        if request.path == admin_login_path and request.method == 'POST':
            if response.status_code == 302 and '/login/' not in response.get('Location', ''):
                # Успешный вход — редирект не на login
                clear_attempts(request, scope='admin')
            elif response.status_code == 200:
                # Неудачный вход — форма отображается снова
                record_failed_attempt(request, scope='admin', max_attempts=5, window=300)

        return response
