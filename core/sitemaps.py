"""Карта сайта.

Домен и схему берём из settings.SITE_URL (см. core.seo), а не из request и не
из таблицы django_site: карта одинакова, по какому бы адресу её ни запросили,
а переезд на боевой домен — правка одной переменной в .env.

Каждый адрес отдаётся в трёх языковых версиях (/ru/, /kk/, /en/) со взаимными
ссылками hreflang — без них три перевода одной страницы выглядят для поисковика
как три дубля. Slug у моделей общий для всех языков, версии отличаются только
префиксом.
"""
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from catalog.models import Category, Product
from pages.models import BlogPost, Page, PageCategory


class BaseSitemap(Sitemap):
    i18n = True
    alternates = True
    # x-default Django собирает как адрес без языкового префикса, а при
    # prefix_default_language=True такой адрес только редиректит на /ru/.
    # Ссылаться в hreflang на редирект незачем — x-default объявлен в <head>
    # (base.html) и указывает сразу на русскую версию.
    x_default = False

    @property
    def protocol(self):
        return urlsplit(settings.SITE_URL).scheme or 'https'

    def get_domain(self, site=None):
        # site приходит из вьюхи как текущий хост — намеренно игнорируем.
        return urlsplit(settings.SITE_URL).netloc


class StaticViewSitemap(BaseSitemap):
    """Страницы без своей модели: главная, каталог, список статей."""
    changefreq = 'weekly'

    PRIORITIES = {
        'home': 1.0,
        'catalog:catalog': 0.9,
        'pages:blog_list': 0.6,
    }

    def items(self):
        return list(self.PRIORITIES)

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return self.PRIORITIES[item]


class CategorySitemap(BaseSitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return Category.objects.filter(is_active=True)


class ProductSitemap(BaseSitemap):
    changefreq = 'weekly'
    priority = 0.9

    def items(self):
        return (
            Product.objects
            .filter(is_active=True, category__is_active=True)
            .select_related('category')
        )

    def lastmod(self, obj):
        return obj.updated_at


class PageSitemap(BaseSitemap):
    changefreq = 'monthly'
    priority = 0.5

    def items(self):
        return Page.objects.filter(is_published=True)

    def lastmod(self, obj):
        return obj.updated_at


class PageCategorySitemap(BaseSitemap):
    changefreq = 'monthly'
    priority = 0.3

    def items(self):
        return PageCategory.objects.filter(pages__is_published=True).distinct()


class BlogPostSitemap(BaseSitemap):
    changefreq = 'monthly'
    priority = 0.6

    def items(self):
        return BlogPost.objects.filter(is_published=True)

    def lastmod(self, obj):
        return obj.updated_at


SITEMAPS = {
    'static': StaticViewSitemap,
    'categories': CategorySitemap,
    'products': ProductSitemap,
    'pages': PageSitemap,
    'page-categories': PageCategorySitemap,
    'blog': BlogPostSitemap,
}
