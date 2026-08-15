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
