from django.contrib import messages
from django.db.models import Q, Count, Prefetch
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.views import View
from django.views.generic import ListView

from backoffice.mixins import BackofficeAccessMixin
from catalog.models import (
    Category, Product, ProductSize, RegionPrice, Stock,
    ProductMainImage, ProductPackageImage, ProductIndividualImage,
    ProductCharacteristic, Characteristic, UnitOfMeasure,
)
from regions.models import Region


# ─── Товары ───

class ProductListView(BackofficeAccessMixin, ListView):
    template_name = 'backoffice/catalog/product_list.html'
    context_object_name = 'products'
    paginate_by = 25

    def get_queryset(self):
        qs = Product.objects.select_related('category').annotate(
            sizes_count=Count('sizes'),
            images_count=Count('main_images'),
        ).order_by('-created_at')

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(name_ru__icontains=q) |
                Q(name_kk__icontains=q) |
                Q(name_en__icontains=q) |
                Q(slug__icontains=q)
            )

        category = self.request.GET.get('category')
        if category:
            qs = qs.filter(category_id=category)

        active = self.request.GET.get('active')
        if active == 'yes':
            qs = qs.filter(is_active=True)
        elif active == 'no':
            qs = qs.filter(is_active=False)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categories'] = Category.objects.order_by('order', 'name')
        ctx['current_q'] = self.request.GET.get('q', '')
        ctx['current_category'] = self.request.GET.get('category', '')
        ctx['current_active'] = self.request.GET.get('active', '')
        return ctx


