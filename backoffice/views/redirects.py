from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.views import View
from django.views.generic import ListView

from backoffice.mixins import BackofficeAccessMixin
from redirects.models import Redirect


class RedirectListView(BackofficeAccessMixin, ListView):
    template_name = 'backoffice/redirects/list.html'
    context_object_name = 'redirects'
    paginate_by = 25

    def get_queryset(self):
        qs = Redirect.objects.order_by('-created_at')

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(path__icontains=q) | Q(destination__icontains=q) | Q(note__icontains=q))

        active = self.request.GET.get('active')
        if active == 'yes':
            qs = qs.filter(is_active=True)
        elif active == 'no':
            qs = qs.filter(is_active=False)

        rtype = self.request.GET.get('type')
        if rtype in ('301', '302'):
            qs = qs.filter(redirect_type=int(rtype))

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['current_q'] = self.request.GET.get('q', '')
        ctx['current_active'] = self.request.GET.get('active', '')
        ctx['current_type'] = self.request.GET.get('type', '')
        return ctx


class RedirectCreateView(BackofficeAccessMixin, View):
    def get(self, request):
        return TemplateResponse(request, 'backoffice/redirects/form.html', {'redir': None})

    def post(self, request):
        redir = Redirect(
            path=request.POST.get('path', '').strip(),
            destination=request.POST.get('destination', '').strip(),
            redirect_type=int(request.POST.get('redirect_type', 301)),
            is_active=request.POST.get('is_active') == 'on',
            note=request.POST.get('note', '').strip(),
        )
        if not redir.path or not redir.destination:
            messages.error(request, 'Путь и назначение обязательны.')
            return TemplateResponse(request, 'backoffice/redirects/form.html', {
                'redir': None, 'post_data': request.POST,
            })
        redir.save()
        messages.success(request, f'Редирект «{redir.path}» создан.')
        return redirect('backoffice:redirect_list')


class RedirectEditView(BackofficeAccessMixin, View):
    def get(self, request, pk):
        redir = get_object_or_404(Redirect, pk=pk)
        return TemplateResponse(request, 'backoffice/redirects/form.html', {'redir': redir})

    def post(self, request, pk):
        redir = get_object_or_404(Redirect, pk=pk)
        redir.path = request.POST.get('path', '').strip()
        redir.destination = request.POST.get('destination', '').strip()
        redir.redirect_type = int(request.POST.get('redirect_type', 301))
        redir.is_active = request.POST.get('is_active') == 'on'
        redir.note = request.POST.get('note', '').strip()
        redir.save()
        messages.success(request, f'Редирект «{redir.path}» сохранён.')
        return redirect('backoffice:redirect_list')


class RedirectDeleteView(BackofficeAccessMixin, View):
    def post(self, request, pk):
        redir = get_object_or_404(Redirect, pk=pk)
        redir.delete()
        messages.success(request, 'Редирект удалён.')
        return redirect('backoffice:redirect_list')
