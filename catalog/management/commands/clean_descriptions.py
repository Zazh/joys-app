import re
from html import unescape

from django.core.management.base import BaseCommand
from django.utils.html import strip_tags

from catalog.models import Product


FIELDS = ['description_ru', 'description_kk', 'description_en']


def clean(text):
    """Убирает HTML-теги и расшифровывает HTML-entities, сохраняя переносы строк."""
    if not text:
        return text
    # Сохраняем переносы абзацев и <br> до strip_tags
    text = re.sub(r'</p\s*>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = strip_tags(text)
    text = unescape(text)
    # Нормализация пробелов внутри строк и схлопывание лишних пустых строк
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()]
    text = '\n'.join(lines)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text


class Command(BaseCommand):
    help = 'Одноразовая чистка description_* у товаров: убирает HTML-теги и спецсимволы.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Показать изменения, ничего не сохраняя.',
        )

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        to_update = []
        for product in Product.objects.all():
            changed = False
            for field in FIELDS:
                old = getattr(product, field) or ''
                new = clean(old)
                if new != old:
                    if dry:
                        self.stdout.write(f'pk={product.pk} {field}: {old[:80]!r} -> {new[:80]!r}')
                    setattr(product, field, new)
                    changed = True
            if changed and not dry:
                to_update.append(product)

        if dry:
            self.stdout.write(self.style.WARNING('Dry-run, ничего не сохранено.'))
            return

        if to_update:
            # bulk_update — минуем save() и сигналы (post_save для image-полей).
            Product.objects.bulk_update(to_update, FIELDS, batch_size=200)
        self.stdout.write(self.style.SUCCESS(f'Очищено товаров: {len(to_update)}'))
