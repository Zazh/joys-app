from django import template
from django.db.models import Avg, Count, F, Q, Value
from django.db.models.functions import Coalesce, Length

from reviews.models import Review

register = template.Library()


@register.simple_tag
def get_featured_reviews():
    """Избранные отзывы: самый длинный в центре, соседи >= 40 символов."""
    MIN_NEIGHBOR_LEN = 40

    reviews = list(
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

    if len(reviews) < 3:
        return reviews

    # reviews[0] — самый длинный (центр)
    # reviews[1] — сосед справа, reviews[-1] — сосед слева
    # Гарантируем что оба >= MIN_NEIGHBOR_LEN символов

    def content_len(r):
        return len(r.text or '') + len(r.pros or '') + len(r.cons or '')

    # Сосед справа (index 1): если короткий — найти первый длинный и поменять
    if content_len(reviews[1]) < MIN_NEIGHBOR_LEN:
        for i in range(2, len(reviews) - 1):
            if content_len(reviews[i]) >= MIN_NEIGHBOR_LEN:
                reviews[1], reviews[i] = reviews[i], reviews[1]
                break

    # Сосед слева (последний): если короткий — найти длинный с конца и поменять
    if content_len(reviews[-1]) < MIN_NEIGHBOR_LEN:
        for i in range(len(reviews) - 2, 1, -1):
            if content_len(reviews[i]) >= MIN_NEIGHBOR_LEN:
                reviews[-1], reviews[i] = reviews[i], reviews[-1]
                break

    return reviews


@register.simple_tag
def get_review_stats():
    """Статистика: средняя оценка, кол-во позитив/негатив по всем отзывам WB."""
    stats = Review.objects.aggregate(
        avg_rating=Avg('rating'),
        total_count=Count('id'),
        positive_count=Count('id', filter=Q(rating__gte=2)),
        negative_count=Count('id', filter=Q(rating=1)),
    )
    total = stats['total_count'] or 1
    negative_count = stats['negative_count']
    negative_percent = round(negative_count / total * 100, 1)

    return {
        'avg_rating': round(stats['avg_rating'] or 0, 1),
        'total_count': stats['total_count'],
        'positive_count': stats['positive_count'],
        'negative_count': negative_count,
        'negative_percent': negative_percent,
    }
