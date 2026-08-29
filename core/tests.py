"""Тесты SEO-инфраструктуры: sitemap.xml, robots.txt, llms.txt, canonical.

Главное, что здесь проверяется, — что домен во всех этих ответах берётся из
SITE_URL, а не из хоста запроса. Это условие переезда app.dr-joys.com →
dr-joys.com одной правкой .env, и без теста оно тихо ломается при любом
рефакторинге.

Плюс конфигурация `core/settings.py`, которую больше негде проверить: секция
LOGGING (PH-01) и настройки пути денег — VTB_CALLBACK_TOKEN, PAYMENT_ALERT_EMAIL
(PH-04/PH-05).
"""
import importlib
import io
import json
import logging
import os
import re
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from catalog.models import Category, Product, ProductSize
from core.text import one_line
# Модулем, а не `from orders.tests import ...`: класс в неймспейсе core.tests
# тест-раннер собрал бы и прогнал второй раз целиком
from orders import tests as orders_tests
from pages.models import BlogPost, Page, PageCategory

PROD = 'https://dr-joys.com'
# Технический домен: с него приходит запрос, в ответе его быть не должно
STAGING_HOST = 'app.dr-joys.com'


@override_settings(SITE_URL=PROD, SITE_INDEXABLE=True, ALLOWED_HOSTS=['*'])
class SitemapTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name='Презервативы', slug='prezervativy')
        cls.product = Product.objects.create(
            name='Classic', slug='classic', category=cls.category,
        )
        cls.page = Page.objects.create(title='Оферта', slug='oferta')
        cls.hidden_page = Page.objects.create(
            title='Черновик', slug='draft', is_published=False,
        )
        cls.post = BlogPost.objects.create(
            title='Краш-тест', slug='krash-test', published_at='2026-07-01T10:00:00Z',
        )

    def get_sitemap(self):
        return self.client.get('/sitemap.xml', headers={'host': STAGING_HOST})

    def test_domain_comes_from_site_url_not_request_host(self):
        body = self.get_sitemap().content.decode()
        self.assertIn(f'{PROD}/ru/', body)
        self.assertNotIn(STAGING_HOST, body)

    def test_contains_all_sections(self):
        body = self.get_sitemap().content.decode()
        for path in (
            '/ru/',
            '/ru/catalog/',
            '/ru/blog/',
            '/ru/catalog/prezervativy/',
            '/ru/catalog/prezervativy/classic/',
            '/ru/oferta/',
            '/ru/blog/krash-test/',
        ):
            self.assertIn(f'<loc>{PROD}{path}</loc>', body)

    def test_every_url_has_three_language_versions(self):
        body = self.get_sitemap().content.decode()
        for lang in ('ru', 'kk', 'en'):
            self.assertIn(
                f'<xhtml:link rel="alternate" hreflang="{lang}" '
                f'href="{PROD}/{lang}/catalog/prezervativy/classic/"/>',
                body,
            )

    def test_unpublished_content_is_excluded(self):
        body = self.get_sitemap().content.decode()
        self.assertNotIn('/draft/', body)

    def test_inactive_product_is_excluded(self):
        Product.objects.filter(pk=self.product.pk).update(is_active=False)
        self.assertNotIn('/classic/', self.get_sitemap().content.decode())


class RobotsTests(TestCase):
    @override_settings(SITE_URL=PROD, SITE_INDEXABLE=True)
    def test_open_site_points_to_sitemap_on_prod_domain(self):
        body = self.client.get('/robots.txt').content.decode()
        self.assertIn(f'Sitemap: {PROD}/sitemap.xml', body)
        self.assertNotIn('\nDisallow: /\n', body)

    @override_settings(SITE_URL=PROD, SITE_INDEXABLE=True)
    def test_private_sections_are_closed(self):
        body = self.client.get('/robots.txt').content.decode()
        for path in ('/backoffice/', '/api/', '/orders/', '/ru/accounts/', '/kk/quiz/'):
            self.assertIn(f'Disallow: {path}', body)

    @override_settings(SITE_URL=PROD, SITE_INDEXABLE=True)
    def test_clean_param_only_in_yandex_group(self):
        """Clean-param понимает только Яндекс: в общей группе Google писал на
        него предупреждение в Search Console."""
        body = self.client.get('/robots.txt').content.decode()
        common, yandex = body.split('User-agent: Yandex')
        self.assertNotIn('Clean-param', common)
        self.assertIn('Clean-param: utm_source', yandex)

    @override_settings(SITE_URL=PROD, SITE_INDEXABLE=True)
    def test_yandex_group_closes_the_same_sections(self):
        """Своя группа означает, что общую Яндекс не читает — закрытое в ней
        должно совпадать до строки, иначе бэкофис уедет в его индекс."""
        body = self.client.get('/robots.txt').content.decode()
        common, yandex = body.split('User-agent: Yandex')

        def rules(part):
            return [ln for ln in part.splitlines() if ln.startswith('Disallow: ')]

        self.assertEqual(rules(common), rules(yandex))
        self.assertIn('Disallow: /backoffice/', rules(yandex))

    @override_settings(SITE_URL='https://app.dr-joys.com', SITE_INDEXABLE=False)
    def test_staging_is_closed_entirely(self):
        body = self.client.get('/robots.txt').content.decode()
        self.assertEqual(body.strip(), 'User-agent: *\nDisallow: /')


