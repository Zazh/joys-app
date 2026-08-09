from django.core.cache import cache
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, ListView, TemplateView

from django.db.models import Avg, Count, Prefetch, Q, Value
from django.db.models.functions import Coalesce, Length

from catalog import jsonld as jld
from core import seo
from inquiries.models import InquiryForm
from modals.models import InteractiveModal
from quiz.models import QuizQuestion, QuizResultText
from reviews.models import Review
from .jsonld import (
    build_blog_list_jsonld, build_blogposting_jsonld, build_contact_page_jsonld,
    build_offline_stores_jsonld,
)
from .models import (
    PageCategory, Page, BlogPost, HeroSection, HeroCard, FeatureSlide, PromoBlock,
    OfflineStore,
)


class HomeView(TemplateView):
    template_name = 'pages/home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_type'] = 'home'
        hero = (
            HeroSection.objects
            .filter(is_active=True)
            .prefetch_related(Prefetch(
                'cards',
                HeroCard.objects.select_related('product__category'),
            ))
            .first()
        )
        if hero:
            ctx['hero'] = hero
            cards = list(hero.cards.all())
            ctx['hero_cards'] = cards
            # Для доступа по индексу в шаблоне
            for i, card in enumerate(cards):
                ctx[f'card{i+1}'] = card
        ctx['feature_slides'] = FeatureSlide.objects.filter(is_active=True)
        # Промо-блоки: загружаем все 3 одним запросом
        promos = {
            p.slug: p
            for p in PromoBlock.objects
            .filter(slug__in=['tattoo', 'quiz', 'partners'], is_active=True)
            .prefetch_related('images')
        }
        ctx['quiz_promo'] = promos.get('quiz')
        ctx['partners_promo'] = promos.get('partners')
        ctx['tattoo_promo'] = promos.get('tattoo')
        tattoo = promos.get('tattoo')
        if tattoo:
            images = list(tattoo.images.all())
            if images:
                ctx['tattoo_gallery'] = [images[i % len(images)] for i in range(8)]
        ctx['blog_posts'] = (
            BlogPost.objects
            .filter(is_published=True)
            .order_by('-published_at')[:5]
        )
        # Модалки: загружаем обе одним запросом с prefetch
        modals = {
            m.slug: m
            for m in InteractiveModal.objects
            .filter(slug__in=['tattoo', 'partner'], is_active=True)
            .prefetch_related('steps', 'steps__inquiry_form', 'steps__inquiry_form__fields')
        }
        ctx['tattoo_modal'] = modals.get('tattoo')
        ctx['partner_modal'] = modals.get('partner')
        # Квиз: вопросы + текст результата
        ctx['quiz_questions'] = list(
            QuizQuestion.objects
            .filter(is_active=True)
            .prefetch_related('options')
            .order_by('order')
        )
        ctx['result_text'] = QuizResultText.load()
        # Отзывы: кеш на сутки — данные меняются только ежедневной
        # командой rotate_featured_reviews, она же сбрасывает кеш
        ctx['review_stats'] = cache.get_or_set(
            'home_review_stats', self._build_review_stats, 60 * 60 * 24,
        )
        ctx['featured_reviews'] = cache.get_or_set(
            'home_featured_reviews', self._build_featured_reviews, 60 * 60 * 24,
        )
        return ctx

    @staticmethod
    def _build_review_stats():
        stats = Review.objects.aggregate(
            avg_rating=Avg('rating'),
            total_count=Count('id'),
            positive_count=Count('id', filter=Q(rating__gte=2)),
            negative_count=Count('id', filter=Q(rating=1)),
        )
        total = stats['total_count'] or 1
        stats['negative_percent'] = round(stats['negative_count'] / total * 100, 1)
        stats['avg_rating'] = round(stats['avg_rating'] or 0, 1)
        return stats

    @staticmethod
    def _build_featured_reviews():
        featured = list(
            Review.objects
            .with_content()
            .filter(is_featured=True, is_excluded=False)
            .annotate(
                _content_len=Coalesce(Length('text'), Value(0))
                + Coalesce(Length('pros'), Value(0))
                + Coalesce(Length('cons'), Value(0)),
            )
            .order_by('-_content_len', '-wb_created_at')[:12]
        )
        if len(featured) >= 3:
            def _clen(r):
                return len(r.text or '') + len(r.pros or '') + len(r.cons or '')
            if _clen(featured[1]) < 40:
                for i in range(2, len(featured) - 1):
                    if _clen(featured[i]) >= 40:
                        featured[1], featured[i] = featured[i], featured[1]
                        break
            if _clen(featured[-1]) < 40:
                for i in range(len(featured) - 2, 1, -1):
                    if _clen(featured[i]) >= 40:
                        featured[-1], featured[i] = featured[i], featured[-1]
                        break
        return featured


