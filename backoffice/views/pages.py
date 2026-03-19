from django.contrib import messages
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from backoffice.mixins import BackofficeAccessMixin
from pages.models import (
    ServicePage, Page, PageCategory, BlogPost, BlogCategory,
)


# ─── Служебные страницы ───

class ServicePageListView(BackofficeAccessMixin, ListView):
    template_name = 'backoffice/pages/service_list.html'
    context_object_name = 'pages'

    def get_queryset(self):
        return ServicePage.objects.order_by('slug')


class ServicePageEditView(BackofficeAccessMixin, View):
    def get(self, request, pk):
        page = get_object_or_404(ServicePage, pk=pk)
        return TemplateResponse(request, 'backoffice/pages/service_form.html', {'page': page})

    def post(self, request, pk):
        page = get_object_or_404(ServicePage, pk=pk)

        page.title_ru = request.POST.get('title_ru', '').strip()
        page.title_kk = request.POST.get('title_kk', '').strip()
        page.title_en = request.POST.get('title_en', '').strip()
        page.description_ru = request.POST.get('description_ru', '').strip()
        page.description_kk = request.POST.get('description_kk', '').strip()
        page.description_en = request.POST.get('description_en', '').strip()
        page.button_text_ru = request.POST.get('button_text_ru', '').strip()
        page.button_text_kk = request.POST.get('button_text_kk', '').strip()
        page.button_text_en = request.POST.get('button_text_en', '').strip()
        page.button_url = request.POST.get('button_url', '/').strip()

        page.save()
        messages.success(request, f'Страница «{page.slug}» сохранена.')
        return redirect('backoffice:service_page_list')


# ─── Статические страницы ───

class PageListView(BackofficeAccessMixin, ListView):
    template_name = 'backoffice/pages/page_list.html'
    context_object_name = 'pages'
    paginate_by = 25

    def get_queryset(self):
        qs = Page.objects.select_related('category').order_by('order', 'title')

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(title_ru__icontains=q) | Q(slug__icontains=q)
            )

        cat = self.request.GET.get('category')
        if cat:
            qs = qs.filter(category_id=cat)

        pub = self.request.GET.get('published')
        if pub == 'yes':
            qs = qs.filter(is_published=True)
        elif pub == 'no':
            qs = qs.filter(is_published=False)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categories'] = PageCategory.objects.order_by('order', 'name')
        ctx['current_q'] = self.request.GET.get('q', '')
        ctx['current_category'] = self.request.GET.get('category', '')
        ctx['current_published'] = self.request.GET.get('published', '')
        return ctx


class PageEditView(BackofficeAccessMixin, View):
    def get(self, request, pk):
        page = get_object_or_404(Page.objects.select_related('category'), pk=pk)
        return TemplateResponse(request, 'backoffice/pages/page_form.html', {
            'page': page,
            'categories': PageCategory.objects.order_by('order', 'name'),
        })

    def post(self, request, pk):
        page = get_object_or_404(Page, pk=pk)
        self._fill(page, request)
        page.save()
        messages.success(request, f'Страница «{page.title_ru}» сохранена.')
        return redirect('backoffice:page_edit', pk=page.pk)

    def _fill(self, page, request):
        page.title_ru = request.POST.get('title_ru', '').strip()
        page.title_kk = request.POST.get('title_kk', '').strip()
        page.title_en = request.POST.get('title_en', '').strip()
        page.slug = request.POST.get('slug', '').strip()
        page.body_ru = request.POST.get('body_ru', '').strip()
        page.body_kk = request.POST.get('body_kk', '').strip()
        page.body_en = request.POST.get('body_en', '').strip()
        page.category_id = request.POST.get('category') or None
        page.is_published = request.POST.get('is_published') == 'on'
        page.order = int(request.POST.get('order', 0) or 0)
        page.meta_title_ru = request.POST.get('meta_title_ru', '').strip()
        page.meta_title_kk = request.POST.get('meta_title_kk', '').strip()
        page.meta_title_en = request.POST.get('meta_title_en', '').strip()
        page.meta_description_ru = request.POST.get('meta_description_ru', '').strip()
        page.meta_description_kk = request.POST.get('meta_description_kk', '').strip()
        page.meta_description_en = request.POST.get('meta_description_en', '').strip()
        if 'og_image' in request.FILES:
            page.og_image = request.FILES['og_image']


