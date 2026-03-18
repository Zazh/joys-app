"""
Автоконвертация загруженных изображений в WebP.
- JPG/JPEG → WebP (quality=95)
- PNG → WebP (quality=95, прозрачность сохраняется)
- Заменяет оригинальный файл, обновляет поле модели.
"""
import os
from io import BytesIO
from pathlib import Path

from PIL import Image
from django.core.files.base import ContentFile
from django.db import models
from django.db.models.signals import post_save


CONVERTIBLE = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}

SKIP_MODELS = {'qrcodes.QRCode'}

# Защита от рекурсии
_processing = set()


def convert_to_webp(instance, field_name):
    """Конвертирует изображение в WebP и обновляет поле модели."""
    field_file = getattr(instance, field_name)
    if not field_file or not field_file.name:
        return False

    ext = Path(field_file.name).suffix.lower()
    if ext not in CONVERTIBLE:
        return False

    try:
        field_file.seek(0)
        img = Image.open(field_file)

        if img.mode == 'RGBA':
            pass
        else:
            img = img.convert('RGB')

        buf = BytesIO()
        img.save(buf, format='WEBP', quality=95, method=4)
        buf.seek(0)

        old_path = field_file.path
        new_path = str(Path(old_path).with_suffix('.webp'))

        # Записываем webp-файл напрямую на диск
        with open(new_path, 'wb') as f:
            f.write(buf.read())

        # Обновляем имя в поле (относительный путь от MEDIA_ROOT)
        from django.conf import settings
        rel_path = os.path.relpath(new_path, settings.MEDIA_ROOT)
        setattr(instance, field_name, rel_path)

        if os.path.exists(old_path) and old_path != new_path:
            try:
                os.remove(old_path)
            except OSError:
                pass

        return True
    except Exception:
        return False


def process_model_images(sender, instance, **kwargs):
    """Signal handler: конвертирует все ImageField модели в WebP."""
    model_label = f'{sender._meta.app_label}.{sender.__name__}'
    if model_label in SKIP_MODELS:
        return

    key = f'{model_label}:{instance.pk}'
    if key in _processing:
        return
    _processing.add(key)

    try:
        image_fields = [
            f.name for f in sender._meta.get_fields()
            if isinstance(f, models.ImageField)
        ]

        if not image_fields:
            return

        updated = False
        for field_name in image_fields:
            if convert_to_webp(instance, field_name):
                updated = True

        if updated:
            sender.objects.filter(pk=instance.pk).update(
                **{f: getattr(instance, f) for f in image_fields}
            )
    finally:
        _processing.discard(key)


# Приложения, для которых работает автоконвертация
PROJECT_APPS = {'catalog', 'pages', 'modals', 'quiz', 'reviews', 'orders', 'inquiries'}


def connect_signals():
    """Подключает post_save для всех моделей проектных приложений."""
    from django.apps import apps

    for app_label in PROJECT_APPS:
        try:
            app_models = apps.get_app_config(app_label).get_models()
            for model in app_models:
                has_images = any(
                    isinstance(f, models.ImageField)
                    for f in model._meta.get_fields()
                )
                if has_images:
                    post_save.connect(
                        process_model_images,
                        sender=model,
                        dispatch_uid=f'webp_{model._meta.label}',
                    )
        except LookupError:
            pass
