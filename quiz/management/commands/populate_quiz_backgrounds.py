from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand

from quiz.models import QuizBackground


BACKGROUNDS = [
    ('banana', 'dist/images/modal-quizzes/bgs/banana.jpg', False),
    ('strawberry', 'dist/images/modal-quizzes/bgs/strawberry.jpg', False),
    ('chocolate', 'dist/images/modal-quizzes/bgs/chocolate.jpg', True),
    ('dotted-ribbed', 'dist/images/modal-quizzes/bgs/dotted-ribbed.jpg', False),
    ('triple-lube', 'dist/images/modal-quizzes/bgs/triple-lube.jpg', False),
]


class Command(BaseCommand):
    help = 'Заполнить фоны квиза из static-файлов'

    def handle(self, *args, **options):
        static_root = Path(settings.BASE_DIR) / 'static'

        created = 0
        skipped = 0
        for key, rel_path, is_dark in BACKGROUNDS:
            if QuizBackground.objects.filter(key=key).exists():
                skipped += 1
                continue

            src = static_root / rel_path
            if not src.exists():
                self.stderr.write(self.style.WARNING(f'Файл не найден: {src}'))
                skipped += 1
                continue

            with open(src, 'rb') as f:
                bg = QuizBackground(key=key, is_dark_theme=is_dark)
                bg.image.save(src.name, File(f), save=True)
                created += 1
                self.stdout.write(f'  + {key} (dark={is_dark})')

        self.stdout.write(self.style.SUCCESS(f'Создано: {created}, пропущено: {skipped}'))
