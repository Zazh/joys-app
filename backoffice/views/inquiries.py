from django.shortcuts import get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import ListView, DetailView

from backoffice.mixins import BackofficeAccessMixin
from inquiries.models import InquiryForm, InquirySubmission, InquiryStatusLog


class InquiryListView(BackofficeAccessMixin, ListView):
    template_name = 'backoffice/inquiries/list.html'
    context_object_name = 'submissions'
    paginate_by = 25

    def get_queryset(self):
        qs = InquirySubmission.objects.select_related('form').order_by('-created_at')

        form_slug = self.request.GET.get('form')
        if form_slug:
            qs = qs.filter(form__slug=form_slug)

        processed = self.request.GET.get('processed')
        if processed == 'yes':
            qs = qs.filter(is_processed=True)
        elif processed == 'no':
            qs = qs.filter(is_processed=False)

        date_from = self.request.GET.get('date_from')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)

        date_to = self.request.GET.get('date_to')
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['forms'] = InquiryForm.objects.filter(is_active=True).order_by('title')
        ctx['current_form'] = self.request.GET.get('form', '')
        ctx['current_processed'] = self.request.GET.get('processed', '')
        ctx['current_date_from'] = self.request.GET.get('date_from', '')
        ctx['current_date_to'] = self.request.GET.get('date_to', '')
        return ctx


class InquiryDetailView(BackofficeAccessMixin, DetailView):
    template_name = 'backoffice/inquiries/detail.html'
    context_object_name = 'submission'

    def get_object(self):
        return get_object_or_404(
            InquirySubmission.objects.select_related('form').prefetch_related(
                'values__field', 'status_logs__changed_by',
            ),
            pk=self.kwargs['pk'],
        )


class InquiryToggleProcessedView(BackofficeAccessMixin, View):
    def post(self, request, pk):
        submission = get_object_or_404(InquirySubmission, pk=pk)
        submission.is_processed = not submission.is_processed
        submission.save(update_fields=['is_processed'])

        InquiryStatusLog.objects.create(
            submission=submission,
            action='processed' if submission.is_processed else 'unprocessed',
            changed_by=request.user,
        )

        next_url = request.POST.get('next', '')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=None):
            return redirect(next_url)
        return redirect('backoffice:inquiry_detail', pk=pk)
