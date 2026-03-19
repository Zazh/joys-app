import json
from datetime import timedelta

from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone
from django.views.generic import TemplateView

from backoffice.mixins import BackofficeAccessMixin
from inquiries.models import InquirySubmission
from orders.models import Order
from regions.models import Region
from reviews.models import Review


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

        # --- Charts data ---

        # Orders by day (last 30 days)
        thirty_days_ago = today - timedelta(days=30)
        daily_orders = (
            orders.filter(created_at__date__gte=thirty_days_ago)
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        # Fill missing days
        days_map = {item['day']: item['count'] for item in daily_orders}
        chart_labels = []
        chart_data = []
        for i in range(30):
            d = thirty_days_ago + timedelta(days=i)
            chart_labels.append(d.strftime('%d.%m'))
            chart_data.append(days_map.get(d, 0))

        ctx['chart_orders_labels'] = json.dumps(chart_labels)
        ctx['chart_orders_data'] = json.dumps(chart_data)

        # --- Reviews stats ---
        reviews = Review.objects.all()
        ctx['review_total'] = reviews.count()
        ctx['review_avg'] = reviews.aggregate(avg=Avg('rating'))['avg'] or 0

        # Rating distribution
        rating_dist = dict(
            reviews.values_list('rating').annotate(c=Count('id')).values_list('rating', 'c')
        )
        ctx['chart_rating_labels'] = json.dumps(['5★', '4★', '3★', '2★', '1★'])
        ctx['chart_rating_data'] = json.dumps([
            rating_dist.get(5, 0),
            rating_dist.get(4, 0),
            rating_dist.get(3, 0),
            rating_dist.get(2, 0),
            rating_dist.get(1, 0),
        ])

        # Weekly average rating (last 12 weeks)
        twelve_weeks_ago = today - timedelta(weeks=12)
        weekly_avg = (
            reviews.filter(wb_created_at__date__gte=twelve_weeks_ago)
            .annotate(week=TruncWeek('wb_created_at'))
            .values('week')
            .annotate(avg_rating=Avg('rating'), count=Count('id'))
            .order_by('week')
        )
        week_labels = []
        week_data = []
        for item in weekly_avg:
            week_labels.append(item['week'].strftime('%d.%m'))
            week_data.append(round(float(item['avg_rating']), 2))

        ctx['chart_weekly_labels'] = json.dumps(week_labels)
        ctx['chart_weekly_data'] = json.dumps(week_data)

        # --- Monthly sales report ---
        MONTHS_RU = {
            1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
            5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
            9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь',
        }

        monthly_raw = (
            orders
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(
                total=Count('id', distinct=True),
                paid=Count('id', distinct=True, filter=Q(status__in=[
                    Order.Status.PAID, Order.Status.SHIPPED, Order.Status.DELIVERED,
                ])),
                cancelled=Count('id', distinct=True, filter=Q(status__in=[
                    Order.Status.CANCELLED, Order.Status.EXPIRED,
                ])),
                revenue=Sum('total_amount', filter=Q(status__in=[
                    Order.Status.PAID, Order.Status.SHIPPED, Order.Status.DELIVERED,
                ])),
                items_sold=Sum('items__quantity', filter=Q(status__in=[
                    Order.Status.PAID, Order.Status.SHIPPED, Order.Status.DELIVERED,
                ])),
            )
            .order_by('-month')
        )

        monthly_report = []
        chart_monthly_labels = []
        chart_monthly_revenue = []
        chart_monthly_orders = []

        for row in monthly_raw:
            m = row['month']
            revenue = row['revenue'] or 0
            paid = row['paid'] or 0
            avg_check = round(revenue / paid) if paid else 0
            monthly_report.append({
                'month': m,
                'label': f"{MONTHS_RU[m.month]} {m.year}",
                'total': row['total'],
                'paid': paid,
                'cancelled': row['cancelled'] or 0,
                'pending': (row['total'] or 0) - (paid or 0) - (row['cancelled'] or 0),
                'revenue': revenue,
                'avg_check': avg_check,
                'items_sold': row['items_sold'] or 0,
            })
            chart_monthly_labels.append(f"{MONTHS_RU[m.month][:3]} {m.year % 100}")
            chart_monthly_revenue.append(float(revenue))
            chart_monthly_orders.append(paid)

        ctx['monthly_report'] = monthly_report

        # Chart data (reversed for chronological left-to-right)
        ctx['chart_monthly_labels'] = json.dumps(chart_monthly_labels[::-1])
        ctx['chart_monthly_revenue'] = json.dumps(chart_monthly_revenue[::-1])
        ctx['chart_monthly_orders'] = json.dumps(chart_monthly_orders[::-1])

        # --- Sales by region ---
        paid_statuses = [Order.Status.PAID, Order.Status.SHIPPED, Order.Status.DELIVERED]
        region_stats = (
            orders.filter(status__in=paid_statuses, region__isnull=False)
            .values('region__id', 'region__name')
            .annotate(
                orders_count=Count('id'),
                revenue=Sum('total_amount'),
                items_sold=Sum('items__quantity'),
            )
            .order_by('-revenue')
        )

        region_report = []
        chart_region_labels = []
        chart_region_data = []
        for row in region_stats:
            revenue = row['revenue'] or 0
            count = row['orders_count'] or 0
            region_report.append({
                'name': row['region__name'],
                'orders_count': count,
                'revenue': revenue,
                'avg_check': round(revenue / count) if count else 0,
                'items_sold': row['items_sold'] or 0,
            })
            chart_region_labels.append(row['region__name'] or '—')
            chart_region_data.append(float(revenue))

        ctx['region_report'] = region_report
        ctx['chart_region_labels'] = json.dumps(chart_region_labels)
        ctx['chart_region_data'] = json.dumps(chart_region_data)

        return ctx
