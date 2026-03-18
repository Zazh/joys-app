import datetime
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from reviews.models import Review


class CardTypeTest(TestCase):
    """Тест определения типа карточки по контенту отзыва."""

    def _make_review(self, **kwargs):
        defaults = {
            'wb_id': f'test-{id(kwargs)}',
            'rating': 5,
            'wb_created_at': timezone.now(),
        }
        defaults.update(kwargs)
        return Review(**defaults)

    def test_list_only_pros_and_cons(self):
        r = self._make_review(pros='Хорошо', cons='Плохо')
        self.assertEqual(r.card_type, Review.CARD_LIST)

    def test_list_only_pros(self):
        r = self._make_review(pros='Хорошо')
        self.assertEqual(r.card_type, Review.CARD_LIST)

    def test_list_only_cons(self):
        r = self._make_review(cons='Плохо')
        self.assertEqual(r.card_type, Review.CARD_LIST)

    def test_text_list_tags(self):
        r = self._make_review(
            text='Отличный товар', pros='Качество', tags=['тег1', 'тег2'],
        )
        self.assertEqual(r.card_type, Review.CARD_TEXT_LIST_TAGS)

    def test_text_list_tags_all_fields(self):
        r = self._make_review(
            text='Текст', pros='Плюсы', cons='Минусы',
            tags=[{'name': 'тег'}],
        )
        self.assertEqual(r.card_type, Review.CARD_TEXT_LIST_TAGS)

    def test_text_tags(self):
        r = self._make_review(text='Текст отзыва', tags=['тег1'])
        self.assertEqual(r.card_type, Review.CARD_TEXT_TAGS)

    def test_text_list(self):
        r = self._make_review(text='Текст', pros='Плюсы')
        self.assertEqual(r.card_type, Review.CARD_TEXT_LIST)

    def test_text_list_cons_only(self):
        r = self._make_review(text='Текст', cons='Минусы')
        self.assertEqual(r.card_type, Review.CARD_TEXT_LIST)

    def test_text_only(self):
        r = self._make_review(text='Просто текст')
        self.assertEqual(r.card_type, Review.CARD_TEXT)

    def test_empty_content(self):
        r = self._make_review()
        self.assertEqual(r.card_type, Review.CARD_TEXT)

    def test_empty_strings_ignored(self):
        r = self._make_review(text='', pros='', cons='', tags=[])
        self.assertEqual(r.card_type, Review.CARD_TEXT)

    def test_has_list_true(self):
        r = self._make_review(pros='Есть')
        self.assertTrue(r.has_list)

    def test_has_list_false(self):
        r = self._make_review(text='Только текст')
        self.assertFalse(r.has_list)

    def test_formatted_tags_strings(self):
        r = self._make_review(tags=['тег1', 'тег2'])
        self.assertEqual(r.formatted_tags, ['тег1', 'тег2'])

    def test_formatted_tags_dicts(self):
        r = self._make_review(tags=[{'name': 'качество'}, {'name': 'цена'}])
        self.assertEqual(r.formatted_tags, ['качество', 'цена'])

    def test_formatted_tags_empty(self):
        r = self._make_review(tags=[])
        self.assertEqual(r.formatted_tags, [])

    def test_formatted_date(self):
        dt = timezone.datetime(2025, 11, 24, tzinfo=datetime.timezone.utc)
        r = self._make_review(wb_created_at=dt)
        self.assertEqual(r.formatted_date, '24 нояб. 2025')

    def test_formatted_date_january(self):
        dt = timezone.datetime(2026, 1, 5, tzinfo=datetime.timezone.utc)
        r = self._make_review(wb_created_at=dt)
        self.assertEqual(r.formatted_date, '5 янв. 2026')

    def test_content_length(self):
        r = self._make_review(text='abc', pros='de', cons='f')
        self.assertEqual(r.content_length, 6)

    def test_content_length_empty(self):
        r = self._make_review()
        self.assertEqual(r.content_length, 0)


class WithContentQuerySetTest(TestCase):
    """Тест фильтра with_content() — исключение пустых и коротких отзывов."""

    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        # Нормальный контент (>= 20 символов)
        Review.objects.create(
            wb_id='good-text', rating=5, wb_created_at=now,
            text='Отличный товар, рекомендую всем покупателям!',
        )
        Review.objects.create(
            wb_id='good-pros', rating=5, wb_created_at=now,
            pros='Качество супер, очень приятно',
        )
        Review.objects.create(
            wb_id='good-combined', rating=4, wb_created_at=now,
            text='Норм', pros='Хорошо сделано',  # 4 + 15 = 19 < 20
        )
        # Слишком короткий (< 20 символов)
        Review.objects.create(wb_id='short-1', rating=5, wb_created_at=now, text='Топ')
        Review.objects.create(wb_id='short-2', rating=5, wb_created_at=now, pros='👍')
        Review.objects.create(wb_id='short-3', rating=5, wb_created_at=now, text='Норм')
        # Пустой (только оценка)
        Review.objects.create(wb_id='empty-1', rating=5, wb_created_at=now)

    def test_with_content_excludes_short_and_empty(self):
        self.assertEqual(Review.objects.with_content().count(), 2)

    def test_total_includes_all(self):
        self.assertEqual(Review.objects.count(), 7)

    def test_short_not_in_with_content(self):
        ids = set(Review.objects.with_content().values_list('wb_id', flat=True))
        self.assertNotIn('short-1', ids)
        self.assertNotIn('short-2', ids)
        self.assertNotIn('empty-1', ids)
        self.assertIn('good-text', ids)
        self.assertIn('good-pros', ids)


