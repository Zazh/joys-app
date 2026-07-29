"""Тест-раннер, изолирующий кеш от рабочего окружения.

БД для тестов Django создаёт свою, а вот кеш берёт из настроек — то есть тот же
Redis, что у дева и прода. Любой тест, который отрисует страницу, положит в общий
кеш результат, посчитанный по пустой тестовой базе: навигация пропадает из шапки
и футера на 10 минут (`navigation_data`), блок отзывов на главной — на сутки
(`home_review_stats`, `home_featured_reviews`). Сессии тоже живут в кеше
(`SESSION_ENGINE = cached_db`).

Поэтому на время прогона подменяем кеш на локальный в памяти. Отдельные тесты
могут по-прежнему делать свой `override_settings(CACHES=...)` — этот работает
уровнем выше и на них не влияет.
"""
from django.test.runner import DiscoverRunner
from django.test.utils import override_settings

LOCAL_CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'drjoys-tests',
    }
}


class IsolatedCacheRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        self._caches = override_settings(CACHES=LOCAL_CACHES)
        self._caches.enable()
        super().setup_test_environment(**kwargs)

    def teardown_test_environment(self, **kwargs):
        super().teardown_test_environment(**kwargs)
        self._caches.disable()
