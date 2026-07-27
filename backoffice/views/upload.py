import os
import uuid

from django.conf import settings
from django.http import JsonResponse
from django.views import View
from PIL import Image, UnidentifiedImageError

from backoffice.mixins import BackofficeAccessMixin

# SVG сознательно не принимаем: файл отдаётся как image/svg+xml и может
# содержать <script>, который выполнится в origin сайта. Через это менеджер
# мог бы забрать сессию владельца.
ALLOWED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.webp')

# Что Pillow должен увидеть внутри файла — расширение ни о чём не говорит
ALLOWED_FORMATS = {'JPEG', 'PNG', 'GIF', 'WEBP'}

MAX_UPLOAD_SIZE = 5 * 1024 * 1024


class ImageUploadView(BackofficeAccessMixin, View):
    """TinyMCE image upload handler."""

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return JsonResponse({'error': 'Файл не найден'}, status=400)

        ext = os.path.splitext(file.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return JsonResponse({'error': 'Недопустимый формат'}, status=400)

        if file.size > MAX_UPLOAD_SIZE:
            return JsonResponse({'error': 'Файл слишком большой (макс 5 МБ)'}, status=400)

        # Проверяем содержимое, а не только имя файла
        try:
            image = Image.open(file)
            image.verify()
            image_format = (image.format or '').upper()
        except (UnidentifiedImageError, OSError, ValueError):
            return JsonResponse({'error': 'Файл не является изображением'}, status=400)

        if image_format not in ALLOWED_FORMATS:
            return JsonResponse({'error': 'Недопустимый формат изображения'}, status=400)

        file.seek(0)

        filename = f'{uuid.uuid4().hex}{ext}'
        rel_path = os.path.join('uploads', 'content', filename)
        abs_path = os.path.join(settings.MEDIA_ROOT, rel_path)

        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, 'wb+') as dest:
            for chunk in file.chunks():
                dest.write(chunk)

        url = f'{settings.MEDIA_URL}{rel_path}'
        return JsonResponse({'location': url})
