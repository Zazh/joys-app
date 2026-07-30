from django.contrib import messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.views import View

from backoffice.forms import ContactSettingsForm
from backoffice.mixins import BackofficeAccessMixin
from pages.models import ContactSettings


class ContactsEditView(BackofficeAccessMixin, View):
    """Контакты компании (docs/contact_settings.md §6).

    Модель — синглтон, поэтому раздел без списка: одна страница, GET рисует форму,
    POST сохраняет и редиректит на себя. Кеш контактов сбрасывает сигнал в
    pages/apps.py, так что правка видна на сайте сразу.
    """

    template_name = 'backoffice/contacts/form.html'

    def get(self, request):
        return self._render(request, ContactSettingsForm(instance=ContactSettings.load()))

    def post(self, request):
        form = ContactSettingsForm(request.POST, instance=ContactSettings.load())
        if not form.is_valid():
            messages.error(request, 'Контакты не сохранены — проверьте поля с ошибками.')
            return self._render(request, form)
        form.save()
        messages.success(request, 'Контакты сохранены.')
        return redirect('backoffice:contacts')

    def _render(self, request, form):
        return TemplateResponse(request, self.template_name, {'form': form})
