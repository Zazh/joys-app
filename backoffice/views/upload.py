import os
import uuid

from django.conf import settings
from django.http import JsonResponse
from django.views import View

from backoffice.mixins import BackofficeAccessMixin


class ImageUploadView(BackofficeAccessMixin, View):
    """TinyMCE image upload handler."""

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return JsonResponse({'error': 'Файл не найден'}, status=400)

        ext = os.path.splitext(file.name)[1].lower()
        if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'):
            return JsonResponse({'error': 'Недопустимый формат'}, status=400)

        if file.size > 5 * 1024 * 1024:
            return JsonResponse({'error': 'Файл слишком большой (макс 5 МБ)'}, status=400)

        filename = f'{uuid.uuid4().hex}{ext}'
        rel_path = os.path.join('uploads', 'content', filename)
        abs_path = os.path.join(settings.MEDIA_ROOT, rel_path)

        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, 'wb+') as dest:
            for chunk in file.chunks():
                dest.write(chunk)

        url = f'{settings.MEDIA_URL}{rel_path}'
        return JsonResponse({'location': url})
