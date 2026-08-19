from django.db.models import Prefetch
from django.http import Http404
from django.urls import reverse
from django.utils.translation import gettext as _, gettext_lazy
from django.views.generic import ListView, DetailView

from core import seo

from modals.models import InteractiveModal

from .models import (
    Category, Product, ProductSize, FAQ, RegionPrice, Stock, resolve_buy_state,
)
from . import jsonld as jld


class CatalogListView(ListView):
    model = Product
    template_name = 'pages/catalog.html'
    context_object_name = 'products'
    # Пагинации нет: линейка помещается на одну страницу, отбор — фильтром
    # категорий (решение владельца). Заодно в ItemList JSON-LD попадает весь
    # список, а не первая страница

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
        # Один запрос вместо count/first/get по одной и той же таблице
        categories = list(Category.objects.filter(is_active=True))
        category_count = len(categories)
        single_category = categories[0] if category_count == 1 else None

        category_slug = self.kwargs.get('category_slug')
        current_category = None
        if category_slug:
            current_category = next(
                (c for c in categories if c.slug == category_slug), None,
            )
            if current_category is None:
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
            else _('Каталог презервативов DR.JOYS')
        )
        ctx['meta_description'] = (
            seo.first_filled(
                current_category.meta_description,
                current_category.description,
                _('%(name)s DR.JOYS — официальный интернет-магазин, доставка '
                  'по Казахстану и России.') % {'name': current_category.name},
            )
            if current_category
            else _('Каталог презервативов DR.JOYS — классические, ребристые, ультратонкие')
        )

        # Крошки — только на странице категории. На общем списке цепочка была бы
        # «DR.JOYS / Каталог», то есть пересказ заголовка, поэтому её нет ни в
        # вёрстке, ни в JSON-LD: размечать то, чего пользователь не видит, —
        # против рекомендаций Google по структурированным данным.
        # Опора на category_slug из URL, а не на current_category: когда активна
        # одна категория, она подставляется и на /catalog/, и последняя крошка
        # указывала бы на URL, отличный от текущего.
        breadcrumbs = []
        if category_slug and current_category:
            breadcrumbs = [
                {'name': 'DR.JOYS', 'url': reverse('home')},
                {'name': _('Каталог'), 'url': reverse('catalog:catalog')},
                {'name': current_category.name, 'url': ''},
            ]
        ctx['breadcrumbs'] = breadcrumbs

        # JSON-LD
        ctx['jsonld_blocks'] = jld.serialize_jsonld(
            jld.build_breadcrumb_jsonld(self.request, breadcrumbs) if breadcrumbs else None,
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

    # Подписи под слайдерами фото (упаковка, индивидуальная упаковка) по slug
    # категории. gettext_lazy: строки переводятся в момент рендера, а не импорта
    PHOTO_CAPTIONS = {
        'prezervativy': (
            gettext_lazy('Упаковка презервативов DR.JOYS'),
            gettext_lazy('Презерватив в индивидуальной упаковке'),
        ),
        'smazki': (
            gettext_lazy('Упаковка лубриканта DR.JOYS'),
            gettext_lazy('Лубрикант в индивидуальной упаковке'),
        ),
    }
    DEFAULT_PHOTO_CAPTIONS = (
        gettext_lazy('Упаковка товара DR.JOYS'),
        gettext_lazy('Товар в индивидуальной упаковке'),
    )

    def get_queryset(self):
        region = getattr(self.request, 'region', None)
        rp_qs = RegionPrice.objects.filter(region=region) if region else RegionPrice.objects.none()
        stock_qs = Stock.objects.filter(region=region) if region else Stock.objects.none()
        return (
            Product.objects
            .filter(is_active=True)
            .select_related(
                'category', 'category__size_guide_page',
                'category__usage_page', 'category__contraindications_page',
            )
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
        # Состояние покупки одним флагом: от него зависят и подпись кнопки, и
        # стиль, и показ цены. В шаблоне это условие собиралось трижды и
        # расходилось — размер без остатка, но с ценой, давал «Добавить в
        # корзину». Тот же расчёт печатает статус в карточке каталога, поэтому
        # он общий (resolve_buy_state), а не свой у каждой страницы
        region = getattr(self.request, 'region', None)
        ctx['buy_state'], ctx['default_size'] = resolve_buy_state(sizes, region)
        cover_image = product.get_cover_image()
        ctx['cover_image'] = cover_image
        main_images = list(product.main_images.all())
        ctx['main_images'] = main_images
        ctx['package_images'] = product.package_images.all()
        ctx['individual_images'] = product.individual_images.all()
        # Подписи под слайдерами фото — по категории: жёсткие «презервативы»
        # из шаблона показывались и на смазках. Неизвестной категории — общий текст
        captions = self.PHOTO_CAPTIONS.get(
            product.category.slug, self.DEFAULT_PHOTO_CAPTIONS,
        )
        ctx['package_caption'], ctx['individual_caption'] = captions

        # Справочные материалы категории (правятся в бэкофисе). Модалка размера
        # в приоритете над страницей; неопубликованная страница — как пустое поле
        category = product.category
        ctx['size_guide_modal'] = None
        if category.size_guide_modal_id:
            ctx['size_guide_modal'] = (
                InteractiveModal.objects
                .filter(pk=category.size_guide_modal_id, is_active=True)
                .prefetch_related('steps', 'steps__inquiry_form', 'steps__inquiry_form__fields')
                .first()
            )
        for key in ('size_guide_page', 'usage_page', 'contraindications_page'):
            linked = getattr(category, key)
            ctx[key] = linked if linked and linked.is_published else None
        if ctx['size_guide_modal']:
            ctx['size_guide_page'] = None
        characteristics = list(
            product.characteristics.select_related('characteristic__unit').all()
        )
        ctx['characteristics'] = characteristics
        ctx['page_type'] = 'product_detail'

        # Хлебные крошки
        breadcrumbs = [
            {'name': 'DR.JOYS', 'url': reverse('home')},
            {'name': _('Каталог'), 'url': reverse('catalog:catalog')},
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

        # Заголовок и описание: заполненные в бэкофисе поля в приоритете, иначе
        # собираем сами. Голое `product.name` («Классика 17 шт») не совпадает
        # с запросом ни одним словом, кроме числа, и Google такой заголовок
        # всё равно переписывает — лучше дать ему готовый.
        ctx['meta_title'] = product.meta_title or seo.with_brand(
            product.name, seo.category_suffix(product.category.name, product.name),
        )
        ctx['meta_description'] = seo.first_filled(
            product.meta_description,
            product.description,
            product.tagline,
            _('%(name)s — %(category)s DR.JOYS. Официальный интернет-магазин, '
              'доставка по Казахстану и России.') % {
                'name': product.name, 'category': product.category.name,
            },
        )

        # Связанные товары: сначала соседи по категории, как и раньше. Но если
        # их мало (у смазок всего два товара — карусель стояла из одной карточки),
        # добираем до шести товарами остальных категорий в порядке каталога
        region = getattr(self.request, 'region', None)
        rel_rp_qs = RegionPrice.objects.filter(region=region) if region else RegionPrice.objects.none()
        # Остатки префетчим и здесь: без них in_stock отдаёт True, и карточка
        # карусели печатала цену там, где та же карточка в каталоге говорит
        # «Нет в наличии». Это prefetch, то есть один запрос на весь список,
        # а не N+1
        rel_stock_qs = Stock.objects.filter(region=region) if region else Stock.objects.none()
        rel_qs = (
            Product.objects
            .filter(is_active=True)
            .exclude(pk=product.pk)
            .prefetch_related(
                'main_images',
                Prefetch(
                    'sizes',
                    queryset=ProductSize.objects.prefetch_related(
                        Prefetch('region_prices', queryset=rel_rp_qs, to_attr='_region_prices'),
                        Prefetch('stocks', queryset=rel_stock_qs, to_attr='_stocks'),
                    ),
                ),
            )
        )
        related = list(rel_qs.filter(category=product.category)[:6])
        if len(related) < 6:
            related += list(
                rel_qs.exclude(category=product.category)[:6 - len(related)]
            )
        ctx['related_products'] = related

        # Проверить, в избранном ли товар
        from orders.cart import Favorites
        favs = Favorites(self.request)
        ctx['is_favorited'] = product.pk in favs

        return ctx

