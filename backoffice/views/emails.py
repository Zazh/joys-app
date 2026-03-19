from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView

from backoffice.mixins import BackofficeAccessMixin
from emails.models import EmailLog


class EmailLogListView(BackofficeAccessMixin, ListView):
    template_name = 'backoffice/emails/list.html'
    context_object_name = 'logs'
    paginate_by = 25

    def get_queryset(self):
        qs = EmailLog.objects.order_by('-created_at')

        status = self.request.GET.get('status')
        if status and status in EmailLog.Status.values:
            qs = qs.filter(status=status)

        template = self.request.GET.get('template')
        if template:
            qs = qs.filter(template_slug=template)

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(to_email__icontains=q) | Q(subject__icontains=q))

        date_from = self.request.GET.get('date_from')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)

        date_to = self.request.GET.get('date_to')
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['statuses'] = EmailLog.Status.choices
        ctx['templates'] = (
            EmailLog.objects.values_list('template_slug', flat=True)
            .distinct().order_by('template_slug')
        )
        ctx['current_status'] = self.request.GET.get('status', '')
        ctx['current_template'] = self.request.GET.get('template', '')
        ctx['current_q'] = self.request.GET.get('q', '')
        ctx['current_date_from'] = self.request.GET.get('date_from', '')
        ctx['current_date_to'] = self.request.GET.get('date_to', '')
        return ctx


class EmailLogDetailView(BackofficeAccessMixin, View):
    def get(self, request, pk):
        from django.shortcuts import render
        log = get_object_or_404(EmailLog, pk=pk)
        return render(request, 'backoffice/emails/detail.html', {'log': log})


class EmailLogRetryView(BackofficeAccessMixin, View):
    def post(self, request, pk):
        log = get_object_or_404(EmailLog, pk=pk)
        if log.status != EmailLog.Status.FAILED:
            messages.error(request, 'Повторная отправка доступна только для писем со статусом «Ошибка».')
            return redirect('backoffice:email_log_list')

        from emails.service import _send_via_api
        from django.utils import timezone

        ok, error = _send_via_api(log.to_email, log.subject, log.body)
        log.attempts += 1
        if ok:
            log.status = EmailLog.Status.SENT
            log.sent_at = timezone.now()
            log.error = ''
            log.save(update_fields=['status', 'sent_at', 'attempts', 'error'])
            messages.success(request, f'Письмо успешно отправлено на {log.to_email}.')
        else:
            log.error = error
            log.save(update_fields=['attempts', 'error'])
            messages.error(request, f'Ошибка повторной отправки: {error}')

        return redirect('backoffice:email_log_detail', pk=pk)
