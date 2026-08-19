"""Города оффлайн-точек: CRUD по образцу редиректов.

Названия переводимые (modeltranslation), поэтому форма принимает тройку
name_ru/name_kk/name_en. Пустой перевод пишется как None, а не '': колонки
переводов уникальны, и вторая запись с пустой строкой упала бы на constraint —
при этом None и '' одинаково означают «перевода нет» и одинаково откатываются
на русское название (Р-6).
"""

from django.contrib import messages
from django.db import IntegrityError
from django.db.models import Count, ProtectedError
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.views import View
from django.views.generic import ListView

from backoffice.mixins import BackofficeAccessMixin
from pages.models import City


def _fill_city(city, request):
    """Названия из POST в объект; возвращает текст ошибки или None."""
    name_ru = request.POST.get('name_ru', '').strip()
    city.name_ru = name_ru
    city.name_kk = request.POST.get('name_kk', '').strip() or None
    city.name_en = request.POST.get('name_en', '').strip() or None

    if not name_ru:
        return 'Название на русском обязательно.'
    twin = City.objects.filter(name_ru__iexact=name_ru)
    if city.pk:
        twin = twin.exclude(pk=city.pk)
    if twin.exists():
        return f'Город «{name_ru}» уже есть в справочнике.'
    return None


def _form_response(request, city, is_new):
    return TemplateResponse(request, 'backoffice/cities/form.html', {
        'city': city, 'is_new': is_new,
    })


class CityListView(BackofficeAccessMixin, ListView):
    template_name = 'backoffice/cities/list.html'
    context_object_name = 'cities'
    paginate_by = 50

    def get_queryset(self):
        return City.objects.annotate(stores_count=Count('stores')).order_by('name')


class CityCreateView(BackofficeAccessMixin, View):
    def get(self, request):
        return _form_response(request, City(), is_new=True)

    def post(self, request):
        city = City()
        if error := _fill_city(city, request):
            messages.error(request, error)
            return _form_response(request, city, is_new=True)
        try:
            city.save()
        except IntegrityError:
            # Дубль ловится проверкой по name_ru, сюда доходит только повтор
            # казахского или английского названия — они тоже уникальны
            messages.error(request, 'Такое название уже занято другим городом.')
            return _form_response(request, city, is_new=True)
        messages.success(request, f'Город «{city.name_ru}» создан.')
        return redirect('backoffice:city_list')


class CityEditView(BackofficeAccessMixin, View):
    def get(self, request, pk):
        return _form_response(request, get_object_or_404(City, pk=pk), is_new=False)

    def post(self, request, pk):
        city = get_object_or_404(City, pk=pk)
        if error := _fill_city(city, request):
            messages.error(request, error)
            return _form_response(request, city, is_new=False)
        try:
            city.save()
        except IntegrityError:
            messages.error(request, 'Такое название уже занято другим городом.')
            return _form_response(request, city, is_new=False)
        messages.success(request, f'Город «{city.name_ru}» сохранён.')
        return redirect('backoffice:city_list')


class CityDeleteView(BackofficeAccessMixin, View):
    def post(self, request, pk):
        city = get_object_or_404(City, pk=pk)
        try:
            city.delete()
        except ProtectedError:
            # PROTECT у OfflineStore.city: удаление города утащило бы точки
            messages.error(
                request,
                f'Город нельзя удалить: к нему привязаны точки '
                f'({city.stores.count()} шт.).',
            )
        else:
            messages.success(request, 'Город удалён.')
        return redirect('backoffice:city_list')
