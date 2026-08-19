"""Общие декораторы доступа."""
from functools import wraps

from django.http import Http404


def staff_only_404(view_func):
    """Пускать только персонал, остальным — 404.

    Отличие от staff_member_required: тот редиректит на страницу входа
    в админку и тем самым выдаёт секретный ADMIN_URL любому анониму.
    Здесь служебная страница просто «не существует».
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            raise Http404
        if not (user.is_staff or getattr(user, 'is_full_staff', False)):
            raise Http404
        return view_func(request, *args, **kwargs)

    return _wrapped
