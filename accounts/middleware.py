from django.utils import timezone


class TrackUserActivityMiddleware:
    """Обновляет last_ip и last_user_agent для авторизованных пользователей (раз в 5 мин)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            now = timezone.now()
            last = user.last_login
            if not last or (now - last).total_seconds() > 300:
                ip = self._get_ip(request)
                ua = request.META.get('HTTP_USER_AGENT', '')[:300]
                user.last_login = now
                user.last_ip = ip
                user.last_user_agent = ua
                user.save(update_fields=['last_login', 'last_ip', 'last_user_agent'])
        return response

    @staticmethod
    def _get_ip(request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
