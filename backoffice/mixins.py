from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class BackofficeAccessMixin(LoginRequiredMixin):
    login_url = '/backoffice/login/'

    # Кому раздел открыт помимо senior (супер-менеджер и владелец видят всё).
    # «Менеджеру точек» по умолчанию нет: новая вьюха закрыта для него, пока
    # его не пустили явно. Обычному менеджеру по умолчанию да — разделы, что
    # ушли к senior по Р-9, стоят на SeniorStaffRequiredMixin.
    allow_store_manager = False
    allow_manager = True

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        user = request.user
        if not user.is_staff_role:
            raise PermissionDenied
        if user.is_store_manager:
            if not self.allow_store_manager:
                raise PermissionDenied
        elif not self.allow_manager and not user.is_senior_staff:
            # остались обычный менеджер и senior; senior проходит всегда
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