@override_settings(SITE_URL=PROD, SITE_INDEXABLE=True)
class LlmsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        category = Category.objects.create(name='Презервативы', slug='prezervativy')
        Product.objects.create(name='Classic', slug='classic', category=category)

    def test_lists_catalog_on_prod_domain(self):
        response = self.client.get('/llms.txt')
        body = response.content.decode()
        self.assertTrue(response['Content-Type'].startswith('text/plain'))
        self.assertIn('# DR.JOYS', body)
        self.assertIn(f'[Classic]({PROD}/ru/catalog/prezervativy/classic/)', body)
        self.assertNotIn(STAGING_HOST, body)


@override_settings(SITE_URL=PROD, SITE_INDEXABLE=True, ALLOWED_HOSTS=['*'])
class CanonicalTests(TestCase):
    def test_canonical_uses_prod_domain_and_drops_utm(self):
        response = self.client.get(
            reverse('pages:blog_list'),
            {'utm_source': 'telegram'},
            headers={'host': STAGING_HOST},
        )
        body = response.content.decode()
        self.assertIn(f'<link rel="canonical" href="{PROD}/ru/blog/">', body)
        self.assertNotIn('utm_source', body.split('</head>')[0])

    def test_canonical_drops_page_param(self):
        """С OS-10 пагинации на витрине нет: `?page=2` отдаёт тот же каталог.
        Старый проиндексированный адрес пагинации должен склеиваться с
        каталогом, а не канонизироваться сам на себя."""
        body = self.client.get(
            reverse('catalog:catalog'), {'page': '2'},
        ).content.decode()
        self.assertIn(f'<link rel="canonical" href="{PROD}/ru/catalog/">', body)
        self.assertNotIn('page=2', body.split('</head>')[0])

    def test_hreflang_covers_all_languages_plus_x_default(self):
        body = self.client.get(reverse('pages:blog_list')).content.decode()
        for lang, path in (
            ('ru', '/ru/blog/'), ('kk', '/kk/blog/'), ('en', '/en/blog/'),
            ('x-default', '/ru/blog/'),
        ):
            self.assertIn(
                f'<link rel="alternate" hreflang="{lang}" href="{PROD}{path}">', body,
            )

    def test_no_hreflang_outside_language_prefixed_urls(self):
        """На /orders/ языковых версий нет — три одинаковые ссылки были бы враньём."""
        body = self.client.get('/orders/cart/').content.decode()
        self.assertNotIn('rel="alternate" hreflang', body)

    @override_settings(SITE_INDEXABLE=False)
    def test_noindex_on_closed_site(self):
        body = self.client.get(reverse('pages:blog_list')).content.decode()
        self.assertIn('<meta name="robots" content="noindex, nofollow">', body)


