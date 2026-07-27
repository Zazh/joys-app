import json
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, RequestFactory

from accounts.models import User
from core.ratelimit import get_client_ip


class ClientIPTest(TestCase):
    """X-Forwarded-For подделывается клиентом — доверяем только своему прокси."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_ip_from_remote_addr_when_no_xff(self):
        request = self.factory.get('/', REMOTE_ADDR='10.0.0.5')
        self.assertEqual(get_client_ip(request), '10.0.0.5')

    def test_ip_taken_from_proxy_not_from_client(self):
        """nginx дописывает реальный IP в конец — берём его, а не первый."""
        request = self.factory.get(
            '/',
            REMOTE_ADDR='172.18.0.2',
            HTTP_X_FORWARDED_FOR='1.2.3.4, 203.0.113.77',
        )
        self.assertEqual(get_client_ip(request), '203.0.113.77')

    def test_forged_xff_cannot_change_identity(self):
        """Меняя свою часть заголовка, атакующий остаётся тем же клиентом."""
        ips = set()
        for forged in ('9.9.9.1', '9.9.9.2', '9.9.9.3'):
            request = self.factory.get(
                '/',
                REMOTE_ADDR='172.18.0.2',
                HTTP_X_FORWARDED_FOR=f'{forged}, 203.0.113.77',
            )
            ips.add(get_client_ip(request))
        self.assertEqual(ips, {'203.0.113.77'})

    def test_single_value_xff(self):
        request = self.factory.get(
            '/', REMOTE_ADDR='172.18.0.2', HTTP_X_FORWARDED_FOR='203.0.113.77',
        )
        self.assertEqual(get_client_ip(request), '203.0.113.77')


class AuthRateLimitTest(TestCase):
    """Публичные формы авторизации должны иметь лимит."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(email='u@example.com', password='CorrectHorse42!')

    def tearDown(self):
        cache.clear()

    def _login(self, password='wrong-password', xff='203.0.113.10'):
        return self.client.post(
            '/ru/accounts/login/',
            data=json.dumps({'email': 'u@example.com', 'password': password}),
            content_type='application/json',
            HTTP_X_FORWARDED_FOR=xff,
        )

    def test_login_brute_force_is_blocked(self):
        for _ in range(10):
            self.assertEqual(self._login().status_code, 401)

        # 11-я попытка — уже отказ по лимиту
        self.assertEqual(self._login().status_code, 429)

    def test_login_limit_survives_forged_xff(self):
        """Подмена своей части XFF не должна сбрасывать счётчик."""
        for i in range(10):
            self._login(xff=f'9.9.9.{i}, 203.0.113.10')

        response = self._login(xff='9.9.9.250, 203.0.113.10')
        self.assertEqual(response.status_code, 429)

    def test_successful_login_clears_counter(self):
        for _ in range(3):
            self._login()

        response = self._login(password='CorrectHorse42!')
        self.assertEqual(response.status_code, 200)

        # Счётчик сброшен — снова доступны все попытки
        self.client.logout()
        self.assertEqual(self._login().status_code, 401)

    @patch('accounts.views.send_password_reset')
    def test_password_reset_is_limited(self, mock_send):
        for _ in range(3):
            response = self.client.post(
                '/ru/accounts/password-reset/',
                data=json.dumps({'email': 'u@example.com'}),
                content_type='application/json',
                HTTP_X_FORWARDED_FOR='203.0.113.11',
            )
            self.assertEqual(response.status_code, 200)

        response = self.client.post(
            '/ru/accounts/password-reset/',
            data=json.dumps({'email': 'u@example.com'}),
            content_type='application/json',
            HTTP_X_FORWARDED_FOR='203.0.113.11',
        )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(mock_send.call_count, 3)