class ProductEditView(BackofficeAccessMixin, View):
    """Редактирование товара."""

    def get(self, request, pk):
        product = get_object_or_404(
            Product.objects.select_related('category').prefetch_related(
                'sizes__region_prices__region',
                'sizes__stocks__region',
                'main_images', 'package_images', 'individual_images',
                'characteristics__characteristic__unit',
            ),
            pk=pk,
        )
        regions = Region.objects.filter(is_active=True).order_by('order')
        self._attach_region_data(product, regions)

        # Подготовить характеристики: все определения + текущие значения (мультиязычные)
        all_chars = Characteristic.objects.select_related('unit').order_by('order')
        existing = {pc.characteristic_id: pc for pc in product.characteristics.all()}
        chars_data = []
        for char in all_chars:
            pc = existing.get(char.id)
            chars_data.append({
                'characteristic': char,
                'value_ru': pc.value_ru if pc else '',
                'value_kk': pc.value_kk if pc else '',
                'value_en': pc.value_en if pc else '',
                'subtitle_ru': pc.subtitle_ru if pc else '',
                'subtitle_kk': pc.subtitle_kk if pc else '',
                'subtitle_en': pc.subtitle_en if pc else '',
            })

        return TemplateResponse(request, 'backoffice/catalog/product_form.html', {
            'product': product,
            'image_groups': self._image_groups(product),
            'upload_types': [
                {'type': 'main', 'label': 'Основные'},
                {'type': 'package', 'label': 'Упаковка'},
                {'type': 'individual', 'label': 'Индивидуальная'},
            ],
            'chars_data': chars_data,
            **self._form_context(product),
        })

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)

        # Основные поля
        product.name_ru = request.POST.get('name_ru', '').strip()
        product.name_kk = request.POST.get('name_kk', '').strip()
        product.name_en = request.POST.get('name_en', '').strip()
        product.tagline_ru = request.POST.get('tagline_ru', '').strip()
        product.tagline_kk = request.POST.get('tagline_kk', '').strip()
        product.tagline_en = request.POST.get('tagline_en', '').strip()
        product.description_ru = request.POST.get('description_ru', '').strip()
        product.description_kk = request.POST.get('description_kk', '').strip()
        product.description_en = request.POST.get('description_en', '').strip()
        product.slug = request.POST.get('slug', '').strip()
        product.category_id = request.POST.get('category')
        product.badge = request.POST.get('badge', '')
        product.is_active = request.POST.get('is_active') == 'on'
        product.pack_quantity = request.POST.get('pack_quantity') or None

        # SEO
        product.meta_title_ru = request.POST.get('meta_title_ru', '').strip()
        product.meta_title_kk = request.POST.get('meta_title_kk', '').strip()
        product.meta_title_en = request.POST.get('meta_title_en', '').strip()
        product.meta_description_ru = request.POST.get('meta_description_ru', '').strip()
        product.meta_description_kk = request.POST.get('meta_description_kk', '').strip()
        product.meta_description_en = request.POST.get('meta_description_en', '').strip()

        # Изображения
        if 'transparent_image' in request.FILES:
            product.transparent_image = request.FILES['transparent_image']
        if 'transparent_image_kk' in request.FILES:
            product.transparent_image_kk = request.FILES['transparent_image_kk']
        if 'zoom_image' in request.FILES:
            product.zoom_image = request.FILES['zoom_image']
        product.zoom_rotation_angle = int(request.POST.get('zoom_rotation_angle', 15) or 15)

        product.save()

        # Размеры
        self._save_sizes(request, product)

        # Характеристики
        self._save_characteristics(request, product)

        messages.success(request, f'Товар «{product.name_ru}» сохранён.')
        return redirect('backoffice:product_edit', pk=product.pk)

    def _save_sizes(self, request, product):
        """Сохранить размеры и региональные цены."""
        size_ids = request.POST.getlist('size_id')
        regions = Region.objects.filter(is_active=True)

        for size_id in size_ids:
            if not size_id:
                continue
            try:
                size = ProductSize.objects.get(pk=size_id, product=product)
            except ProductSize.DoesNotExist:
                continue

            size.name = request.POST.get(f'size_name_{size_id}', '').strip()
            size.sku = request.POST.get(f'size_sku_{size_id}', '').strip()
            size.price = request.POST.get(f'size_price_{size_id}') or 0
            size.old_price = request.POST.get(f'size_old_price_{size_id}') or None
            size.order = request.POST.get(f'size_order_{size_id}') or 0
            size.save()

            # Региональные цены
            for region in regions:
                rp_price = request.POST.get(f'rp_{size_id}_{region.id}')
                rp_old = request.POST.get(f'rp_old_{size_id}_{region.id}')
                if rp_price is not None:
                    RegionPrice.objects.update_or_create(
                        size=size, region=region,
                        defaults={
                            'price': rp_price or 0,
                            'old_price': rp_old or None,
                        },
                    )

            # Остатки
            for region in regions:
                qty = request.POST.get(f'stock_{size_id}_{region.id}')
                if qty is not None:
                    Stock.objects.update_or_create(
                        size=size, region=region,
                        defaults={'quantity': int(qty or 0)},
                    )

    def _save_characteristics(self, request, product):
        """Сохранить характеристики товара (мультиязычные)."""
        characteristics = Characteristic.objects.all()
        for char in characteristics:
            value_ru = request.POST.get(f'char_value_ru_{char.id}', '').strip()
            value_kk = request.POST.get(f'char_value_kk_{char.id}', '').strip()
            value_en = request.POST.get(f'char_value_en_{char.id}', '').strip()
            subtitle_ru = request.POST.get(f'char_subtitle_ru_{char.id}', '').strip()
            subtitle_kk = request.POST.get(f'char_subtitle_kk_{char.id}', '').strip()
            subtitle_en = request.POST.get(f'char_subtitle_en_{char.id}', '').strip()

            has_value = value_ru or value_kk or value_en
            if has_value:
                ProductCharacteristic.objects.update_or_create(
                    product=product, characteristic=char,
                    defaults={
                        'value_ru': value_ru, 'value_kk': value_kk, 'value_en': value_en,
                        'subtitle_ru': subtitle_ru, 'subtitle_kk': subtitle_kk, 'subtitle_en': subtitle_en,
                    },
                )
            else:
                ProductCharacteristic.objects.filter(
                    product=product, characteristic=char,
                ).delete()

    def _attach_region_data(self, product, regions):
        """Подготовить region_data для каждого size — цены и остатки по регионам."""
        for size in product.sizes.all():
            rp_map = {rp.region_id: rp for rp in size.region_prices.all()}
            st_map = {st.region_id: st for st in size.stocks.all()}
            region_data = []
            for region in regions:
                rp = rp_map.get(region.id)
                st = st_map.get(region.id)
                region_data.append({
                    'region': region,
                    'price': rp.price if rp else None,
                    'old_price': rp.old_price if rp else None,
                    'stock': st.quantity if st else 0,
                })
            size.region_data = region_data

    def _image_groups(self, product):
        """Сгруппировать изображения для шаблона."""
        return [
            {'type': 'main', 'label': 'Основные фото', 'images': list(product.main_images.all())},
            {'type': 'package', 'label': 'Фото упаковки', 'images': list(product.package_images.all())},
            {'type': 'individual', 'label': 'Фото индивидуальной упаковки', 'images': list(product.individual_images.all())},
        ]

    def _form_context(self, product=None):
        return {
            'categories': Category.objects.order_by('order', 'name'),
            'badges': Product.Badge.choices,
            'regions': Region.objects.filter(is_active=True).order_by('order'),
            'characteristics': Characteristic.objects.order_by('order'),
        }


