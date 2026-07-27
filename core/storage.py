"""
Хранилище с транслитерацией имён файлов.

Все загружаемые файлы получают безопасное латинское имя:
«Клубничный_перед.webp» → «klubnichnyy_pered.webp».
Без этого кириллица в URL превращается в percent-encoding,
ломает переносимость медиа и усложняет отладку.
"""
import os
import re
import unicodedata

from django.core.files.storage import FileSystemStorage

# Русский + казахский алфавит
TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    'ә': 'a', 'ғ': 'g', 'қ': 'q', 'ң': 'n', 'ө': 'o', 'ұ': 'u',
    'ү': 'u', 'і': 'i', 'һ': 'h',
}


def transliterate(text):
    return ''.join(TRANSLIT_MAP.get(ch, ch) for ch in text)


def translit_filename(name):
    """Безопасное латинское имя файла: транслит + [a-z0-9._-]."""
    # NFC склеивает разложенные символы (macOS отдаёт й как и + бреве)
    name = unicodedata.normalize('NFC', name)
    base, ext = os.path.splitext(name)
    base = transliterate(base.lower())
    base = re.sub(r'[^a-z0-9_-]+', '_', base)
    base = re.sub(r'_+', '_', base).strip('_-') or 'file'
    return f'{base}{ext.lower()}'


class TranslitFileSystemStorage(FileSystemStorage):
    def get_valid_name(self, name):
        return super().get_valid_name(translit_filename(name))
