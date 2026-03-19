from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.views import View

from backoffice.mixins import BackofficeAccessMixin
from catalog.models import Product, ProductSize, Stock
from regions.models import Region


class StockListView(BackofficeAccessMixin, View):
    def get(self, request):
        regions = Region.objects.filter(is_active=True).order_by('order')
        products = (
            Product.objects.filter(is_active=True)
            .prefetch_related('sizes__stocks__region')
            .order_by('category__order', 'name')
        )

        q = request.GET.get('q', '').strip()
        if q:
            products = products.filter(name__icontains=q)

        # Build stock matrix with region-ordered quantities
        data = []
        for product in products:
            sizes_data = []
            for size in product.sizes.all():
                stocks_by_region = {s.region_id: s for s in size.stocks.all()}
                region_stocks = []
                for region in regions:
                    stock = stocks_by_region.get(region.pk)
                    region_stocks.append({
                        'region_id': region.pk,
                        'quantity': stock.quantity if stock else 0,
                        'reserved': stock.reserved if stock else 0,
                    })
                sizes_data.append({'size': size, 'region_stocks': region_stocks})
            if sizes_data:
                data.append({'product': product, 'sizes': sizes_data})

        return render(request, 'backoffice/stock/list.html', {
            'data': data,
            'regions': regions,
            'current_q': q,
        })


class StockUpdateView(BackofficeAccessMixin, View):
    def post(self, request):
        regions = Region.objects.filter(is_active=True)
        region_ids = set(regions.values_list('id', flat=True))
        valid_size_ids = set(ProductSize.objects.values_list('id', flat=True))
        updated = 0

        with transaction.atomic():
            for key, value in request.POST.items():
                if not key.startswith('stock_'):
                    continue
                # stock_{size_id}_{region_id}
                parts = key.split('_')
                if len(parts) != 3:
                    continue
                try:
                    size_id = int(parts[1])
                    region_id = int(parts[2])
                    qty = max(0, int(value))
                except (ValueError, IndexError):
                    continue

                if region_id not in region_ids:
                    continue
                if size_id not in valid_size_ids:
                    continue

                stock, created = Stock.objects.get_or_create(
                    size_id=size_id, region_id=region_id,
                    defaults={'quantity': qty},
                )
                if not created and stock.quantity != qty:
                    stock.quantity = qty
                    stock.save(update_fields=['quantity'])
                updated += 1

        messages.success(request, f'Остатки обновлены ({updated} записей).')
        return redirect('backoffice:stock_list')
