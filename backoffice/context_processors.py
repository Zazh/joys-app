from orders.models import Order
from inquiries.models import InquirySubmission

from backoffice.views.inquiries import visible_submissions


def backoffice_badges(request):
    if not request.path.startswith('/backoffice/'):
        return {}
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {}
    user = request.user
    if getattr(user, 'is_store_manager', False):
        # заказов у роли нет, заявки — только её формы
        return {
            'bo_unprocessed_inquiries': visible_submissions(user).filter(
                is_processed=False).count(),
        }
    if not getattr(user, 'is_full_staff', False):
        return {}
    return {
        'bo_pending_orders': Order.objects.filter(status=Order.Status.PENDING).count(),
        'bo_unprocessed_inquiries': InquirySubmission.objects.filter(is_processed=False).count(),
    }
