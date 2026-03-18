from django.db.models import Prefetch
from django.http import Http404
from django.urls import reverse
from django.views.generic import ListView, DetailView

from .models import Category, Product, ProductSize, FAQ, RegionPrice, Stock
from . import jsonld as jld


class CatalogListView(ListView):
    model = Product
    template_name = 'pages/catalog.html'
    context_object_name = 'products'

    def get_queryset(self):
        region = getattr(self.request, 'region', None)
        rp_qs = RegionPrice.objects.filter(region=region) if region else RegionPrice.objects.none()
        stock_qs = Stock.objects.filter(region=region) if region else Stock.objects.none()
        qs = (
            Product.objects
            .filter(is_active=True)
            .select_related('category')
            .prefetch_related(
                'main_images',
                Prefetch(
                    'sizes',
                    queryset=ProductSize.objects.prefetch_related(
                        Prefetch('region_prices', queryset=rp_qs, to_attr='_region_prices'),
                        Prefetch('stocks', queryset=stock_qs, to_attr='_stocks'),
                    ),
                ),
            )
        )
        category_slug = self.kwargs.get('category_slug')
        if category_slug:
            qs = qs.filter(category__slug=category_slug, category__is_active=True)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        categories = Category.objects.filter(is_active=True)
        category_count = categories.count()
        single_category = categories.first() if category_count == 1 else None

        category_slug = self.kwargs.get('category_slug')
        current_category = None
        if category_slug:
            try:
                current_category = categories.get(slug=category_slug)
            except Category.DoesNotExist:
                raise Http404
        elif single_category:
            current_category = single_category

        ctx['categories'] = categories
        ctx['current_category'] = current_category
        ctx['show_filters'] = category_count > 1
        ctx['single_category'] = single_category
        faqs = FAQ.objects.filter(is_active=True)
        ctx['faqs'] = faqs
        ctx['page_type'] = 'catalog'
        ctx['meta_title'] = (
            current_category.meta_title or current_category.name
            if current_category
            else 'Каталог презервативов DR.JOYS'
        )
        ctx['meta_description'] = (
            current_category.meta_description
            if current_category
            else 'Каталог презервативов DR.JOYS — классические, ребристые, ультратонкие'
        )

        # JSON-LD
        breadcrumbs = [
            {'name': 'DR.JOYS', 'url': reverse('home')},
            {'name': 'Каталог', 'url': reverse('catalog:catalog')},
        ]
        if current_category:
            breadcrumbs.append({
                'name': current_category.name,
                'url': current_category.get_absolute_url(),
            })
        ctx['jsonld_blocks'] = jld.serialize_jsonld(
            jld.build_breadcrumb_jsonld(self.request, breadcrumbs),
            jld.build_catalog_itemlist_jsonld(
                self.request, ctx['products'], current_category,
                region=getattr(self.request, 'region', None),
            ),
            jld.build_faq_jsonld(faqs),
        )

        return ctx


class ProductDetailView(DetailView):
    model = Product
    template_name = 'pages/product_detail.html'
    context_object_name = 'product'
    slug_url_kwarg = 'product_slug'

    def get_queryset(self):
        region = getattr(self.request, 'region', None)
        rp_qs = RegionPrice.objects.filter(region=region) if region else RegionPrice.objects.none()
        stock_qs = Stock.objects.filter(region=region) if region else Stock.objects.none()
        return (
            Product.objects
            .filter(is_active=True)
            .select_related('category')
            .prefetch_related(
                Prefetch(
                    'sizes',
                    queryset=ProductSize.objects.prefetch_related(
                        Prefetch('region_prices', queryset=rp_qs, to_attr='_region_prices'),
                        Prefetch('stocks', queryset=stock_qs, to_attr='_stocks'),
                    ),
                ),
                'characteristics__characteristic__unit',
                'main_images',
                'package_images',
                'individual_images',
            )
        )

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.category.slug != self.kwargs['category_slug']:
            raise Http404
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        product = self.object

        sizes = list(product.sizes.all())
        ctx['sizes'] = sizes
        ctx['default_size'] = sizes[0] if sizes else None
        cover_image = product.get_cover_image()
        ctx['cover_image'] = cover_image
        main_images = list(product.main_images.all())
        ctx['main_images'] = main_images
        ctx['package_images'] = product.package_images.all()
        ctx['individual_images'] = product.individual_images.all()
        characteristics = list(
            product.characteristics.select_related('characteristic__unit').all()
        )
        ctx['characteristics'] = characteristics
        ctx['page_type'] = 'product_detail'

        # Хлебные крошки
        breadcrumbs = [
            {'name': 'DR.JOYS', 'url': reverse('home')},
            {'name': 'Каталог', 'url': reverse('catalog:catalog')},
            {'name': product.category.name, 'url': product.category.get_absolute_url()},
            {'name': product.name, 'url': ''},
        ]
        ctx['breadcrumbs'] = breadcrumbs

        # JSON-LD
        ctx['jsonld_blocks'] = jld.serialize_jsonld(
            jld.build_breadcrumb_jsonld(self.request, breadcrumbs),
            jld.build_product_jsonld(
                self.request, product, sizes, cover_image, main_images, characteristics,
                region=getattr(self.request, 'region', None),
            ),
        )

        ctx['meta_title'] = product.meta_title or product.name
        ctx['meta_description'] = product.meta_description or product.description

        # Связанные товары (из той же категории)
        region = getattr(self.request, 'region', None)
        rel_rp_qs = RegionPrice.objects.filter(region=region) if region else RegionPrice.objects.none()
        ctx['related_products'] = (
            Product.objects
            .filter(is_active=True, category=product.category)
            .exclude(pk=product.pk)
            .prefetch_related(
                'main_images',
                Prefetch(
                    'sizes',
                    queryset=ProductSize.objects.prefetch_related(
                        Prefetch('region_prices', queryset=rel_rp_qs, to_attr='_region_prices'),
                    ),
                ),
            )[:6]
        )

        # Проверить, в избранном ли товар
        from orders.cart import Favorites
        favs = Favorites(self.request)
        ctx['is_favorited'] = product.pk in favs

        return ctx