@override_settings(SITE_URL=PROD, SITE_INDEXABLE=True)
class MetaFallbackTests(TestCase):
    """Пустые поля в бэкофисе не должны оставлять страницу без title/description.

    Именно так и было: у 24 товаров из 24 заголовок сводился к названию
    («Классика 17 шт»), а у статей блога тега description не было вовсе.
    """

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name='Презервативы', slug='prezervativy')
        cls.lube_category = Category.objects.create(name='Смазки', slug='smazki')
        cls.product = Product.objects.create(
            name='Классика 17 шт', slug='classic-17', category=cls.category,
            description='Гладкий презерватив с нейтральным ароматом.',
        )
        cls.lube = Product.objects.create(
            name='Смазка на водной основе', slug='lube', category=cls.lube_category,
        )
        cls.post = BlogPost.objects.create(
            title='Краш-тест', slug='krash-test',
            body='<p>Мы проверили прочность на разрыв &mdash; и вот что вышло.</p>',
            published_at='2026-07-01T10:00:00Z',
        )
        cls.page = Page.objects.create(
            title='О компании DR.JOYS', slug='about',
            body='<p>Казахстанский бренд средств личной гигиены.</p>',
        )

    def head_of(self, url):
        return self.client.get(url).content.decode().split('</head>')[0]

    def test_product_title_gets_category_and_brand(self):
        head = self.head_of(self.product.get_absolute_url())
        self.assertIn('<title>Классика 17 шт — Презервативы DR.JOYS</title>', head)

    def test_product_title_does_not_repeat_category_word(self):
        """«Смазка ... — Смазки DR.JOYS» — одно слово дважды подряд."""
        head = self.head_of(self.lube.get_absolute_url())
        self.assertIn('<title>Смазка на водной основе — DR.JOYS</title>', head)

    def test_filled_meta_title_wins(self):
        Product.objects.filter(pk=self.product.pk).update(meta_title='Свой заголовок')
        self.assertIn('<title>Свой заголовок</title>',
                      self.head_of(self.product.get_absolute_url()))

    def test_blog_post_gets_description_from_body(self):
        head = self.head_of(self.post.get_absolute_url())
        self.assertIn('<meta name="description" content="Мы проверили прочность '
                      'на разрыв — и вот что вышло."', head)
        self.assertNotIn('<p>', head.split('name="description"')[1][:200])

    def test_page_title_does_not_double_the_brand(self):
        self.assertIn('<title>О компании DR.JOYS</title>',
                      self.head_of(self.page.get_absolute_url()))

    def test_page_description_falls_back_to_body(self):
        self.assertIn('content="Казахстанский бренд средств личной гигиены."',
                      self.head_of(self.page.get_absolute_url()))


@override_settings(SITE_URL=PROD, SITE_INDEXABLE=True)
class StructuredDataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name='Презервативы', slug='prezervativy')
        cls.product = Product.objects.create(
            name='Классика 17 шт', slug='classic-17', category=cls.category,
            description='Гладкий презерватив.',
        )
        ProductSize.objects.create(
            product=cls.product, name='M', sku='DJ-CLASSIC-17-M', price=8990,
        )
        # «Скоро в продаже» — заведён без цены
        ProductSize.objects.create(
            product=cls.product, name='XL', sku='DJ-CLASSIC-17-XL',
            price=0, coming_soon=True,
        )
        cls.post = BlogPost.objects.create(
            title='Краш-тест', slug='krash-test', body='<p>Текст статьи.</p>',
            published_at='2026-07-01T10:00:00Z',
        )

    @staticmethod
    def jsonld_blocks(body):
        raw = re.findall(r'application/ld\+json">(.*?)</script>', body, re.S)
        return [
            json.loads(
                block.replace('\\u003c', '<').replace('\\u003e', '>').replace('\\u0026', '&')
            )
            for block in raw
        ]

    def blocks_of(self, url):
        return self.jsonld_blocks(self.client.get(url).content.decode())

    def test_size_without_price_stays_out_of_offers(self):
        """`lowPrice: "0.00"` Google отклоняет, Offer без price невалиден по схеме."""
        product = next(
            b for b in self.blocks_of(self.product.get_absolute_url())
            if b['@type'] == 'Product'
        )
        self.assertEqual(product['offers']['@type'], 'Offer')
        self.assertEqual(product['offers']['price'], '8990.00')

    def test_price_range_ignores_zeroes(self):
        ProductSize.objects.create(
            product=self.product, name='L', sku='DJ-CLASSIC-17-L', price=9990,
        )
        product = next(
            b for b in self.blocks_of(self.product.get_absolute_url())
            if b['@type'] == 'Product'
        )
        offers = product['offers']
        self.assertEqual(offers['@type'], 'AggregateOffer')
        self.assertEqual(offers['lowPrice'], '8990.00')
        self.assertEqual(offers['highPrice'], '9990.00')
        self.assertEqual(offers['offerCount'], 2)

    def test_blogposting_has_fields_google_requires(self):
        blocks = self.blocks_of(self.post.get_absolute_url())
        posting = [b for b in blocks if b['@type'] == 'BlogPosting']
        # Ровно один: раньше их было два — из вьюхи и inline в шаблоне
        self.assertEqual(len(posting), 1)
        posting = posting[0]
        self.assertEqual(posting['headline'], 'Краш-тест')
        self.assertEqual(posting['publisher']['@type'], 'Organization')
        self.assertTrue(posting['publisher']['logo']['url'].endswith('.png'))
        self.assertIn('dateModified', posting)
        self.assertIn('author', posting)

    def test_logo_in_markup_is_raster(self):
        """SVG в поле logo Google Search не рисует, соцсети не рендерят вовсе."""
        for block in self.blocks_of(reverse('home')):
            if block.get('@type') == 'Organization':
                self.assertTrue(block['logo'].endswith('.png'), block['logo'])
                break
        else:
            self.fail('глобального блока Organization нет на главной')

    def test_blog_list_marked_as_list_not_as_articles(self):
        blocks = self.blocks_of(reverse('pages:blog_list'))
        self.assertFalse([b for b in blocks if b['@type'] == 'BlogPosting'])
        blog = next(b for b in blocks if b['@type'] == 'Blog')
        self.assertEqual(blog['mainEntity']['numberOfItems'], 1)