class PageCategoryDetailView(DetailView):
    model = PageCategory
    template_name = 'pages/category_detail.html'
    context_object_name = 'category'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        category = self.object
        pages = list(category.pages.filter(is_published=True).order_by('order', 'title'))
        ctx['pages'] = pages
        ctx['meta_title'] = seo.with_brand(category.name)
        ctx['meta_description'] = seo.first_filled(
            category.description,
            ', '.join(page.title for page in pages),
        )
        breadcrumbs = [
            {'name': 'DR.JOYS', 'url': reverse('home')},
            {'name': category.name, 'url': ''},
        ]
        ctx['breadcrumbs'] = breadcrumbs
        ctx['jsonld_blocks'] = jld.serialize_jsonld(
            jld.build_breadcrumb_jsonld(self.request, breadcrumbs),
        )
        return ctx


class PageDetailView(DetailView):
    model = Page
    template_name = 'pages/page.html'
    context_object_name = 'page'

    # Страницы с собственной вёрсткой вместо generic pages/page.html
    CUSTOM_TEMPLATES = {
        'contacts': 'pages/contacts.html',
        'partners': 'pages/partners.html',
    }

    # Форма обращения на странице: slug страницы → slug InquiryForm
    INQUIRY_FORMS = {
        'contacts': 'contact',
    }

    # Описание для страниц, чей шаблон не показывает `body`: у них взять текст
    # для сниппета больше неоткуда. Для остальных фолбэк — начало самого текста
    # страницы (см. get_context_data). Заполненное в бэкофисе поле всегда важнее.
    FALLBACK_DESCRIPTIONS = {
        'contacts': _('Контакты DR.JOYS: телефон, WhatsApp, Telegram и почта, '
                      'адрес офиса в Алматы на карте и форма обращения.'),
        'partners': _('Оффлайн магазины с товарами DR.JOYS: адреса точек продаж '
                      'в Алматы, Астане и других городах Казахстана на карте — '
                      'самовывоз и доставка.'),
    }

    def get_queryset(self):
        return Page.objects.filter(is_published=True).select_related('category')

    def get_template_names(self):
        return [self.CUSTOM_TEMPLATES.get(self.object.slug, self.template_name)]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        page = self.object
        form_slug = self.INQUIRY_FORMS.get(page.slug)
        if form_slug:
            # Поля и лейблы редактируются в бэкофисе, шаблон только рисует
            ctx['inquiry_form'] = (
                InquiryForm.objects
                .prefetch_related('fields')
                .filter(slug=form_slug, is_active=True)
                .first()
            )

        # str() снимает ленивость: строка уходит в json.dumps, а __proxy__ он не умеет
        description = seo.first_filled(
            page.meta_description,
            str(self.FALLBACK_DESCRIPTIONS.get(page.slug, '')),
            page.body,
        )
        ctx['meta_description'] = description
        ctx['meta_title'] = seo.with_brand(page.meta_title or page.title)

        # Раздел в середину цепочки, если страница лежит в категории («Правовая
        # информация» и т.п.): у категории есть свой URL, и без неё цепочка врёт
        # об уровне вложенности
        breadcrumbs = [{'name': 'DR.JOYS', 'url': reverse('home')}]
        if page.category:
            breadcrumbs.append({
                'name': page.category.name,
                'url': page.category.get_absolute_url(),
            })
        breadcrumbs.append({'name': page.title, 'url': ''})
        ctx['breadcrumbs'] = breadcrumbs

        stores = None
        if page.slug == 'partners':
            stores = list(OfflineStore.objects.filter(is_active=True))
            ctx.update(self._stores_context(stores))

        ctx['jsonld_blocks'] = jld.serialize_jsonld(
            jld.build_breadcrumb_jsonld(self.request, breadcrumbs),
            build_contact_page_jsonld(self.request, page, description)
            if page.slug == 'contacts' else None,
            build_offline_stores_jsonld(self.request, page, stores, description)
            if stores is not None else None,
        )
        return ctx

    @staticmethod
    def _stores_context(stores):
        """Группы точек по городам и данные для карты.

        Порядок городов — по числу точек: он же порядок чипов и секций списка,
        Алматы и Астана оказываются первыми сами, без ручного приоритета.
        JSON для карты — те же точки, что в карточках: JS не ходит за данными,
        а собирает пины из json_script.
        """
        counts = {}
        for store in stores:
            counts[store.city] = counts.get(store.city, 0) + 1
        ordered_cities = sorted(counts, key=lambda city: -counts[city])
        return {
            'page_type': 'partners',
            'city_groups': [
                {
                    'name': city,
                    'count': counts[city],
                    'stores': [s for s in stores if s.city == city],
                }
                for city in ordered_cities
            ],
            'stores_json': [
                {
                    'id': store.pk,
                    'city': store.city,
                    'name': store.name,
                    'address': store.address,
                    'lat': store.geo['lat'] if store.geo else None,
                    'lng': store.geo['lng'] if store.geo else None,
                    'url': store.map_url,
                    'pickupOnly': store.fulfillment == OfflineStore.Fulfillment.PICKUP,
                }
                for store in stores
            ],
        }


