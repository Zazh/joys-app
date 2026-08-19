"""Оффлайн-точки: CRUD по образцу редиректов.

Координаты можно не вводить руками: пустые lat/lng при сохранении достаются
из вставленной ссылки 2ГИС тем же разбором, что и разовый импорт
(OfflineStore.coords_from_2gis) — второго парсера таких ссылок быть не должно.
"""

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.views import View
from django.views.generic import ListView

from backoffice.mixins import StoreManagerSectionMixin
from pages.models import City, OfflineStore


def _city_pk(raw):
    """id города из сырой строки запроса или None, если это не число.

    И фильтр списка, и селект формы шлют id, но в адрес приходит и чужое:
    ссылка эпохи текстового города (`?city=Алматы`), правка адреса руками.
    Без проверки такой запрос уходит в БД и падает ValueError — 500 вместо
    списка. `isdigit()` тут не годится: у '²' он True, а int('²') бросает.
    """
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _fill_store(store, request):
    """Поля из POST в объект; возвращает текст ошибки или None."""
    # Город — id из селекта справочника: свободный ввод разводил «Алматы»
    # и «алматы» по двум записям. Присваиваем до валидации, чтобы форма после
    # ошибки вернула выбранный город
    city_pk = _city_pk(request.POST.get('city', '').strip())
    city = City.objects.filter(pk=city_pk).first() if city_pk is not None else None
    store.city = city
    store.name = request.POST.get('name', '').strip()
    store.address = request.POST.get('address', '').strip()
    store.map_url = request.POST.get('map_url', '').strip()
    fulfillment = request.POST.get('fulfillment', '')
    if fulfillment in OfflineStore.Fulfillment.values:
        store.fulfillment = fulfillment
    store.is_active = request.POST.get('is_active') == 'on'
    store.order = int(request.POST.get('order', 0) or 0)

    # Проверяем локальную переменную, а не store.city: у необязательного к
    # заполнению, но не-nullable FK чтение пустого значения бросает DoesNotExist
    if city is None or not store.name or not store.address:
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


class OfflineStoreListView(StoreManagerSectionMixin, ListView):
    template_name = 'backoffice/stores/list.html'
    context_object_name = 'stores'
    paginate_by = 50

    def get_queryset(self):
        qs = (OfflineStore.objects.select_related('city')
              .order_by('city__name', 'order', 'name', 'address'))

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(address__icontains=q))

        city_pk = _city_pk(self.request.GET.get('city'))
        if city_pk is not None:
            qs = qs.filter(city_id=city_pk)

        active = self.request.GET.get('active')
        if active == 'yes':
            qs = qs.filter(is_active=True)
        elif active == 'no':
            qs = qs.filter(is_active=False)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cities'] = _cities()
        ctx['no_coords_count'] = OfflineStore.objects.filter(lat__isnull=True).count()
        ctx['current_q'] = self.request.GET.get('q', '')
        ctx['current_city'] = self.request.GET.get('city', '')
        ctx['current_active'] = self.request.GET.get('active', '')
        return ctx


def _cities():
    """Справочник целиком — опции селекта в форме и фильтра в списке."""
    return City.objects.all()


def _form_response(request, store, is_new):
    """Форма всегда получает объект (пусть и несохранённый): значения полей
    берутся из него, отдельного словаря post_data нет — при ошибке валидации
    показывается ровно то, что ввели, включая дефолты модели у новой точки."""
    return TemplateResponse(request, 'backoffice/stores/form.html', {
        'store': store, 'is_new': is_new, 'cities': _cities(),
    })


class OfflineStoreCreateView(StoreManagerSectionMixin, View):
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


class OfflineStoreEditView(StoreManagerSectionMixin, View):
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


class OfflineStoreDeleteView(StoreManagerSectionMixin, View):
    def post(self, request, pk):
        store = get_object_or_404(OfflineStore, pk=pk)
        store.delete()
        messages.success(request, 'Точка удалена.')
        return redirect('backoffice:store_list')


class ParseGisUrlView(StoreManagerSectionMixin, View):
    """Координаты из ссылки 2ГИС для живого автозаполнения формы точки.

    Разбор — тот же `coords_from_2gis`, что и при сохранении: второго парсера
    таких ссылок в проекте быть не должно (Р-4), в том числе на JS. В сеть не
    ходит, только разбирает строку.
    """

    # Ссылка 2ГИС на порядок короче; длинная строка — мусор, координат в ней нет
    MAX_URL_LENGTH = 2048

    def get(self, request):
        url = request.GET.get('url', '').strip()[:self.MAX_URL_LENGTH]
        try:
            pair = OfflineStore.coords_from_2gis(url)
        except ValueError:
            # urlsplit бросает на битом адресе (например, незакрытая скобка
            # IPv6-хоста) — для формы это просто «не разобралось», не 500
            pair = None
        if not pair:
            return JsonResponse({'found': False})
        lat, lng = pair
        # Строки с шестью знаками — ровно то, что печатает форма
        return JsonResponse({'found': True, 'lat': f'{lat:.6f}', 'lng': f'{lng:.6f}'})
