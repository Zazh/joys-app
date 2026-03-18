from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from .models import QRCode
from .utils import generate_zip, transliterate


@staff_member_required
def download_qr_zip(request, pk):
    """Скачать ZIP с QR-кодами."""
    qr = get_object_or_404(QRCode, pk=pk)
    slug = transliterate(qr.title or 'qr')

    zip_bytes = generate_zip(qr.content, slug)

    response = HttpResponse(zip_bytes, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{slug}-qr.zip"'
    return response