@override_settings(SITE_URL=PROD, SITE_INDEXABLE=True, DEBUG=False)
class ErrorPageTests(TestCase):
    def test_404_is_branded_and_offers_a_way_out(self):
        response = self.client.get('/ru/net-takoy-adresa/')
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')
        body = response.content.decode()
        self.assertIn(reverse('catalog:catalog'), body)

    def test_favicon_at_root_redirects_to_static(self):
        response = self.client.get('/favicon.ico')
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response['Location'].endswith('/favicon/favicon.ico'))


class LoggingConfigTests(SimpleTestCase):
    """Платёжные INFO-строки должны доходить до вывода контейнера.

    Без секции LOGGING в settings эффективный уровень этих логгеров —
    WARNING от root, и logger.info в vtb.py / emails/service.py молчит:
    инцидент с деньгами разбирать нечем.

    assertLogs здесь не помощник: он сам подменяет уровень, handlers и
    propagate у запрошенного логгера, поэтому зелёный и с пустым LOGGING.
    Поэтому пишем в настоящий консольный хендлер, подменив ему поток, —
    и читаем ровно то, что ушло бы в `docker compose logs backend`.
    """

    def console_output(self, logger_name):
        """Что напечатает консольный хендлер на logger.info из этого модуля.

        Хендлер `console` в LOGGING один на всех, и `orders`/`emails`
        держат его же — значит лишний emit от propagate попадёт в тот же
        буфер и будет виден как вторая строка.
        """
        handlers = logging.getLogger(logger_name.partition('.')[0]).handlers
        self.assertEqual(len(handlers), 1, 'ожидался один консольный хендлер')
        handler = handlers[0]
        buffer = io.StringIO()
        original, handler.stream = handler.stream, buffer
        try:
            logging.getLogger(logger_name).info('PH-01 probe')
        finally:
            handler.stream = original
        return buffer.getvalue()

    def test_orders_logger_passes_info(self):
        self.assertTrue(
            logging.getLogger('orders.gateways.vtb').isEnabledFor(logging.INFO)
        )

    def test_emails_logger_passes_info(self):
        self.assertTrue(
            logging.getLogger('emails.service').isEnabledFor(logging.INFO)
        )

    def test_orders_info_printed_once_with_timestamp(self):
        output = self.console_output('orders.gateways.vtb')
        self.assertEqual(output.count('PH-01 probe'), 1, 'строка задвоилась')
        self.assertRegex(
            output,
            r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} '
            r'INFO orders\.gateways\.vtb: PH-01 probe\n$',
        )

    def test_emails_info_printed_once(self):
        output = self.console_output('emails.service')
        self.assertEqual(output.count('PH-01 probe'), 1, 'строка задвоилась')
        self.assertIn('INFO emails.service: PH-01 probe', output)


# ─── Настройки пути денег ───

