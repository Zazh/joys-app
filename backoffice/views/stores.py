"""Оффлайн-точки: CRUD по образцу редиректов.

Координаты можно не вводить руками: пустые lat/lng при сохранении достаются
из вставленной ссылки 2ГИС тем же разбором, что и разовый импорт
(OfflineStore.coords_from_2gis) — второго парсера таких ссылок быть не должно.
"""

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.views import View
from django.views.generic import ListView

from backoffice.mixins import BackofficeAccessMixin
from pages.models import OfflineStore


def _fill_store(store, request):
    """Поля из POST в объект; возвращает текст ошибки или None."""
    store.city = request.POST.get('city', '').strip()
    store.name = request.POST.get('name', '').strip()
    store.address = request.POST.get('address', '').strip()
    store.map_url = request.POST.get('map_url', '').strip()
    fulfillment = request.POST.get('fulfillment', '')
    if fulfillment in OfflineStore.Fulfillment.values:
        store.fulfillment = fulfillment
    store.is_active = request.POST.get('is_active') == 'on'
    store.order = int(request.POST.get('order', 0) or 0)

    if not store.city or not store.name or not store.address:
        return 'Город, магазин и адрес обязательны.'

    lat_raw = request.POST.get('lat', '').strip().replace(',', '.')
    lng_raw = request.POST.get('lng', '').strip().replace(',', '.')
    try:
        store.lat = Decimal(lat_raw) if lat_raw else None
        store.lng = Decimal(lng_raw) if lng_raw else None
    except InvalidOperation:
        return 'Координаты — числа вида 43.204689 (или пусто, чтобы взять их из ссылки 2ГИС).'

    # Ручной ввод важнее разбора ссылки: она может вести на список филиалов
    if (store.lat is None or store.lng is None) and store.map_url:
        pair = OfflineStore.coords_from_2gis(store.map_url)
        if pair:
            store.lat, store.lng = Decimal(str(pair[0])), Decimal(str(pair[1]))
    return None


class OfflineStoreListView(BackofficeAccessMixin, ListView):
    template_name = 'backoffice/stores/list.html'
    context_object_name = 'stores'
    paginate_by = 50

    def get_queryset(self):
        qs = OfflineStore.objects.order_by('city', 'order', 'name', 'address')

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(address__icontains=q))

        city = self.request.GET.get('city')
        if city:
            qs = qs.filter(city=city)

        active = self.request.GET.get('active')
        if active == 'yes':
            qs = qs.filter(is_active=True)
        elif active == 'no':
            qs = qs.filter(is_active=False)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cities'] = (
            OfflineStore.objects.order_by('city')
            .values_list('city', flat=True).distinct()
        )
        ctx['no_coords_count'] = OfflineStore.objects.filter(lat__isnull=True).count()
        ctx['current_q'] = self.request.GET.get('q', '')
        ctx['current_city'] = self.request.GET.get('city', '')
        ctx['current_active'] = self.request.GET.get('active', '')
        return ctx


def _cities():
    return (
        OfflineStore.objects.order_by('city')
        .values_list('city', flat=True).distinct()
    )


def _form_response(request, store, is_new):
    """Форма всегда получает объект (пусть и несохранённый): значения полей
    берутся из него, отдельного словаря post_data нет — при ошибке валидации
    показывается ровно то, что ввели, включая дефолты модели у новой точки."""
    return TemplateResponse(request, 'backoffice/stores/form.html', {
        'store': store, 'is_new': is_new, 'cities': _cities(),
    })


class OfflineStoreCreateView(BackofficeAccessMixin, View):
    def get(self, request):
        return _form_response(request, OfflineStore(), is_new=True)

    def post(self, request):
        store = OfflineStore()
        if error := _fill_store(store, request):
            messages.error(request, error)
            return _form_response(request, store, is_new=True)
        store.save()
        messages.success(request, f'Точка «{store.name}, {store.address}» создана.')
        return redirect('backoffice:store_list')


class OfflineStoreEditView(BackofficeAccessMixin, View):
    def get(self, request, pk):
        store = get_object_or_404(OfflineStore, pk=pk)
        return _form_response(request, store, is_new=False)

    def post(self, request, pk):
        store = get_object_or_404(OfflineStore, pk=pk)
        if error := _fill_store(store, request):
            messages.error(request, error)
            return _form_response(request, store, is_new=False)
        store.save()
        messages.success(request, f'Точка «{store.name}, {store.address}» сохранена.')
        return redirect('backoffice:store_list')


class OfflineStoreDeleteView(BackofficeAccessMixin, View):
    def post(self, request, pk):
        store = get_object_or_404(OfflineStore, pk=pk)
        store.delete()
        messages.success(request, 'Точка удалена.')
        return redirect('backoffice:store_list')