class RotateFeaturedReviewsTest(TestCase):
    """Тест management command rotate_featured_reviews."""

    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        # 40 положительных с текстом (rating 5)
        for i in range(40):
            Review.objects.create(
                wb_id=f'pos-{i}', rating=5, wb_created_at=now,
                text=f'Положительный отзыв номер {i}, хороший товар',
            )
        # 25 отрицательных с текстом (rating 2)
        for i in range(25):
            Review.objects.create(
                wb_id=f'neg-{i}', rating=2, wb_created_at=now,
                text=f'Отрицательный отзыв номер {i}, плохой товар',
            )
        # 10 пустых (только оценка) — не должны попадать в ротацию
        for i in range(10):
            Review.objects.create(
                wb_id=f'empty-{i}', rating=5, wb_created_at=now,
            )

    def _rotate(self, seed='test-seed'):
        out = StringIO()
        call_command('rotate_featured_reviews', seed=seed, stdout=out)
        return out.getvalue()

    def test_creates_30_positive_20_negative(self):
        self._rotate()
        pos = Review.objects.filter(is_featured=True, rating__gte=4).count()
        neg = Review.objects.filter(is_featured=True, rating__lt=4).count()
        self.assertEqual(pos, 30)
        self.assertEqual(neg, 20)

    def test_total_featured_50(self):
        self._rotate()
        self.assertEqual(Review.objects.filter(is_featured=True).count(), 50)

    def test_same_seed_same_result(self):
        self._rotate(seed='day-1')
        ids_1 = set(
            Review.objects.filter(is_featured=True).values_list('id', flat=True)
        )
        # Сбросим и повторим
        Review.objects.update(is_featured=False)
        self._rotate(seed='day-1')
        ids_2 = set(
            Review.objects.filter(is_featured=True).values_list('id', flat=True)
        )
        self.assertEqual(ids_1, ids_2)

    def test_different_seed_different_result(self):
        self._rotate(seed='day-1')
        ids_1 = set(
            Review.objects.filter(is_featured=True).values_list('id', flat=True)
        )
        Review.objects.update(is_featured=False)
        self._rotate(seed='day-2')
        ids_2 = set(
            Review.objects.filter(is_featured=True).values_list('id', flat=True)
        )
        # Не гарантировано 100% разные, но крайне вероятно
        self.assertNotEqual(ids_1, ids_2)

    def test_pinned_always_included(self):
        # Закрепляем 5 положительных вручную
        pinned = Review.objects.filter(rating=5)[:5]
        pinned_ids = set(pinned.values_list('id', flat=True))
        Review.objects.filter(id__in=pinned_ids).update(
            is_pinned=True, is_featured=True,
        )

        self._rotate()

        featured_ids = set(
            Review.objects.filter(is_featured=True).values_list('id', flat=True)
        )
        # Все pinned должны быть в featured
        self.assertTrue(pinned_ids.issubset(featured_ids))

        # Положительных всё ещё 30 (5 pinned + 25 random)
        pos = Review.objects.filter(is_featured=True, rating__gte=4).count()
        self.assertEqual(pos, 30)

        # Cleanup
        Review.objects.filter(id__in=pinned_ids).update(is_pinned=False)

    def test_pinned_negative_reduces_random(self):
        # Закрепляем 8 отрицательных
        pinned = Review.objects.filter(rating=2)[:8]
        pinned_ids = set(pinned.values_list('id', flat=True))
        Review.objects.filter(id__in=pinned_ids).update(
            is_pinned=True, is_featured=True,
        )

        self._rotate()

        neg = Review.objects.filter(is_featured=True, rating__lt=4).count()
        self.assertEqual(neg, 20)  # 8 pinned + 12 random = 20

        # Cleanup
        Review.objects.filter(id__in=pinned_ids).update(is_pinned=False)

    def test_rerun_clears_old_auto(self):
        self._rotate(seed='day-1')
        auto_day1 = set(
            Review.objects.filter(
                is_featured=True, is_pinned=False,
            ).values_list('id', flat=True)
        )
        self._rotate(seed='day-2')
        auto_day2 = set(
            Review.objects.filter(
                is_featured=True, is_pinned=False,
            ).values_list('id', flat=True)
        )
        # Старые авто-отзывы должны быть сброшены (набор поменялся)
        self.assertNotEqual(auto_day1, auto_day2)

    def test_dry_run_no_changes(self):
        out = StringIO()
        call_command('rotate_featured_reviews', seed='test', dry_run=True, stdout=out)
        self.assertEqual(Review.objects.filter(is_featured=True).count(), 0)
        self.assertIn('DRY RUN', out.getvalue())

    def test_empty_reviews_excluded(self):
        """Пустые отзывы (только оценка) не попадают в ротацию."""
        self._rotate()
        empty_featured = Review.objects.filter(
            is_featured=True, text='', pros='', cons='',
        ).count()
        self.assertEqual(empty_featured, 0)


class FeaturedOrderingTest(TestCase):
    """Тест что самый длинный отзыв идёт первым."""

    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        Review.objects.create(
            wb_id='short', rating=5, is_featured=True,
            text='Нормальный отзыв, всё ок', wb_created_at=now,
        )
        Review.objects.create(
            wb_id='long', rating=5, is_featured=True,
            text='Очень длинный текст отзыва ' * 20,
            pros='Много достоинств ' * 10,
            wb_created_at=now,
        )
        Review.objects.create(
            wb_id='medium', rating=5, is_featured=True,
            text='Средний текст отзыва, хороший товар ' * 5,
            wb_created_at=now,
        )

    def test_longest_first(self):
        from reviews.templatetags.review_tags import get_featured_reviews
        reviews = get_featured_reviews()
        self.assertEqual(len(reviews), 3)
        self.assertEqual(reviews[0].wb_id, 'long')
        self.assertEqual(reviews[1].wb_id, 'medium')
        self.assertEqual(reviews[2].wb_id, 'short')