class ProductCreateView(BackofficeAccessMixin, View):
    """Создание товара."""

    def get(self, request):
        return TemplateResponse(request, 'backoffice/catalog/product_form.html', {
            'product': None,
            'categories': Category.objects.order_by('order', 'name'),
            'badges': Product.Badge.choices,
            'regions': Region.objects.filter(is_active=True).order_by('order'),
            'characteristics': Characteristic.objects.order_by('order'),
        })

    def post(self, request):
        product = Product(
            name_ru=request.POST.get('name_ru', '').strip(),
            name_kk=request.POST.get('name_kk', '').strip(),
            name_en=request.POST.get('name_en', '').strip(),
            tagline_ru=request.POST.get('tagline_ru', '').strip(),
            tagline_kk=request.POST.get('tagline_kk', '').strip(),
            tagline_en=request.POST.get('tagline_en', '').strip(),
            description_ru=request.POST.get('description_ru', '').strip(),
            description_kk=request.POST.get('description_kk', '').strip(),
            description_en=request.POST.get('description_en', '').strip(),
            slug=request.POST.get('slug', '').strip(),
            category_id=request.POST.get('category'),
            badge=request.POST.get('badge', ''),
            is_active=request.POST.get('is_active') == 'on',
            pack_quantity=request.POST.get('pack_quantity') or None,
            meta_title_ru=request.POST.get('meta_title_ru', '').strip(),
            meta_title_kk=request.POST.get('meta_title_kk', '').strip(),
            meta_title_en=request.POST.get('meta_title_en', '').strip(),
            meta_description_ru=request.POST.get('meta_description_ru', '').strip(),
            meta_description_kk=request.POST.get('meta_description_kk', '').strip(),
            meta_description_en=request.POST.get('meta_description_en', '').strip(),
        )

        if 'transparent_image' in request.FILES:
            product.transparent_image = request.FILES['transparent_image']
        if 'transparent_image_kk' in request.FILES:
            product.transparent_image_kk = request.FILES['transparent_image_kk']
        if 'zoom_image' in request.FILES:
            product.zoom_image = request.FILES['zoom_image']
        product.zoom_rotation_angle = int(request.POST.get('zoom_rotation_angle', 15) or 15)

        if not product.slug or not product.name_ru:
            messages.error(request, 'Название (RU) и slug обязательны.')
            return TemplateResponse(request, 'backoffice/catalog/product_form.html', {
                'product': None,
                'categories': Category.objects.order_by('order', 'name'),
                'badges': Product.Badge.choices,
                'regions': Region.objects.filter(is_active=True).order_by('order'),
                'characteristics': Characteristic.objects.order_by('order'),
                'post_data': request.POST,
            })

        product.save()
        messages.success(request, f'Товар «{product.name_ru}» создан.')
        return redirect('backoffice:product_edit', pk=product.pk)


class ProductSizeCreateView(BackofficeAccessMixin, View):
    """Добавить новый размер."""
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        name = request.POST.get('name', '').strip()
        sku = request.POST.get('sku', '').strip()
        price = request.POST.get('price', '0')

        if not name or not sku:
            messages.error(request, 'Название и артикул обязательны.')
            return redirect('backoffice:product_edit', pk=pk)

        if ProductSize.objects.filter(sku=sku).exists():
            messages.error(request, f'Артикул «{sku}» уже существует.')
            return redirect('backoffice:product_edit', pk=pk)

        ProductSize.objects.create(
            product=product,
            name=name,
            sku=sku,
            price=price or 0,
            old_price=request.POST.get('old_price') or None,
            order=request.POST.get('order') or 0,
        )
        messages.success(request, f'Размер «{name}» добавлен.')
        return redirect('backoffice:product_edit', pk=pk)


