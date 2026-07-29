from django.core.management.base import BaseCommand

from inquiries.models import InquiryForm, InquiryField

FORM = {
    'title_ru': 'Напишите нам',
    'title_kk': 'Бізге жазыңыз',
    'title_en': 'Write to us',
    'description_ru': 'Ответим на почту или в мессенджер — обычно в течение рабочего дня.',
    'description_kk': 'Поштаға немесе мессенджерге жауап береміз — әдетте жұмыс күні ішінде.',
    'description_en': 'We reply by email or messenger — usually within one business day.',
    'success_title_ru': 'Спасибо!',
    'success_title_kk': 'Рахмет!',
    'success_title_en': 'Thank you!',
    'success_text_ru': 'Мы получили ваше обращение и ответим в ближайшее время.',
    'success_text_kk': 'Хабарламаңызды алдық, жақын арада жауап береміз.',
    'success_text_en': 'We have received your message and will reply shortly.',
    'submit_text_ru': 'Отправить',
    'submit_text_kk': 'Жіберу',
    'submit_text_en': 'Send',
    'email_notify_to': 'drjoysoriginal@gmail.com',
    'is_active': True,
}

FIELDS = [
    {
        'key': 'name',
        'field_type': 'text',
        'is_required': True,
        'label_ru': 'Имя', 'label_kk': 'Есіміңіз', 'label_en': 'Name',
        'placeholder_ru': 'Как к вам обращаться',
        'placeholder_kk': 'Сізге қалай жүгінейік',
        'placeholder_en': 'How should we address you',
    },
    {
        # Одно поле на почту и телефон: человек оставляет то, чем сам пользуется.
        # Тип text, а не phone — иначе маска не даст ввести email
        'key': 'contact',
        'field_type': 'text',
        'is_required': True,
        'label_ru': 'Email или телефон', 'label_kk': 'Email немесе телефон', 'label_en': 'Email or phone',
        'placeholder_ru': 'Куда прислать ответ',
        'placeholder_kk': 'Жауапты қайда жіберейік',
        'placeholder_en': 'Where to send the reply',
    },
    {
        'key': 'topic',
        'field_type': 'select',
        'is_required': False,
        'label_ru': 'Тема', 'label_kk': 'Тақырып', 'label_en': 'Topic',
        'placeholder_ru': 'Выберите тему',
        'placeholder_kk': 'Тақырыпты таңдаңыз',
        'placeholder_en': 'Choose a topic',
        'choices_text_ru': 'order|Вопрос по заказу\npartnership|Сотрудничество\nother|Другое',
        'choices_text_kk': 'order|Тапсырыс бойынша сұрақ\npartnership|Ынтымақтастық\nother|Басқа',
        'choices_text_en': 'order|Order question\npartnership|Partnership\nother|Other',
    },
    {
        'key': 'message',
        'field_type': 'textarea',
        'is_required': True,
        'label_ru': 'Сообщение', 'label_kk': 'Хабарлама', 'label_en': 'Message',
        'placeholder_ru': 'Расскажите, чем помочь',
        'placeholder_kk': 'Немен көмектесе алатынымызды жазыңыз',
        'placeholder_en': 'Tell us how we can help',
    },
]


def with_base(values):
    """Дописывает базовые колонки значениями из `_ru`.

    modeltranslation читает поле по активному языку, но исходная колонка
    участвует в Meta.ordering и в старых записях заполнена — держим так же.
    """
    base = {key.removesuffix('_ru'): value for key, value in values.items() if key.endswith('_ru')}
    return {**values, **base}


class Command(BaseCommand):
    help = 'Создать/обновить форму обращения contact для страницы контактов'

    def handle(self, *args, **options):
        form, created = InquiryForm.objects.update_or_create(
            slug='contact',
            defaults=with_base(FORM),
        )

        for order, field in enumerate(FIELDS):
            InquiryField.objects.update_or_create(
                form=form,
                key=field['key'],
                defaults=with_base({**field, 'order': order}),
            )

        action = 'Создана' if created else 'Обновлена'
        self.stdout.write(self.style.SUCCESS(
            f'{action} форма contact ({len(FIELDS)} поля), уведомления → {form.email_notify_to}'
        ))
