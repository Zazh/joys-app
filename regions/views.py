from django.http import HttpResponseRedirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from .middleware import get_default_region, get_region


class SetRegionView(View):
    """POST: установить cookie drjoys_region и redirect обратно."""

    def post(self, request):
        region_code = request.POST.get('region', '')
        redirect_url = request.POST.get('next', '/')

        # next приходит из формы — без проверки чужой сайт увёл бы покупателя
        # к себе, попутно выставив ему наш регион
        if not url_has_allowed_host_and_scheme(
            redirect_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            redirect_url = '/'

        # Тот же поиск, что у middleware (общий кеш, PH-08), а не свой второй:
        # cookie ставит эта вьюха, а читает его middleware — расходиться им нельзя
        region = get_region(region_code) or get_default_region()

        response = HttpResponseRedirect(redirect_url)
        # Дефолта может не быть вовсе, и это не поломка данных: снять
        # `is_default` у одного региона, не назначив другого, — единственный
        # путь смены дефолта (constraint `unique_default_region` не даёт
        # держать два сразу). В этом окне `region.code` падал с AttributeError,
        # то есть 500 посетителю с чужим кодом региона. Cookie просто не ставим:
        # человек увидит модалку выбора региона и выберет сам.
        if region:
            response.set_cookie(
                'drjoys_region',
                region.code,
                max_age=365 * 24 * 60 * 60,
                httponly=False,
                samesite='Lax',
            )
        return response
