from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class BackofficeAccessMixin(LoginRequiredMixin):
    login_url = '/backoffice/login/'

    # Раздел доступен роли «Менеджер точек». По умолчанию нет: новая вьюха
    # бэкофиса закрыта для неё, пока её сюда не пустили явно.
    allow_store_manager = False

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_staff_role:
            raise PermissionDenied
        if request.user.is_store_manager and not self.allow_store_manager:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class SeniorStaffRequiredMixin(BackofficeAccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_staff_role:
            raise PermissionDenied
        if not request.user.is_senior_staff:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
