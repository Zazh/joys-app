import logging
import time

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

from reviews.models import Review

logger = logging.getLogger(__name__)

WB_FEEDBACKS_URL = 'https://feedbacks-api.wildberries.ru/api/v1/feedbacks'
PAGE_SIZE = 5000  # Max WB allows

# nm_id товаров, которые не относятся к DR.JOYS (OTAKU SHOP и т.д.)
EXCLUDED_NM_IDS = {163395432, 112335360}


class Command(BaseCommand):
    help = 'Синхронизация отзывов с Wildberries Feedbacks API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--full', action='store_true',
            help='Полная синхронизация (все отзывы). По умолчанию — только новые.',
        )

    def handle(self, *args, **options):
        token = settings.WB_API_TOKEN
        if not token:
            self.stderr.write('WB_API_TOKEN не задан в настройках.')
            return

        full_sync = options['full']

        if full_sync:
            self.stdout.write('Полная синхронизация...')
        else:
            self.stdout.write('Синхронизация новых отзывов...')

        total_created = 0
        total_updated = 0

        # Синхронизируем оба типа: без ответа и с ответом
        for is_answered in [False, True]:
            label = 'с ответом' if is_answered else 'без ответа'
            created, updated = self._sync_feedbacks(token, is_answered, full_sync)
            self.stdout.write(f'  {label}: +{created} новых, {updated} обновлено')
            total_created += created
            total_updated += updated

        self.stdout.write(self.style.SUCCESS(
            f'Итого: +{total_created} новых, {total_updated} обновлено. '
            f'Всего в БД: {Review.objects.count()}'
        ))

    def _sync_feedbacks(self, token, is_answered, full_sync):
        created = 0
        updated = 0
        skip = 0

        while True:
            try:
                resp = requests.get(
                    WB_FEEDBACKS_URL,
                    params={
                        'isAnswered': str(is_answered).lower(),
                        'take': PAGE_SIZE,
                        'skip': skip,
                    },
                    headers={'Authorization': token},
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as e:
                logger.error('WB API error: %s', e)
                self.stderr.write(f'Ошибка API: {e}')
                break

            if data.get('error'):
                logger.error('WB API error: %s', data.get('errorText'))
                self.stderr.write(f'WB ошибка: {data.get("errorText")}')
                break

            feedbacks = data.get('data', {}).get('feedbacks', [])
            if not feedbacks:
                break

            for fb in feedbacks:
                c, u = self._upsert_review(fb, full_sync)
                created += c
                updated += u

            skip += len(feedbacks)

            # Если получили меньше чем запрашивали — это последняя страница
            if len(feedbacks) < PAGE_SIZE:
                break

            # Rate limiting
            time.sleep(0.5)

        return created, updated

    def _upsert_review(self, fb, full_sync):
        """Создать или обновить отзыв. Returns (created_count, updated_count)."""
        wb_id = fb.get('id', '')
        if not wb_id:
            return 0, 0

        pd = fb.get('productDetails', {})
        nm_id = pd.get('nmId')

        answer = fb.get('answer')

        defaults = {
            'nm_id': nm_id,
            'is_excluded': nm_id in EXCLUDED_NM_IDS,
            'product_name': pd.get('productName', ''),
            'supplier_article': pd.get('supplierArticle', ''),
            'user_name': fb.get('userName', ''),
            'rating': fb.get('productValuation', 0),
            'text': fb.get('text', ''),
            'pros': fb.get('pros', ''),
            'cons': fb.get('cons', ''),
            'tags': fb.get('bables') or [],
            'photos': fb.get('photoLinks') or [],
            'answer_text': answer.get('text', '') if answer else '',
            'wb_created_at': parse_datetime(fb['createdDate']),
        }

        existing = Review.objects.filter(wb_id=wb_id).first()

        if existing:
            if full_sync:
                for key, val in defaults.items():
                    setattr(existing, key, val)
                existing.save()
                return 0, 1
            return 0, 0
        else:
            Review.objects.create(wb_id=wb_id, **defaults)
            return 1, 0