class PaymentSettingsFromEnvTests(SimpleTestCase):
    """Настройки пути денег читаются из окружения под своими именами.

    Потребители берут их через `getattr(settings, …, '')`
    (`orders/gateways/vtb.py`, `emails/service.py`), а все тесты, которым
    значение важно, ставят его сами через `override_settings` — который
    заводит настройку, даже если строки в `settings.py` нет. Поэтому
    пропавшая при рефакторинге строка или опечатка в имени переменной
    окружения не роняют ни один тест, а на проде выключают ровно то, ради
    чего писался блок: проверку подписи callback-а ВТБ и единственный
    push-канал алерта «заказ истёк, а деньги списаны».
    """

    ENV = {
        'VTB_CALLBACK_TOKEN': 'probe-token',
        'PAYMENT_ALERT_EMAIL': 'probe@dr-joys.test',
    }

    def reloaded_settings(self, env):
        """Перечитать модуль настроек с подменённым окружением.

        Живые `django.conf.settings` при этом не меняются — тесты читают их,
        а не атрибуты модуля; cleanup возвращает модуль к окружению прогона.
        """
        import core.settings

        self.addCleanup(importlib.reload, core.settings)
        with mock.patch.dict(os.environ, env):
            return importlib.reload(core.settings)

    def test_vtb_callback_token_comes_from_env(self):
        reloaded = self.reloaded_settings(self.ENV)
        self.assertEqual(reloaded.VTB_CALLBACK_TOKEN, 'probe-token')

    def test_payment_alert_email_comes_from_env(self):
        reloaded = self.reloaded_settings(self.ENV)
        self.assertEqual(reloaded.PAYMENT_ALERT_EMAIL, 'probe@dr-joys.test')

    def test_both_default_to_empty(self):
        """Пустое окружение — обе пустые, а не AttributeError: «пусто =
        выключено» и есть заявленный дефолт (fail-open у токена сознателен —
        код едет на прод раньше значения)."""
        reloaded = self.reloaded_settings({k: '' for k in self.ENV})
        self.assertEqual(reloaded.VTB_CALLBACK_TOKEN, '')
        self.assertEqual(reloaded.PAYMENT_ALERT_EMAIL, '')


