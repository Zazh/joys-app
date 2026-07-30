from django.contrib import messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.views import View

from backoffice.forms import ContactSettingsForm, ContactsPageForm
from backoffice.mixins import BackofficeAccessMixin
from pages.models import ContactSettings, Page

# Slug CMS-страницы контактов: из неё резолвится /contacts/ и на неё ссылается
# пункт меню, поэтому запись живёт, а редактируется отсюда (см. views/pages.py)
CONTACTS_PAGE_SLUG = 'contacts'


class ContactsEditView(BackofficeAccessMixin, View):
    """Контакты компании (docs/contact_settings.md §6).

    Две формы на одной странице: контакты (синглтон `ContactSettings`) и заголовок
    с мета-тегами страницы `/contacts/` (CMS-запись `Page`). Раздел без списка:
    GET рисует формы, POST сохраняет обе и редиректит на себя. Кеш контактов
    сбрасывает сигнал в pages/apps.py, так что правка видна на сайте сразу.

    SEO-формы может не быть: если CMS-записи нет (свежая база), редактор контактов
    всё равно должен открываться — блок просто не рисуется.
    """

    template_name = 'backoffice/contacts/form.html'

    def get(self, request):
        return self._render(request, *self._build())

    def post(self, request):
        form, seo_form = self._build(request.POST)
        # Список, а не all(...) с генератором: обе формы должны провалидироваться,
        # иначе ошибки второй не покажутся
        valid = [f.is_valid() for f in (form, seo_form) if f is not None]
        if not all(valid):
            messages.error(request, 'Контакты не сохранены — проверьте поля с ошибками.')
            return self._render(request, form, seo_form)
        form.save()
        if seo_form is not None:
            seo_form.save()
        messages.success(request, 'Контакты сохранены.')
        return redirect('backoffice:contacts')

    def _build(self, data=None):
        page = Page.objects.filter(slug=CONTACTS_PAGE_SLUG).first()
        return (
            ContactSettingsForm(data, instance=ContactSettings.load()),
            ContactsPageForm(data, instance=page, prefix='seo') if page else None,
        )

    def _render(self, request, form, seo_form):
        return TemplateResponse(request, self.template_name, {
            'form': form,
            'seo_form': seo_form,
        })
