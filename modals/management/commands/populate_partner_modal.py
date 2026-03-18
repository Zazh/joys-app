from django.core.management.base import BaseCommand

from inquiries.models import InquiryForm
from modals.models import InteractiveModal, ModalStep


class Command(BaseCommand):
    help = 'Создать InteractiveModal для партнёрской формы'

    def handle(self, *args, **options):
        partner_form = InquiryForm.objects.filter(slug='partner-request').first()
        if not partner_form:
            self.stderr.write('InquiryForm partner-request не найдена. Сначала создайте её.')
            return

        modal, created = InteractiveModal.objects.update_or_create(
            slug='partner',
            defaults={
                'title': 'Стать партнёром',
                'theme': 'light',
                'trigger_text': 'Оставить заявку',
                'is_active': True,
            },
        )

        ModalStep.objects.filter(modal=modal).delete()
        ModalStep.objects.create(
            modal=modal,
            order=1,
            step_type='form',
            text='<h2 class="modal-title">Стать<br>партнером</h2>',
            inquiry_form=partner_form,
        )

        action = 'Создана' if created else 'Обновлена'
        self.stdout.write(self.style.SUCCESS(f'{action} модалка partner (1 шаг: форма)'))