class LangSwitchOutsideI18nTest(orders_tests.CheckoutRegionTest):
    """Меню языка вне i18n-префикса — POST на штатный set_language (SB-05).

    Ссылка меню строится срезом `request.path|slice:'3:'` и на /orders/checkout/
    давала /ruders/checkout/ → 404 на пути денег. Фикстуры корзины и логин —
    у CheckoutRegionTest (конвенция payments-region: наследоваться,
    не переписывать).
    """

    def test_setlang_sets_cookie_and_redirects(self):
        response = self.client.post(
            '/i18n/setlang/', {'language': 'en', 'next': '/orders/checkout/'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/orders/checkout/')
        self.assertEqual(
            response.cookies[settings.LANGUAGE_COOKIE_NAME].value, 'en',
        )

    def test_checkout_menu_is_setlang_form(self):
        """Кнопки, csrf и next ищем ВНУТРИ формы setlang (идиома
        test_get_renders_region_switch_form): без next штатная вьюха уходит
        на referer, и ассерт по всей странице этого не поймал бы."""
        response = self.client.get('/orders/checkout/')
        self.assertNotContains(response, '/ruders')
        html = response.content.decode()
        form = next(
            chunk for chunk in html.split('<form')
            if 'action="/i18n/setlang/"' in chunk
        ).split('</form>')[0]
        self.assertIn('name="csrfmiddlewaretoken"', form)
        self.assertIn('name="next" value="/orders/checkout/"', form)
        for code, _name in settings.LANGUAGES:
            self.assertIn(f'name="language" value="{code}"', form)

    def test_prefixed_page_keeps_links(self):
        response = self.client.get('/ru/')
        self.assertContains(response, 'href="/en/"')
        self.assertNotContains(response, '/i18n/setlang/')

    def test_checkout_respects_language_cookie(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'en'
        response = self.client.get('/orders/checkout/')
        # Маркер шаблона: заголовок формы «Доставка» в en-локали
        self.assertContains(response, 'Delivery')


@override_settings(SHOP_PAUSED=True, ALLOWED_HOSTS=['*'])
class ShopPausedTests(TestCase):
    """Пауза магазина (SHOP_PAUSED): главная отдаёт заглушку pages/pause.html
    с кодом 200, каталог временно (302) уводит на неё — адреса не выпадают из
    индекса, — checkout закрыт, «Оффлайн магазины» и правовые страницы живы
    без навигации (по прямой ссылке), остальные страницы — как обычно."""

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name='Презервативы', slug='prezervativy')
        cls.page = Page.objects.create(title='Оферта', slug='oferta')
        Page.objects.create(title='Оффлайн магазины', slug='partners', body='')
        legal = PageCategory.objects.create(name='Правовая информация', slug='legal')
        cls.legal_page = Page.objects.create(
            title='Политика конфиденциальности', slug='privacy', category=legal,
        )

    def test_home_shows_pause_stub(self):
        response = self.client.get('/ru/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pages/pause.html')
        self.assertContains(response, 'https://t.me/drjoyspromo_bot')

    def test_catalog_redirects_to_home(self):
        response = self.client.get('/ru/catalog/')
        self.assertRedirects(response, '/ru/', status_code=302,
                             fetch_redirect_response=False)

    def test_category_page_redirects_to_home(self):
        response = self.client.get('/ru/catalog/prezervativy/')
        self.assertRedirects(response, '/ru/', status_code=302,
                             fetch_redirect_response=False)

    def test_partners_stays_alive_but_hides_navigation(self):
        # «Оффлайн магазины» на паузе живут (точки продаж работают), но без
        # навигации и футера — уйти можно только логотипом, обратно на заглушку
        response = self.client.get('/ru/partners/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateNotUsed(response, 'pages/pause.html')
        self.assertNotContains(response, 'id="menuBtn"')
        self.assertNotContains(response, 'id="mainNav"')
        self.assertNotContains(response, '>Меню</h2>')
        self.assertNotContains(response, '<footer')

    def test_other_cms_pages_stay_alive(self):
        response = self.client.get('/ru/oferta/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateNotUsed(response, 'pages/pause.html')

    def test_checkout_get_redirects_home(self):
        response = self.client.get('/orders/checkout/')
        self.assertRedirects(response, '/ru/', fetch_redirect_response=False)

    def test_checkout_post_redirects_home(self):
        response = self.client.post('/orders/checkout/', {})
        self.assertRedirects(response, '/ru/', fetch_redirect_response=False)

    def test_pause_stub_hides_navigation(self):
        # На заглушке нет навигации и футера: бургер, иконки корзины/избранного,
        # mainNav скрыты, футер не рендерится целиком (ни меню, ни правового
        # блока, ни копирайта с юрлицом)
        response = self.client.get('/ru/')
        self.assertNotContains(response, 'id="menuBtn"')
        self.assertNotContains(response, 'id="mainNav"')
        self.assertNotContains(response, 'data-open-modal="modalFavorites"')
        self.assertNotContains(response, 'data-open-modal="modalCart"')
        self.assertNotContains(response, '>Меню</h2>')
        self.assertNotContains(response, 'contact-links')
        self.assertNotContains(response, '<footer')
        self.assertNotContains(response, 'Все права защищены')

    def test_legal_pages_stay_alive_but_hide_navigation(self):
        # Правовые страницы живы (по прямой ссылке), но без навигации и футера:
        # уйти с них можно только логотипом — обратно на заглушку
        response = self.client.get('/ru/privacy/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateNotUsed(response, 'pages/pause.html')
        self.assertNotContains(response, 'id="menuBtn"')
        self.assertNotContains(response, 'id="mainNav"')
        self.assertNotContains(response, '>Меню</h2>')
        self.assertNotContains(response, '<footer')

    @override_settings(SHOP_PAUSED=False)
    def test_flag_off_legal_page_keeps_navigation(self):
        response = self.client.get('/ru/privacy/')
        self.assertContains(response, 'id="menuBtn"')
        self.assertContains(response, '>Меню</h2>')
        self.assertContains(response, 'Все права защищены')

    @override_settings(SHOP_PAUSED=False)
    def test_flag_off_home_is_normal(self):
        response = self.client.get('/ru/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pages/home.html')
        # Навигация и футер на месте: гейт pause_stub не задел обычный режим
        self.assertContains(response, 'id="menuBtn"')
        self.assertContains(response, 'id="mainNav"')
        self.assertContains(response, '>Меню</h2>')
        self.assertContains(response, '>Правовая информация</h2>')
        self.assertContains(response, 'Все права защищены')


# ─── core/text.py::one_line — санитайзер значений покупателя (PP-01) ───

class OneLineTests(SimpleTestCase):
    """Один санитайзер на лог callback-а и письма владельцу (Р-5).

    Перевод строки в значении от покупателя — это поддельная запись в логе
    или поддельная строка в plain-text письме; здесь он обязан умереть.
    """

    def test_newlines_become_single_spaces(self):
        self.assertEqual(
            one_line('ул. Ленина 1\r\nСумма: 999'),
            'ул. Ленина 1 Сумма: 999',
        )

    def test_controls_collapse_and_edges_trimmed(self):
        self.assertEqual(one_line('  a \t\t b \n\n '), 'a b')

    def test_none_is_empty_string(self):
        self.assertEqual(one_line(None), '')

    def test_plain_string_passes_unchanged(self):
        self.assertEqual(one_line('ул. Абая 1, кв. 2'), 'ул. Абая 1, кв. 2')
