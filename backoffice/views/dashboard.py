from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from django.views.generic import TemplateView

from backoffice.mixins import BackofficeAccessMixin
from inquiries.models import InquirySubmission
from orders.models import Order


class DashboardView(BackofficeAccessMixin, TemplateView):
    template_name = 'backoffice/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        now = timezone.now()
        today = now.date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        orders = Order.objects.all()

        ctx['orders_today'] = orders.filter(created_at__date=today).count()
        ctx['orders_week'] = orders.filter(created_at__date__gte=week_ago).count()
        ctx['orders_month'] = orders.filter(created_at__date__gte=month_ago).count()

        status_counts = dict(
            orders.values_list('status').annotate(c=Count('id')).values_list('status', 'c')
        )
        ctx['pending_count'] = status_counts.get(Order.Status.PENDING, 0)
        ctx['paid_count'] = status_counts.get(Order.Status.PAID, 0)
        ctx['shipped_count'] = status_counts.get(Order.Status.SHIPPED, 0)

        ctx['unprocessed_inquiries'] = InquirySubmission.objects.filter(is_processed=False).count()
        ctx['recent_orders'] = orders.select_related('region').order_by('-created_at')[:5]

        return ctx
