from django.views.generic import DetailView, ListView, TemplateView

from django.db.models import Avg, Count, Q, Value
from django.db.models.functions import Coalesce, Length

from modals.models import InteractiveModal
from quiz.models import QuizQuestion, QuizResultText
from reviews.models import Review
from .models import PageCategory, Page, BlogPost, HeroSection, FeatureSlide, PromoBlock


class HomeView(TemplateView):
    template_name = 'pages/home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_type'] = 'home'
        hero = (
            HeroSection.objects
            .filter(is_active=True)
            .prefetch_related('cards')
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
        # Отзывы: статистика + избранные
        stats = Review.objects.aggregate(
            avg_rating=Avg('rating'),
            total_count=Count('id'),
            positive_count=Count('id', filter=Q(rating__gte=2)),
            negative_count=Count('id', filter=Q(rating=1)),
        )
        total = stats['total_count'] or 1
        stats['negative_percent'] = round(stats['negative_count'] / total * 100, 1)
        stats['avg_rating'] = round(stats['avg_rating'] or 0, 1)
        ctx['review_stats'] = stats
        featured = list(
            Review.objects
            .with_content()
            .filter(is_featured=True)
            .annotate(
                _content_len=Coalesce(Length('text'), Value(0))
                + Coalesce(Length('pros'), Value(0))
                + Coalesce(Length('cons'), Value(0)),
            )
            .order_by('-_content_len', '-wb_created_at')
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
        ctx['featured_reviews'] = featured
        return ctx


class PageCategoryDetailView(DetailView):
    model = PageCategory
    template_name = 'pages/category_detail.html'
    context_object_name = 'category'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['pages'] = self.object.pages.filter(is_published=True).order_by('order', 'title')
        return ctx


class PageDetailView(DetailView):
    model = Page
    template_name = 'pages/page.html'
    context_object_name = 'page'

    def get_queryset(self):
        return Page.objects.filter(is_published=True).select_related('category')


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
        ctx['page_type'] = 'blog_detail'
        return ctx
