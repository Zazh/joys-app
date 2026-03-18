import io
from pathlib import Path

from PIL import Image
from django.core.files.uploadedfile import InMemoryUploadedFile


def optimize_image_field(
    image_field,
    max_width=None,
    max_height=None,
    quality=100,
    preserve_transparency=False,
):
    """
    Ресайзит и конвертирует ImageField.

    - max_width / max_height — ограничения (пропорционально, выбирается меньший масштаб)
    - preserve_transparency=True — сохраняет PNG с альфа-каналом (не WebP)
    - Иначе конвертирует в WebP
    """
    if not image_field:
        return None

    image_field.file.seek(0)
    img = Image.open(image_field.file)

    # Определяем нужен ли ресайз
    need_resize = False
    if max_width and img.width > max_width:
        need_resize = True
    if max_height and img.height > max_height:
        need_resize = True

    # Если уже в целевом формате и ресайз не нужен — пропускаем
    if preserve_transparency:
        if img.format == 'PNG' and not need_resize:
            image_field.file.seek(0)
            return None
    else:
        if img.format == 'WEBP' and not need_resize:
            image_field.file.seek(0)
            return None

    # Ресайз пропорционально (по наименьшему коэффициенту)
    if need_resize:
        ratio = 1.0
        if max_width and img.width > max_width:
            ratio = min(ratio, max_width / img.width)
        if max_height and img.height > max_height:
            ratio = min(ratio, max_height / img.height)
        new_width = int(img.width * ratio)
        new_height = int(img.height * ratio)
        img = img.resize((new_width, new_height), Image.LANCZOS)

    # Сохранение
    buffer = io.BytesIO()
    original_name = Path(image_field.name).stem

    if preserve_transparency:
        # Сохраняем как PNG с альфа-каналом
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        img.save(buffer, format='PNG', optimize=True)
        new_name = f'{original_name}.png'
        content_type = 'image/png'
    else:
        # Конвертируем в WebP (RGB)
        if img.mode in ('RGBA', 'P', 'LA'):
            img = img.convert('RGB')
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        img.save(buffer, format='WEBP', quality=quality, method=4)
        new_name = f'{original_name}.webp'
        content_type = 'image/webp'

    size = buffer.tell()
    buffer.seek(0)

    image_field.file.seek(0)

    return InMemoryUploadedFile(
        file=buffer,
        field_name=None,
        name=new_name,
        content_type=content_type,
        size=size,
        charset=None,
    )
