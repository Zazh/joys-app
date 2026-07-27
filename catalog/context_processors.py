from django.templatetags.static import static


def placeholder_image(request):
    """Добавляет placeholder_image_url во все шаблоны (кеш 1 час)."""
    from django.core.cache import cache

    def _resolve():
        from .models import SiteSettings

        url = static('dist/images/placeholder.svg')
        try:
            settings = SiteSettings.load()
            if settings.placeholder_image:
                url = settings.placeholder_image.url
        except Exception:
            pass
        return url

    return {'placeholder_image_url': cache.get_or_set('placeholder_image_url', _resolve, 3600)}


def global_jsonld(request):
    """Organization + WebSite JSON-LD на всех страницах."""
    from . import jsonld as jld

    try:
        blocks = jld.serialize_jsonld(
            jld.build_organization_jsonld(request),
            jld.build_website_jsonld(request),
        )
    except Exception:
        blocks = []

    return {'global_jsonld_blocks': blocks}
