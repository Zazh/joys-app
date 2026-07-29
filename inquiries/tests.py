"""Тесты формы заявок: антиспам (honeypot, time-trap) и сохранение заявки."""

import json
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings

from .antispam import HONEYPOT_FIELD, TIMESTAMP_FIELD, make_timestamp_token
from .models import InquiryForm, InquiryField, InquirySubmission

LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


def old_token(seconds_ago=10):
    """Метка времени, как будто форму отрисовали seconds_ago секунд назад."""
    import time
    with patch('django.core.signing.time.time', return_value=time.time() - seconds_ago):
        return make_timestamp_token()


@override_settings(CACHES=LOCMEM)
class InquirySubmitTests(TestCase):
    """Отправка заявки на /api/inquiries/<slug>/submit/."""

    @classmethod
    def setUpTestData(cls):
        cls.form = InquiryForm.objects.create(
            slug='contact', title='Напишите нам',
            email_notify_to='drjoysoriginal@gmail.com',
        )
        InquiryField.objects.create(form=cls.form, key='name', label='Имя', order=0)
        InquiryField.objects.create(
            form=cls.form, key='topic', label='Тема', field_type='select',
            choices_text='order|Вопрос по заказу\nother|Другое',
            is_required=False, order=1,
        )
        InquiryField.objects.create(
            form=cls.form, key='message', label='Сообщение',
            field_type='textarea', order=2,
        )

    def setUp(self):
        cache.clear()
        # Уведомление шлётся через внешний API — в тестах только проверяем вызов
        patcher = patch('emails.service.send_inquiry_notification')
        self.notify = patcher.start()
        self.addCleanup(patcher.stop)

    def submit(self, **data):
        payload = {'name': 'Айдар', 'message': 'Вопрос по доставке', **data}
        return self.client.post(
            '/api/inquiries/contact/submit/',
            data=json.dumps({'data': payload}),
            content_type='application/json',
        )

    def test_valid_submission_saves_and_notifies(self):
        resp = self.submit(topic='order', **{TIMESTAMP_FIELD: old_token()})

        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.json()['ok'])
        submission = InquirySubmission.objects.get()
        self.assertEqual(
            submission.get_data_dict(),
            {'name': 'Айдар', 'topic': 'order', 'message': 'Вопрос по доставке'},
        )
        self.notify.assert_called_once_with(submission)

    def test_antispam_fields_not_saved_as_answers(self):
        self.submit(**{TIMESTAMP_FIELD: old_token(), HONEYPOT_FIELD: ''})

        self.assertNotIn(TIMESTAMP_FIELD, InquirySubmission.objects.get().get_data_dict())

    def test_honeypot_filled_looks_successful_but_saves_nothing(self):
        resp = self.submit(**{HONEYPOT_FIELD: 'http://spam.example', TIMESTAMP_FIELD: old_token()})

        # Боту отвечаем как обычному человеку, чтобы он не подбирал обход
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])
        self.assertFalse(InquirySubmission.objects.exists())
        self.notify.assert_not_called()

    def test_submit_faster_than_three_seconds_rejected(self):
        resp = self.submit(**{TIMESTAMP_FIELD: make_timestamp_token()})

        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()['ok'])
        self.assertFalse(InquirySubmission.objects.exists())

    def test_forged_timestamp_rejected(self):
        resp = self.submit(**{TIMESTAMP_FIELD: 'inquiry:1abcde:подпись-не-наша'})

        self.assertEqual(resp.status_code, 400)
        self.assertFalse(InquirySubmission.objects.exists())

    def test_missing_timestamp_still_accepted(self):
        # Старый бандл или страница из кеша браузера — заявку не теряем
        resp = self.submit()

        self.assertEqual(resp.status_code, 201)
        self.assertTrue(InquirySubmission.objects.exists())

    def test_required_field_error(self):
        resp = self.submit(name='', **{TIMESTAMP_FIELD: old_token()})

        self.assertEqual(resp.status_code, 400)
        self.assertIn('name', resp.json()['errors']['data'])
        self.assertFalse(InquirySubmission.objects.exists())

    def test_unknown_select_value_rejected(self):
        resp = self.submit(topic='hack', **{TIMESTAMP_FIELD: old_token()})

        self.assertEqual(resp.status_code, 400)
        self.assertIn('topic', resp.json()['errors']['data'])

    def test_rate_limit_after_five_submissions(self):
        for _ in range(5):
            self.assertEqual(self.submit(**{TIMESTAMP_FIELD: old_token()}).status_code, 201)

        resp = self.submit(**{TIMESTAMP_FIELD: old_token()})
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(InquirySubmission.objects.count(), 5)
