from django.templatetags.static import static


def placeholder_image(request):
    """Добавляет placeholder_image_url во все шаблоны."""
    from .models import SiteSettings

    url = static('dist/images/placeholder.svg')

    try:
        settings = SiteSettings.load()
        if settings.placeholder_image:
            url = settings.placeholder_image.url
    except Exception:
        pass

    return {'placeholder_image_url': url}


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
