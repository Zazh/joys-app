from django.test import TestCase

from catalog.models import Category, Product

from .models import QuizRule, QuizSubmission

# Строка из quiz/views.py (FP-01) и её перевод из locale/en (Р-6)
NO_MATCH_RU = 'Не нашли подходящий товар. Попробуйте изменить ответы.'
NO_MATCH_EN = "We couldn't find a matching product. Try changing your answers."

ANSWERS = {'q1': 'texture', 'q2': 'banana', 'q3': 'daily', 'q4': 'yes'}


class QuizEmptyResultTest(TestCase):
    """FP-01: пустой подбор отвечает локализованной строкой, а не англ. хардкодом.

    Таблица `QuizRule` пуста — ни одно правило не совпадает. URL внутри
    `i18n_patterns`, язык ответа задаёт префикс страницы.
    """

    def test_ru_returns_localized_error(self):
        response = self.client.post('/ru/quiz/result/', ANSWERS)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['ok'])
        self.assertEqual(data['error'], NO_MATCH_RU)

    def test_en_returns_translated_error(self):
        """Сверяет именно перевод — заодно ловит несобранный .mo."""
        response = self.client.post('/en/quiz/result/', ANSWERS)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['error'], NO_MATCH_EN)

    def test_submission_saved_on_empty_result(self):
        """Аналитика пишется и при пустом подборе (существующее поведение)."""
        self.client.post('/ru/quiz/result/', ANSWERS)
        submission = QuizSubmission.objects.get()
        self.assertIsNone(submission.result_product)
        self.assertEqual(submission.q1, 'texture')


class QuizHappyPathTest(TestCase):
    """Правило + товар → ok: True (подбор — не предмет FP-01, фикстура минимальна)."""

    @classmethod
    def setUpTestData(cls):
        category = Category.objects.create(name='Презервативы', slug='condoms')
        cls.product = Product.objects.create(
            name='Классика', slug='klassika', category=category,
        )
        # Пустые условия = «любой ответ»
        QuizRule.objects.create(product=cls.product)

    def test_matching_rule_returns_product(self):
        response = self.client.post('/ru/quiz/result/', ANSWERS)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['products'][0]['slug'], 'klassika')
        self.assertEqual(
            QuizSubmission.objects.get().result_product, self.product,
        )
