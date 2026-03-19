import json
from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.views.generic import TemplateView

from backoffice.mixins import BackofficeAccessMixin
from quiz.models import QuizSubmission, QuizRule


class QuizAnalyticsView(BackofficeAccessMixin, TemplateView):
    template_name = 'backoffice/quiz/analytics.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        now = timezone.now()
        today = now.date()

        qs = QuizSubmission.objects.all()
        ctx['total'] = qs.count()
        ctx['today'] = qs.filter(created_at__date=today).count()
        ctx['week'] = qs.filter(created_at__date__gte=today - timedelta(days=7)).count()
        ctx['month'] = qs.filter(created_at__date__gte=today - timedelta(days=30)).count()

        # Submissions по дням (30 дней)
        thirty_days_ago = today - timedelta(days=30)
        daily = (
            qs.filter(created_at__date__gte=thirty_days_ago)
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        days_map = {item['day']: item['count'] for item in daily}
        chart_labels = []
        chart_data = []
        for i in range(30):
            d = thirty_days_ago + timedelta(days=i)
            chart_labels.append(d.strftime('%d.%m'))
            chart_data.append(days_map.get(d, 0))
        ctx['chart_labels'] = json.dumps(chart_labels)
        ctx['chart_data'] = json.dumps(chart_data)

        # Распределение ответов по каждому вопросу
        q_choices = {
            'q1': dict(QuizRule.Q1_CHOICES),
            'q2': dict(QuizRule.Q2_CHOICES),
            'q3': dict(QuizRule.Q3_CHOICES),
            'q4': dict(QuizRule.Q4_CHOICES),
        }

        questions_stats = []
        for field in ['q1', 'q2', 'q3', 'q4']:
            dist = (
                qs.exclude(**{field: ''})
                .values(field)
                .annotate(count=Count('id'))
                .order_by('-count')
            )
            labels_map = q_choices[field]
            items = [
                {'value': row[field], 'label': labels_map.get(row[field], row[field]), 'count': row['count']}
                for row in dist
            ]
            total_q = sum(i['count'] for i in items)
            for item in items:
                item['pct'] = round(item['count'] / total_q * 100) if total_q else 0
            questions_stats.append({
                'key': field.upper(),
                'items': items,
                'total': total_q,
            })
        ctx['questions_stats'] = questions_stats

        # Топ рекомендованных товаров
        top_products = (
            qs.exclude(result_product__isnull=True)
            .values('result_product__name_ru', 'result_product__slug')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        ctx['top_products'] = top_products

        # Последние 20 прохождений
        ctx['recent'] = qs.select_related('result_product')[:20]

        return ctx