class ProductSizeDeleteView(BackofficeAccessMixin, View):
    """Удалить размер."""
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        size_id = request.POST.get('size_id')
        if size_id:
            deleted, _ = ProductSize.objects.filter(pk=size_id, product=product).delete()
            if deleted:
                messages.success(request, 'Размер удалён.')
        return redirect('backoffice:product_edit', pk=pk)


class ProductToggleActiveView(BackofficeAccessMixin, View):
    """Быстрое вкл/выкл товара."""
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        product.is_active = not product.is_active
        product.save(update_fields=['is_active'])
        return redirect('backoffice:product_list')


class ProductImageUploadView(BackofficeAccessMixin, View):
    """Загрузка изображений товара."""
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        image_type = request.POST.get('image_type', 'main')

        model_map = {
            'main': ProductMainImage,
            'package': ProductPackageImage,
            'individual': ProductIndividualImage,
        }
        Model = model_map.get(image_type)
        if not Model:
            messages.error(request, 'Неверный тип изображения.')
            return redirect('backoffice:product_edit', pk=pk)

        files = request.FILES.getlist('images')
        for f in files:
            kwargs = {'product': product, 'image': f}
            if image_type == 'main':
                # Если это первое фото — сделать обложкой
                if not product.main_images.exists():
                    kwargs['is_cover'] = True
            Model.objects.create(**kwargs)

        messages.success(request, f'Загружено {len(files)} фото.')
        return redirect('backoffice:product_edit', pk=pk)


class ProductImageDeleteView(BackofficeAccessMixin, View):
    """Удаление изображения товара."""
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        image_type = request.POST.get('image_type', 'main')
        image_id = request.POST.get('image_id')

        model_map = {
            'main': ProductMainImage,
            'package': ProductPackageImage,
            'individual': ProductIndividualImage,
        }
        Model = model_map.get(image_type)
        if Model and image_id:
            Model.objects.filter(pk=image_id, product=product).delete()

        return redirect('backoffice:product_edit', pk=pk)


class ProductImageCoverView(BackofficeAccessMixin, View):
    """Установить обложку."""
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        image_id = request.POST.get('image_id')
        if image_id:
            product.main_images.update(is_cover=False)
            product.main_images.filter(pk=image_id).update(is_cover=True)
        return redirect('backoffice:product_edit', pk=pk)


# ─── Категории ───

# ─── Характеристики (справочник) ───

class CharacteristicListView(BackofficeAccessMixin, View):
    """Справочник характеристик."""
    def get(self, request):
        chars = Characteristic.objects.select_related('unit').order_by('order', 'name_ru')
        units = UnitOfMeasure.objects.order_by('name_ru')
        return TemplateResponse(request, 'backoffice/catalog/characteristic_list.html', {
            'characteristics': chars,
            'units': units,
        })


class CharacteristicCreateView(BackofficeAccessMixin, View):
    """Создать характеристику."""
    def post(self, request):
        name_ru = request.POST.get('name_ru', '').strip()
        if not name_ru:
            messages.error(request, 'Название (RU) обязательно.')
            return redirect('backoffice:characteristic_list')

        Characteristic.objects.create(
            name_ru=name_ru,
            name_kk=request.POST.get('name_kk', '').strip(),
            name_en=request.POST.get('name_en', '').strip(),
            unit_id=request.POST.get('unit') or None,
            order=int(request.POST.get('order', 0) or 0),
        )
        messages.success(request, f'Характеристика «{name_ru}» создана.')
        return redirect('backoffice:characteristic_list')


class CharacteristicEditView(BackofficeAccessMixin, View):
    """Редактировать характеристику."""
    def get(self, request, pk):
        char = get_object_or_404(Characteristic.objects.select_related('unit'), pk=pk)
        units = UnitOfMeasure.objects.order_by('name_ru')
        return TemplateResponse(request, 'backoffice/catalog/characteristic_form.html', {
            'char': char,
            'units': units,
        })

    def post(self, request, pk):
        char = get_object_or_404(Characteristic, pk=pk)
        char.name_ru = request.POST.get('name_ru', '').strip()
        char.name_kk = request.POST.get('name_kk', '').strip()
        char.name_en = request.POST.get('name_en', '').strip()
        char.unit_id = request.POST.get('unit') or None
        char.order = int(request.POST.get('order', 0) or 0)
        char.save()
        messages.success(request, f'Характеристика «{char.name_ru}» сохранена.')
        return redirect('backoffice:characteristic_list')


