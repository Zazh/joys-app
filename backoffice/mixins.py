from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class BackofficeAccessMixin(LoginRequiredMixin):
    """Базовый гейт бэкофиса: пускает штатные роли, дальше решают два флага.

    Супер-менеджер и владелец проходят всегда. «Менеджеру точек» раздел закрыт,
    пока его не пустили явно (`allow_store_manager`), обычному менеджеру —
    открыт, пока не закрыли (`allow_manager`, Р-9). Оба флага живут здесь, а
    наследники ниже только выставляют их — второго места с проверкой ролей в
    бэкофисе быть не должно.
    """

    login_url = '/backoffice/login/'

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
    """Раздел только для супер-менеджера и владельца."""

    allow_store_manager = False
    allow_manager = False


class StoreManagerSectionMixin(BackofficeAccessMixin):
    """Раздел «Менеджера точек»: он и senior, обычному менеджеру — 403 (Р-9)."""

    allow_store_manager = True
    allow_manager = False
