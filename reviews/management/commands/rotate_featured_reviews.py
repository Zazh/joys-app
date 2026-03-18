import hashlib
import logging

from django.core.management.base import BaseCommand
from django.db.models import Q, Value
from django.db.models.functions import Length
from django.utils import timezone

from reviews.models import Review

logger = logging.getLogger(__name__)

POSITIVE_LIMIT = 35
NEGATIVE_LIMIT = 20


class Command(BaseCommand):
    help = (
        'Ежедневная ротация отзывов на сайте: '
        f'{POSITIVE_LIMIT} положительных + {NEGATIVE_LIMIT} отрицательных. '
        'Закреплённые (is_pinned) сохраняются всегда.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--seed', type=str, default='',
            help='Seed для рандомизации (по умолчанию — текущая дата YYYY-MM-DD).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Показать что будет сделано, без изменений.',
        )

    def handle(self, *args, **options):
        seed = options['seed'] or timezone.localdate().isoformat()
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(f'[DRY RUN] Seed: {seed}')
        else:
            self.stdout.write(f'Seed: {seed}')

        # --- 1. Сбросить автоматически выбранные (не pinned) ---
        if not dry_run:
            cleared = Review.objects.filter(
                is_featured=True, is_pinned=False,
            ).update(is_featured=False)
            self.stdout.write(f'Сброшено авто-отзывов: {cleared}')

        # --- 2. Убедиться что все pinned → featured ---
        if not dry_run:
            pinned_updated = Review.objects.filter(
                is_pinned=True, is_featured=False,
            ).update(is_featured=True)
            if pinned_updated:
                self.stdout.write(f'Закреплённых активировано: {pinned_updated}')

        # --- 3. Подсчёт закреплённых ---
        pinned_positive = Review.objects.filter(
            is_pinned=True, rating__gte=4,
        ).count()
        pinned_negative = Review.objects.filter(
            is_pinned=True, rating__lte=2,
        ).count()

        need_positive = max(0, POSITIVE_LIMIT - pinned_positive)
        need_negative = max(0, NEGATIVE_LIMIT - pinned_negative)

        self.stdout.write(
            f'Закреплённые: {pinned_positive} полож. + {pinned_negative} отриц. | '
            f'Нужно добрать: {need_positive} полож. + {need_negative} отриц.'
        )

        # --- 4. Рандомная выборка с детерминированным seed ---
        # Используем MD5(seed + wb_id) для стабильной рандомизации в рамках дня
        def pick_random(queryset, count, seed_str):
            if count <= 0:
                return []
            ids_list = list(queryset.values_list('id', 'wb_id'))
            # Сортируем по хешу seed+wb_id — детерминированный рандом
            ids_list.sort(
                key=lambda x: hashlib.md5(
                    f'{seed_str}:{x[1]}'.encode()
                ).hexdigest()
            )
            return [item[0] for item in ids_list[:count]]

        # Положительные: rating >= 4 (4-5 звёзд), не pinned, не featured, не excluded, с контентом
        positive_pool = Review.objects.with_content().filter(
            rating__gte=4, is_pinned=False, is_featured=False, is_excluded=False,
        )
        selected_positive = pick_random(positive_pool, need_positive, seed)

        # Отрицательные: rating <= 2 (1-2 звезды), не pinned, не featured, не excluded, с контентом
        negative_pool = Review.objects.with_content().filter(
            rating__lte=2, is_pinned=False, is_featured=False, is_excluded=False,
        )
        selected_negative = pick_random(negative_pool, need_negative, seed)

        self.stdout.write(
            f'Выбрано рандомно: {len(selected_positive)} полож. + '
            f'{len(selected_negative)} отриц.'
        )

        # --- 5. Установить is_featured ---
        all_selected = selected_positive + selected_negative
        if all_selected and not dry_run:
            Review.objects.filter(id__in=all_selected).update(is_featured=True)

        # --- Итого ---
        if not dry_run:
            total = Review.objects.filter(is_featured=True).count()
            pos = Review.objects.filter(is_featured=True, rating__gte=4).count()
            neg = Review.objects.filter(is_featured=True, rating__lte=2).count()
            self.stdout.write(self.style.SUCCESS(
                f'Итого на сайте: {total} ({pos} полож. + {neg} отриц.)'
            ))
        else:
            self.stdout.write('[DRY RUN] Изменения не применены.')
