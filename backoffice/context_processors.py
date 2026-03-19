from orders.models import Order
from inquiries.models import InquirySubmission


def backoffice_badges(request):
    if not request.path.startswith('/backoffice/'):
        return {}
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {}
    if not getattr(request.user, 'is_staff_role', False):
        return {}
    return {
        'bo_pending_orders': Order.objects.filter(status=Order.Status.PENDING).count(),
        'bo_unprocessed_inquiries': InquirySubmission.objects.filter(is_processed=False).count(),
    }
