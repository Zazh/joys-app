import io
import re
import zipfile

import qrcode
import qrcode.image.svg
from PIL import Image
from django.core.files.base import ContentFile

PREVIEW_SIZE = 512
TRANSLITERATION = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    'ә': 'a', 'ғ': 'g', 'қ': 'q', 'ң': 'n', 'ө': 'o', 'ұ': 'u',
    'ү': 'u', 'һ': 'h', 'і': 'i',
}


def transliterate(text):
    """Транслитерация кириллицы → латиница, удаление спецсимволов."""
    result = []
    for ch in text.lower():
        if ch in TRANSLITERATION:
            result.append(TRANSLITERATION[ch])
        elif ch.isascii() and (ch.isalnum() or ch in '-_ '):
            result.append(ch)
    slug = ''.join(result).strip()
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug[:60] or 'qr'


def _make_qr(content):
    """Создаёт объект QRCode."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(content)
    qr.make(fit=True)
    return qr


def generate_png(content, size=PREVIEW_SIZE, transparent=False):
    """Генерирует QR PNG заданного размера."""
    qr = _make_qr(content)
    img = qr.make_image(fill_color='black', back_color='white').convert('RGBA')
    img = img.resize((size, size), Image.NEAREST)

    if transparent:
        pixels = img.load()
        for y in range(img.height):
            for x in range(img.width):
                if pixels[x, y] == (255, 255, 255, 255):
                    pixels[x, y] = (255, 255, 255, 0)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def generate_svg(content, transparent=False):
    """Генерирует QR SVG 512×512."""
    qr = _make_qr(content)
    if transparent:
        factory = qrcode.image.svg.SvgPathImage
    else:
        factory = qrcode.image.svg.SvgImage
    img = qr.make_image(image_factory=factory)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue()


def generate_preview(content):
    """Генерирует превью 512×512 как ContentFile."""
    png_bytes = generate_png(content, size=PREVIEW_SIZE, transparent=False)
    return ContentFile(png_bytes)


def generate_zip(content, slug='qr'):
    """Генерирует ZIP с QR в каталогах white/, transparent/, svg/."""
    sizes = {
        'sm': 256,
        'md': 512,
        'lg': 1024,
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for size_name, px in sizes.items():
            # PNG белый фон
            png = generate_png(content, size=px, transparent=False)
            zf.writestr(f'white/{slug}-{size_name}-{px}px.png', png)

            # PNG прозрачный фон
            png_t = generate_png(content, size=px, transparent=True)
            zf.writestr(f'transparent/{slug}-{size_name}-{px}px.png', png_t)

        # SVG
        svg_white = generate_svg(content, transparent=False)
        zf.writestr(f'svg/{slug}-white.svg', svg_white)

        svg_transparent = generate_svg(content, transparent=True)
        zf.writestr(f'svg/{slug}-transparent.svg', svg_transparent)

    return buf.getvalue()
