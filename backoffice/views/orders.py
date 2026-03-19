from django.contrib import messages
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, DetailView

from backoffice.mixins import BackofficeAccessMixin
from orders.models import Order, OrderStatusLog
from regions.models import Region


class OrderListView(BackofficeAccessMixin, ListView):
    template_name = 'backoffice/orders/list.html'
    context_object_name = 'orders'
    paginate_by = 25

    def get_queryset(self):
        qs = Order.objects.select_related('region').annotate(
            items_count=Count('items'),
        ).order_by('-created_at')

        status = self.request.GET.get('status')
        if status and status in Order.Status.values:
            qs = qs.filter(status=status)

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(number__icontains=q) |
                Q(customer_name__icontains=q) |
                Q(customer_phone__icontains=q)
            )

        region = self.request.GET.get('region')
        if region:
            qs = qs.filter(region_id=region)

        date_from = self.request.GET.get('date_from')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)

        date_to = self.request.GET.get('date_to')
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['statuses'] = Order.Status.choices
        ctx['regions'] = Region.objects.filter(is_active=True).order_by('order')
        ctx['current_status'] = self.request.GET.get('status', '')
        ctx['current_q'] = self.request.GET.get('q', '')
        ctx['current_region'] = self.request.GET.get('region', '')
        ctx['current_date_from'] = self.request.GET.get('date_from', '')
        ctx['current_date_to'] = self.request.GET.get('date_to', '')
        return ctx


class OrderDetailView(BackofficeAccessMixin, DetailView):
    template_name = 'backoffice/orders/detail.html'
    context_object_name = 'order'

    def get_object(self):
        return get_object_or_404(
            Order.objects.select_related('region').prefetch_related('items', 'status_logs__changed_by'),
            number=self.kwargs['number'],
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        order = self.object
        transitions = {
            Order.Status.PENDING: [
                (Order.Status.PAID, 'Подтвердить оплату', 'green'),
                (Order.Status.CANCELLED, 'Отменить', 'red'),
            ],
            Order.Status.PAID: [
                (Order.Status.SHIPPED, 'Отправлен', 'blue'),
                (Order.Status.CANCELLED, 'Отменить', 'red'),
            ],
            Order.Status.SHIPPED: [
                (Order.Status.DELIVERED, 'Доставлен', 'green'),
            ],
        }
        ctx['transitions'] = transitions.get(order.status, [])
        return ctx


class OrderStatusUpdateView(BackofficeAccessMixin, View):
    def post(self, request, number):
        order = get_object_or_404(Order, number=number)
        new_status = request.POST.get('new_status')

        allowed = {
            Order.Status.PENDING: {Order.Status.PAID, Order.Status.CANCELLED},
            Order.Status.PAID: {Order.Status.SHIPPED, Order.Status.CANCELLED},
            Order.Status.SHIPPED: {Order.Status.DELIVERED},
        }

        if new_status not in allowed.get(order.status, set()):
            messages.error(request, 'Недопустимый переход статуса.')
            return redirect('backoffice:order_detail', number=number)

        old_status = order.status

        if new_status == Order.Status.PAID:
            order.confirm_payment()
            messages.success(request, f'Заказ #{number} — оплата подтверждена.')
        elif new_status == Order.Status.CANCELLED:
            order.cancel()
            messages.success(request, f'Заказ #{number} отменён.')
        elif new_status == Order.Status.SHIPPED:
            order.status = Order.Status.SHIPPED
            order.save(update_fields=['status'])
            messages.success(request, f'Заказ #{number} — отправлен.')
        elif new_status == Order.Status.DELIVERED:
            order.status = Order.Status.DELIVERED
            order.save(update_fields=['status'])
            messages.success(request, f'Заказ #{number} — доставлен.')

        OrderStatusLog.objects.create(
            order=order,
            old_status=old_status,
            new_status=new_status,
            changed_by=request.user,
        )

        return redirect('backoffice:order_detail', number=number)
