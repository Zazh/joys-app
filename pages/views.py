from django.views.generic import DetailView, ListView, TemplateView

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
        # Галерея тату: 8 позиций, если меньше — повторяем
        try:
            tattoo = PromoBlock.objects.prefetch_related('images').get(slug='tattoo', is_active=True)
            images = list(tattoo.images.all())
            if images:
                gallery = []
                for i in range(8):
                    gallery.append(images[i % len(images)])
                ctx['tattoo_gallery'] = gallery
        except PromoBlock.DoesNotExist:
            pass
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
