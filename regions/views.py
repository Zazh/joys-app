from django.http import HttpResponseRedirect
from django.views import View

from .models import Region


class SetRegionView(View):
    """POST: установить cookie drjoys_region и redirect обратно."""

    def post(self, request):
        region_code = request.POST.get('region', '')
        redirect_url = request.POST.get('next', '/')

        try:
            region = Region.objects.get(code=region_code, is_active=True)
        except Region.DoesNotExist:
            region = Region.get_default()

        response = HttpResponseRedirect(redirect_url)
        response.set_cookie(
            'drjoys_region',
            region.code,
            max_age=365 * 24 * 60 * 60,
            httponly=False,
            samesite='Lax',
        )
        return response
