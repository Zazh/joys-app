from django.test import TestCase

from .models import Redirect


class RedirectMiddlewareTest(TestCase):
    """Редиректы из БД: точное совпадение и толерантность к слэшу."""

    def test_exact_match(self):
        Redirect.objects.create(
            path='/give_bot/', destination='https://t.me/example_bot',
            redirect_type=301,
        )
        response = self.client.get('/give_bot/')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], 'https://t.me/example_bot')

    def test_entry_with_slash_catches_path_without_slash(self):
        Redirect.objects.create(
            path='/give_bot/', destination='https://t.me/example_bot',
            redirect_type=301,
        )
        response = self.client.get('/give_bot')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], 'https://t.me/example_bot')

    def test_entry_without_slash_catches_path_with_slash(self):
        Redirect.objects.create(
            path='/give_bot', destination='https://t.me/example_bot',
            redirect_type=301,
        )
        response = self.client.get('/give_bot/')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], 'https://t.me/example_bot')

    def test_exact_match_wins_over_slash_fallback(self):
        Redirect.objects.create(
            path='/promo', destination='https://example.com/no-slash',
            redirect_type=301,
        )
        Redirect.objects.create(
            path='/promo/', destination='https://example.com/with-slash',
            redirect_type=301,
        )
        response = self.client.get('/promo/')
        self.assertEqual(response['Location'], 'https://example.com/with-slash')
        response = self.client.get('/promo')
        self.assertEqual(response['Location'], 'https://example.com/no-slash')

    def test_temporary_redirect_type(self):
        Redirect.objects.create(
            path='/temp/', destination='https://example.com/',
            redirect_type=302,
        )
        response = self.client.get('/temp')
        self.assertEqual(response.status_code, 302)

    def test_permanent_redirect_has_bounded_cache(self):
        Redirect.objects.create(
            path='/perm/', destination='https://example.com/',
            redirect_type=301,
        )
        response = self.client.get('/perm/')
        self.assertEqual(response['Cache-Control'], 'max-age=3600')

    def test_temporary_redirect_not_cached(self):
        Redirect.objects.create(
            path='/tmp/', destination='https://example.com/',
            redirect_type=302,
        )
        response = self.client.get('/tmp/')
        self.assertNotIn('Cache-Control', response)

    def test_inactive_redirect_ignored(self):
        Redirect.objects.create(
            path='/off/', destination='https://example.com/',
            redirect_type=301, is_active=False,
        )
        response = self.client.get('/off/')
        self.assertNotEqual(response.status_code, 301)


class LanguagePrefixTest(TestCase):
    """Одна запись без префикса ловит и языковые варианты пути.

    Легаси-трафик (QR, печать) бьётся в `/ru/…`-варианты старых адресов:
    до этой правки запись `/foo/` их не ловила, и класс ошибки уже стоил
    705 потерянных заходов на `/ru/100-sex-positions/` (хотфикс 16.08.2026).
    """

    def setUp(self):
        Redirect.objects.create(
            path='/promo-page/', destination='https://t.me/example_bot',
            redirect_type=301,
        )

    def test_ru_prefix_caught(self):
        response = self.client.get('/ru/promo-page/')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], 'https://t.me/example_bot')

    def test_en_and_kk_prefixes_caught(self):
        for prefix in ('/en', '/kk'):
            response = self.client.get(f'{prefix}/promo-page/')
            self.assertEqual(response.status_code, 301, prefix)

    def test_prefix_and_missing_slash_caught(self):
        response = self.client.get('/ru/promo-page')
        self.assertEqual(response.status_code, 301)

    def test_exact_prefixed_entry_wins_over_stripped(self):
        Redirect.objects.create(
            path='/ru/promo-page/', destination='https://example.com/ru-special',
            redirect_type=301,
        )
        response = self.client.get('/ru/promo-page/')
        self.assertEqual(response['Location'], 'https://example.com/ru-special')
        # остальные префиксы по-прежнему падают в запись без префикса
        response = self.client.get('/en/promo-page/')
        self.assertEqual(response['Location'], 'https://t.me/example_bot')

    def test_bare_language_prefix_not_hijacked_by_root_entry(self):
        # запись для `/` не должна перехватывать языковые главные
        Redirect.objects.create(
            path='/', destination='https://example.com/root',
            redirect_type=301,
        )
        for path in ('/ru/', '/ru'):
            response = self.client.get(path, follow=False)
            self.assertNotEqual(
                response.get('Location'), 'https://example.com/root', path,
            )

    def test_unrelated_prefixed_page_untouched(self):
        # живые страницы с префиксом проходят мимо middleware
        response = self.client.get('/ru/nonexistent-page/')
        self.assertEqual(response.status_code, 404)