class CharacteristicDeleteView(BackofficeAccessMixin, View):
    """Удалить характеристику."""
    def post(self, request, pk):
        char = get_object_or_404(Characteristic, pk=pk)
        char.delete()
        messages.success(request, 'Характеристика удалена.')
        return redirect('backoffice:characteristic_list')


# ─── Категории ───

class CategoryListView(BackofficeAccessMixin, ListView):
    template_name = 'backoffice/catalog/category_list.html'
    context_object_name = 'categories'

    def get_queryset(self):
        return Category.objects.annotate(
            products_count=Count('products'),
        ).order_by('order', 'name')


class CategoryEditView(BackofficeAccessMixin, View):
    def get(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        return TemplateResponse(request, 'backoffice/catalog/category_form.html', {
            'category': category,
        })

    def post(self, request, pk):
        category = get_object_or_404(Category, pk=pk)

        category.name_ru = request.POST.get('name_ru', '').strip()
        category.name_kk = request.POST.get('name_kk', '').strip()
        category.name_en = request.POST.get('name_en', '').strip()
        category.slug = request.POST.get('slug', '').strip()
        category.description_ru = request.POST.get('description_ru', '').strip()
        category.description_kk = request.POST.get('description_kk', '').strip()
        category.description_en = request.POST.get('description_en', '').strip()
        category.is_active = request.POST.get('is_active') == 'on'
        category.order = int(request.POST.get('order', 0) or 0)
        category.meta_title_ru = request.POST.get('meta_title_ru', '').strip()
        category.meta_title_kk = request.POST.get('meta_title_kk', '').strip()
        category.meta_title_en = request.POST.get('meta_title_en', '').strip()
        category.meta_description_ru = request.POST.get('meta_description_ru', '').strip()
        category.meta_description_kk = request.POST.get('meta_description_kk', '').strip()
        category.meta_description_en = request.POST.get('meta_description_en', '').strip()

        if 'image' in request.FILES:
            category.image = request.FILES['image']

        category.save()
        messages.success(request, f'Категория «{category.name_ru}» сохранена.')
        return redirect('backoffice:category_edit', pk=category.pk)


class CategoryCreateView(BackofficeAccessMixin, View):
    def get(self, request):
        return TemplateResponse(request, 'backoffice/catalog/category_form.html', {
            'category': None,
        })

    def post(self, request):
        category = Category(
            name_ru=request.POST.get('name_ru', '').strip(),
            name_kk=request.POST.get('name_kk', '').strip(),
            name_en=request.POST.get('name_en', '').strip(),
            slug=request.POST.get('slug', '').strip(),
            description_ru=request.POST.get('description_ru', '').strip(),
            description_kk=request.POST.get('description_kk', '').strip(),
            description_en=request.POST.get('description_en', '').strip(),
            is_active=request.POST.get('is_active') == 'on',
            order=int(request.POST.get('order', 0) or 0),
            meta_title_ru=request.POST.get('meta_title_ru', '').strip(),
            meta_title_kk=request.POST.get('meta_title_kk', '').strip(),
            meta_title_en=request.POST.get('meta_title_en', '').strip(),
            meta_description_ru=request.POST.get('meta_description_ru', '').strip(),
            meta_description_kk=request.POST.get('meta_description_kk', '').strip(),
            meta_description_en=request.POST.get('meta_description_en', '').strip(),
        )

        if 'image' in request.FILES:
            category.image = request.FILES['image']

        if not category.slug or not category.name_ru:
            messages.error(request, 'Название (RU) и slug обязательны.')
            return TemplateResponse(request, 'backoffice/catalog/category_form.html', {
                'category': None,
                'post_data': request.POST,
            })

        category.save()
        messages.success(request, f'Категория «{category.name_ru}» создана.')
        return redirect('backoffice:category_list')
