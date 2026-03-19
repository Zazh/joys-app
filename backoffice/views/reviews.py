import subprocess
import sys

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView

from backoffice.mixins import BackofficeAccessMixin
from reviews.models import Review


class ReviewListView(BackofficeAccessMixin, ListView):
    template_name = 'backoffice/reviews/list.html'
    context_object_name = 'reviews'
    paginate_by = 25

    def get_queryset(self):
        qs = Review.objects.order_by('-wb_created_at')

        tab = self.request.GET.get('tab', 'all')
        if tab == 'featured':
            qs = qs.filter(is_featured=True)
        elif tab == 'pinned':
            qs = qs.filter(is_pinned=True)
        elif tab == 'excluded':
            qs = qs.filter(is_excluded=True)

        rating = self.request.GET.get('rating')
        if rating:
            try:
                qs = qs.filter(rating=int(rating))
            except ValueError:
                pass

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(user_name__icontains=q) |
                Q(text__icontains=q) |
                Q(pros__icontains=q) |
                Q(cons__icontains=q) |
                Q(product_name__icontains=q)
            )

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['current_tab'] = self.request.GET.get('tab', 'all')
        ctx['current_rating'] = self.request.GET.get('rating', '')
        ctx['current_q'] = self.request.GET.get('q', '')
        ctx['total_all'] = Review.objects.count()
        ctx['total_featured'] = Review.objects.filter(is_featured=True).count()
        ctx['total_pinned'] = Review.objects.filter(is_pinned=True).count()
        ctx['total_excluded'] = Review.objects.filter(is_excluded=True).count()
        return ctx


class ReviewToggleView(BackofficeAccessMixin, View):
    """Toggle pin/exclude/feature для отзыва."""
    def post(self, request, pk):
        review = get_object_or_404(Review, pk=pk)
        action = request.POST.get('action')

        if action == 'pin':
            review.is_pinned = not review.is_pinned
            if review.is_pinned:
                review.is_featured = True
            review.save(update_fields=['is_pinned', 'is_featured'])
            msg = 'закреплён' if review.is_pinned else 'откреплён'
        elif action == 'exclude':
            review.is_excluded = not review.is_excluded
            if review.is_excluded:
                review.is_featured = False
                review.is_pinned = False
            review.save(update_fields=['is_excluded', 'is_featured', 'is_pinned'])
            msg = 'исключён' if review.is_excluded else 'включён обратно'
        elif action == 'feature':
            review.is_featured = not review.is_featured
            if not review.is_featured:
                review.is_pinned = False
            review.save(update_fields=['is_featured', 'is_pinned'])
            msg = 'показан на сайте' if review.is_featured else 'скрыт с сайта'
        else:
            messages.error(request, 'Неизвестное действие.')
            return redirect('backoffice:review_list')

        messages.success(request, f'Отзыв {msg}.')
        # Preserve current filters
        tab = request.GET.get('tab', '')
        url = request.META.get('HTTP_REFERER', '')
        return redirect(url or 'backoffice:review_list')


class ReviewSyncView(BackofficeAccessMixin, View):
    """Запуск синхронизации отзывов с WB."""
    def post(self, request):
        try:
            result = subprocess.run(
                [sys.executable, 'manage.py', 'sync_wb_reviews'],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                output = result.stdout.strip().split('\n')[-1] if result.stdout.strip() else 'Готово'
                messages.success(request, f'Синхронизация завершена: {output}')
            else:
                error = result.stderr.strip()[:200] if result.stderr else 'Неизвестная ошибка'
                messages.error(request, f'Ошибка синхронизации: {error}')
        except subprocess.TimeoutExpired:
            messages.error(request, 'Синхронизация превысила таймаут (2 мин).')
        except Exception as e:
            messages.error(request, f'Ошибка: {e}')

        return redirect('backoffice:review_list')
