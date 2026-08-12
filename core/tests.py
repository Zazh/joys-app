"""Тесты SEO-инфраструктуры: sitemap.xml, robots.txt, llms.txt, canonical.

Главное, что здесь проверяется, — что домен во всех этих ответах берётся из
SITE_URL, а не из хоста запроса. Это условие переезда app.dr-joys.com →
dr-joys.com одной правкой .env, и без теста оно тихо ломается при любом
рефакторинге.
"""
import io
import json
import logging
import re

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from catalog.models import Category, Product, ProductSize
from pages.models import BlogPost, Page

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
