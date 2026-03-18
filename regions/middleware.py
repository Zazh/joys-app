from .models import Region


class RegionMiddleware:
    """
    Читает регион из cookie 'drjoys_region'.
    Устанавливает request.region, request.region_code, request.show_region_modal.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._cache = {}
        self._default = None

    def __call__(self, request):
        region_code = request.COOKIES.get('drjoys_region')

        if region_code:
            region = self._get_region(region_code)
            show_modal = region is None
            if not region:
                region = self._get_default()
        else:
            region = self._get_default()
            show_modal = True

        request.region = region
        request.region_code = region.code if region else 'kz'
        request.show_region_modal = show_modal

        return self.get_response(request)

    def _get_region(self, code):
        if code not in self._cache:
            try:
                self._cache[code] = Region.objects.get(
                    code=code, is_active=True,
                )
            except Region.DoesNotExist:
                self._cache[code] = None
        return self._cache[code]

    def _get_default(self):
        if self._default is None:
            self._default = Region.get_default()
        return self._default