class PageCreateView(BackofficeAccessMixin, View):
    def get(self, request):
        return TemplateResponse(request, 'backoffice/pages/page_form.html', {
            'page': None,
            'categories': PageCategory.objects.order_by('order', 'name'),
        })

    def post(self, request):
        page = Page()
        PageEditView._fill(None, page, request)
        if not page.slug or not page.title_ru:
            messages.error(request, 'Название (RU) и slug обязательны.')
            return TemplateResponse(request, 'backoffice/pages/page_form.html', {
                'page': None,
                'categories': PageCategory.objects.order_by('order', 'name'),
                'post_data': request.POST,
            })
        page.save()
        messages.success(request, f'Страница «{page.title_ru}» создана.')
        return redirect('backoffice:page_edit', pk=page.pk)


# ─── Блог ───

class BlogPostListView(BackofficeAccessMixin, ListView):
    template_name = 'backoffice/pages/blog_list.html'
    context_object_name = 'posts'
    paginate_by = 25

    def get_queryset(self):
        qs = BlogPost.objects.select_related('category').order_by('-created_at')

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(title_ru__icontains=q) | Q(slug__icontains=q)
            )

        cat = self.request.GET.get('category')
        if cat:
            qs = qs.filter(category_id=cat)

        pub = self.request.GET.get('published')
        if pub == 'yes':
            qs = qs.filter(is_published=True)
        elif pub == 'no':
            qs = qs.filter(is_published=False)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categories'] = BlogCategory.objects.order_by('name')
        ctx['current_q'] = self.request.GET.get('q', '')
        ctx['current_category'] = self.request.GET.get('category', '')
        ctx['current_published'] = self.request.GET.get('published', '')
        return ctx


class BlogPostEditView(BackofficeAccessMixin, View):
    def get(self, request, pk):
        post = get_object_or_404(BlogPost.objects.select_related('category'), pk=pk)
        return TemplateResponse(request, 'backoffice/pages/blog_form.html', {
            'post': post,
            'categories': BlogCategory.objects.order_by('name'),
        })

    def post(self, request, pk):
        post = get_object_or_404(BlogPost, pk=pk)
        self._fill(post, request)
        post.save()
        messages.success(request, f'Статья «{post.title_ru}» сохранена.')
        return redirect('backoffice:blog_edit', pk=post.pk)

    def _fill(self, post, request):
        post.title_ru = request.POST.get('title_ru', '').strip()
        post.title_kk = request.POST.get('title_kk', '').strip()
        post.title_en = request.POST.get('title_en', '').strip()
        post.slug = request.POST.get('slug', '').strip()
        post.excerpt_ru = request.POST.get('excerpt_ru', '').strip()
        post.excerpt_kk = request.POST.get('excerpt_kk', '').strip()
        post.excerpt_en = request.POST.get('excerpt_en', '').strip()
        post.body_ru = request.POST.get('body_ru', '').strip()
        post.body_kk = request.POST.get('body_kk', '').strip()
        post.body_en = request.POST.get('body_en', '').strip()
        post.category_id = request.POST.get('category') or None
        post.author = request.POST.get('author', '').strip()
        post.is_published = request.POST.get('is_published') == 'on'
        post.meta_title_ru = request.POST.get('meta_title_ru', '').strip()
        post.meta_title_kk = request.POST.get('meta_title_kk', '').strip()
        post.meta_title_en = request.POST.get('meta_title_en', '').strip()
        post.meta_description_ru = request.POST.get('meta_description_ru', '').strip()
        post.meta_description_kk = request.POST.get('meta_description_kk', '').strip()
        post.meta_description_en = request.POST.get('meta_description_en', '').strip()
        if 'cover_image' in request.FILES:
            post.cover_image = request.FILES['cover_image']
        # Устанавливаем published_at при первой публикации
        if post.is_published and not post.published_at:
            post.published_at = timezone.now()


class BlogPostCreateView(BackofficeAccessMixin, View):
    def get(self, request):
        return TemplateResponse(request, 'backoffice/pages/blog_form.html', {
            'post': None,
            'categories': BlogCategory.objects.order_by('name'),
        })

    def post(self, request):
        post = BlogPost()
        BlogPostEditView._fill(None, post, request)
        if not post.slug or not post.title_ru:
            messages.error(request, 'Заголовок (RU) и slug обязательны.')
            return TemplateResponse(request, 'backoffice/pages/blog_form.html', {
                'post': None,
                'categories': BlogCategory.objects.order_by('name'),
                'post_data': request.POST,
            })
        post.save()
        messages.success(request, f'Статья «{post.title_ru}» создана.')
        return redirect('backoffice:blog_edit', pk=post.pk)
