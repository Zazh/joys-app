import logging

from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.csrf import csrf_failure_reason
from core.ratelimit import get_client_ip, hit, is_rate_limited, record_attempt
from . import antispam
from .models import InquiryForm, InquirySubmission, InquiryFieldValue
from .serializers import InquiryFormSerializer, InquirySubmissionSerializer

logger = logging.getLogger(__name__)

# Два лимита по IP. Квоту заявок списывает только принятая заявка (и сработавшая
# приманка) — иначе пять опечаток оставят человека без формы на час. Чтобы это не
# открыло дверь потоку заведомо невалидных тел, сверху стоит широкий лимит на все
# запросы к эндпоинту: живому человеку его не достать, боту — за минуту.
ACCEPTED_QUOTA = {'scope': 'inquiry', 'window': 3600}
ACCEPTED_MAX = 5
REQUEST_QUOTA = {'scope': 'inquiry-raw', 'window': 3600}
REQUEST_MAX = 60


class InquiryFormDetailView(APIView):
    """Получить структуру формы по slug."""

    @extend_schema(
        summary='Получить форму',
        description='Возвращает структуру формы с полями для рендеринга на клиенте.',
        responses={200: InquiryFormSerializer},
        parameters=[
            OpenApiParameter(name='slug', location='path', description='Slug формы'),
        ],
    )
    def get(self, request, slug):
        try:
            form = InquiryForm.objects.prefetch_related('fields').get(slug=slug, is_active=True)
        except InquiryForm.DoesNotExist:
            return Response({'error': _('Форма не найдена.')}, status=status.HTTP_404_NOT_FOUND)

        serializer = InquiryFormSerializer(form)
        return Response(serializer.data)


class InquirySubmitView(APIView):
    """Отправить заявку по форме."""

    @staticmethod
    def _too_many(remaining_seconds):
        """429 с человеческим текстом: через сколько минут пробовать снова."""
        minutes = remaining_seconds // 60 + 1
        return Response(
            {'ok': False, 'error': _('Слишком много заявок. Попробуйте через %(min)s мин.') % {'min': minutes}},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    @extend_schema(
        summary='Отправить заявку',
        description='Валидирует данные по полям формы и сохраняет заявку.',
        request=InquirySubmissionSerializer,
        responses={
            201: OpenApiExample('Success', value={'ok': True, 'success_title': '...', 'success_text': '...'}),
            400: OpenApiExample('Validation error', value={'ok': False, 'errors': {'name': '...'}}),
        },
        parameters=[
            OpenApiParameter(name='slug', location='path', description='Slug формы'),
        ],
    )
    def post(self, request, slug):
        # DRF-вьюхи csrf_exempt, а форма публичная — проверяем токен сами,
        # иначе заявки можно слать с чужого сайта браузером посетителя
        csrf_reason = csrf_failure_reason(request)
        if csrf_reason:
            logger.warning('Заявка %s отклонена по CSRF: %s', slug, csrf_reason)
            return Response(
                {'ok': False, 'error': _('Страница устарела. Обновите её и отправьте ещё раз.')},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Широкий лимит на любые обращения — от потока заведомо мусорных тел.
        # Здесь считаем каждый запрос, поэтому hit(), а не is_rate_limited()
        limited, remaining = hit(request, max_attempts=REQUEST_MAX, **REQUEST_QUOTA)
        if limited:
            return self._too_many(remaining)

        try:
            form = InquiryForm.objects.prefetch_related('fields').get(slug=slug, is_active=True)
        except InquiryForm.DoesNotExist:
            return Response({'error': _('Форма не найдена.')}, status=status.HTTP_404_NOT_FOUND)

        # Квота заявок: проверяем здесь, списываем ниже — только за принятую
        limited, remaining = is_rate_limited(request, max_attempts=ACCEPTED_MAX, **ACCEPTED_QUOTA)
        if limited:
            return self._too_many(remaining)

        # Антиспам до валидации: бот не должен по ответу узнать, что не так с данными
        antispam_fields = antispam.collect_fields(request)
        if antispam.is_honeypot_filled(antispam_fields):
            # Отвечаем как на нормальную заявку, но ничего не сохраняем.
            # Квоту боту засчитываем — иначе приманка даёт бесплатный обход лимита
            record_attempt(request, **ACCEPTED_QUOTA)
            return Response({
                'ok': True,
                'success_title': form.success_title,
                'success_text': form.success_text,
            })
        if antispam.is_too_fast(antispam_fields):
            # Не молча: живой человек мог успеть за 3 секунды — повтор пройдёт
            return Response(
                {'ok': False, 'error': _('Форма отправлена слишком быстро. Попробуйте ещё раз.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = InquirySubmissionSerializer(data=request.data, inquiry_form=form)
        if not serializer.is_valid():
            return Response(
                {'ok': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # IP берём из доверенного элемента XFF — клиентскую часть заголовка
        # подделать ничего не стоит, а поле в БД строго типизировано
        ip = get_client_ip(request)

        submission = InquirySubmission.objects.create(
            form=form,
            ip_address=ip or None,
        )

        # Сохраняем значения полей (сериализатор отдал только поля формы, без пустых)
        fields_by_key = {f.key: f for f in form.fields.all()}
        InquiryFieldValue.objects.bulk_create([
            InquiryFieldValue(submission=submission, field=fields_by_key[key], value=value)
            for key, value in serializer.validated_data['data'].items()
        ])

        record_attempt(request, **ACCEPTED_QUOTA)

        # Email-уведомление администратору
        from emails.service import send_inquiry_notification
        send_inquiry_notification(submission)

        return Response({
            'ok': True,
            'success_title': form.success_title,
            'success_text': form.success_text,
        }, status=status.HTTP_201_CREATED)