class BlogListView(ListView):
    model = BlogPost
    template_name = 'pages/blog_list.html'
    context_object_name = 'posts'

    def get_queryset(self):
        return (
            BlogPost.objects
            .filter(is_published=True)
            .select_related('category')
            .order_by('-published_at')
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_type'] = 'blog_list'
        breadcrumbs = [
            {'name': 'DR.JOYS', 'url': reverse('home')},
            {'name': str(_('Блог')), 'url': ''},
        ]
        ctx['breadcrumbs'] = breadcrumbs
        ctx['jsonld_blocks'] = jld.serialize_jsonld(
            jld.build_breadcrumb_jsonld(self.request, breadcrumbs),
            build_blog_list_jsonld(self.request, ctx['posts']),
        )
        return ctx


class BlogDetailView(DetailView):
    model = BlogPost
    template_name = 'pages/blog_detail.html'
    context_object_name = 'post'

    def get_queryset(self):
        return (
            BlogPost.objects
            .filter(is_published=True)
            .select_related('category')
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        post = self.object
        ctx['page_type'] = 'blog_detail'
        # Описание: без него шаблон вообще не выводил тег, и сниппет в выдаче
        # Google сочинял сам. Анонс и начало текста — уже написанный редактором
        # текст об этой же статье, лучшего фолбэка нет.
        ctx['meta_description'] = seo.first_filled(
            post.meta_description, post.excerpt, post.body,
        )
        # Категорию в цепочку не берём: у BlogCategory нет своей страницы,
        # ссылаться неоткуда, а крошка без URL ломает уровень вложенности
        breadcrumbs = [
            {'name': 'DR.JOYS', 'url': reverse('home')},
            {'name': str(_('Блог')), 'url': reverse('pages:blog_list')},
            {'name': post.title, 'url': ''},
        ]
        ctx['breadcrumbs'] = breadcrumbs
        ctx['jsonld_blocks'] = jld.serialize_jsonld(
            jld.build_breadcrumb_jsonld(self.request, breadcrumbs),
            build_blogposting_jsonld(self.request, post, ctx['meta_description']),
        )
        return ctx
