from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, CreateView, DetailView

from qrcodes.models import QRCode
from qrcodes.utils import generate_preview, generate_zip, transliterate
from ..mixins import BackofficeAccessMixin


class QRCodeListView(BackofficeAccessMixin, ListView):
    model = QRCode
    template_name = 'backoffice/qrcodes/list.html'
    context_object_name = 'qrcodes'
    paginate_by = 25
    ordering = ['-created_at']


class QRCodeCreateView(BackofficeAccessMixin, View):
    def get(self, request):
        from django.template.response import TemplateResponse
        return TemplateResponse(request, 'backoffice/qrcodes/create.html')

    def post(self, request):
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()

        if not content:
            from django.template.response import TemplateResponse
            return TemplateResponse(request, 'backoffice/qrcodes/create.html', {
                'error': 'Введите содержимое QR-кода',
                'title': title,
                'content': content,
            })

        qr = QRCode(title=title, content=content)
        slug = transliterate(title or 'qr')
        preview = generate_preview(content)
        qr.preview.save(f'{slug}.png', preview, save=False)
        qr.save()

        return redirect('backoffice:qrcode_detail', pk=qr.pk)


class QRCodeDetailView(BackofficeAccessMixin, DetailView):
    model = QRCode
    template_name = 'backoffice/qrcodes/detail.html'
    context_object_name = 'qr'


class QRCodeDeleteView(BackofficeAccessMixin, View):
    def post(self, request, pk):
        qr = get_object_or_404(QRCode, pk=pk)
        qr.delete()
        return redirect('backoffice:qrcode_list')


class QRCodeDownloadView(BackofficeAccessMixin, View):
    def get(self, request, pk):
        qr = get_object_or_404(QRCode, pk=pk)
        slug = transliterate(qr.title or 'qr')
        zip_bytes = generate_zip(qr.content, slug)
        response = HttpResponse(zip_bytes, content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{slug}-qr.zip"'
        return response
