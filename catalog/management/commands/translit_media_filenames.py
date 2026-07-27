"""
Переименование существующих медиафайлов с кириллицей на латиницу.

Идёт по всем FileField всех моделей (включая переводные поля
modeltranslation), переименовывает файл на диске и обновляет путь в БД
через queryset.update() — без сигналов и повторной WebP-конвертации.
"""
import os

from django.apps import apps
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.db.models import FileField

from core.storage import translit_filename


class Command(BaseCommand):
    help = 'Переименовать медиафайлы с кириллицей в латиницу и обновить пути в БД'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Показать план без изменений')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        renamed = skipped = missing = 0

        for model in apps.get_models():
            file_fields = [
                f.name for f in model._meta.get_fields()
                if isinstance(f, FileField)
            ]
            if not file_fields:
                continue

            for obj in model._base_manager.all():
                updates = {}
                for field_name in file_fields:
                    f = getattr(obj, field_name, None)
                    if not f or not f.name or f.name.isascii():
                        continue

                    dirname, basename = os.path.split(f.name)
                    new_basename = translit_filename(basename)
                    new_rel = os.path.join(dirname, new_basename)
                    if new_rel == f.name:
                        continue

                    try:
                        old_path = f.path
                    except Exception:
                        skipped += 1
                        continue

                    if not os.path.exists(old_path):
                        self.stdout.write(self.style.WARNING(
                            f'  НЕТ ФАЙЛА: {model.__name__}.{field_name} pk={obj.pk} {f.name}'
                        ))
                        missing += 1
                        continue

                    # Коллизия имён — берём свободное имя через storage
                    if default_storage.exists(new_rel):
                        new_rel = default_storage.get_available_name(new_rel)

                    label = f'{model.__name__}.{field_name} pk={obj.pk}'
                    self.stdout.write(f'  {label}: {f.name} -> {new_rel}')
                    if not dry_run:
                        new_path = default_storage.path(new_rel)
                        os.makedirs(os.path.dirname(new_path), exist_ok=True)
                        os.rename(old_path, new_path)
                        updates[field_name] = new_rel
                    renamed += 1

                if updates and not dry_run:
                    model._base_manager.filter(pk=obj.pk).update(**updates)

        prefix = '[DRY RUN] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Переименовано: {renamed}, пропущено: {skipped}, без файла: {missing}'
        ))
