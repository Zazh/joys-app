from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class BackofficeAccessMixin(LoginRequiredMixin):
    login_url = '/backoffice/login/'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_staff_role:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class SeniorStaffRequiredMixin(BackofficeAccessMixin):
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if hasattr(response, 'status_code') and response.status_code in (302, 403):
            return response
        if not request.user.is_senior_staff:
            raise PermissionDenied
        return response
