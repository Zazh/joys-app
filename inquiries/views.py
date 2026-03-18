from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import InquiryForm, InquirySubmission, InquiryFieldValue
from .serializers import InquiryFormSerializer, InquirySubmissionSerializer


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
            return Response({'error': 'Форма не найдена.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = InquiryFormSerializer(form)
        return Response(serializer.data)


class InquirySubmitView(APIView):
    """Отправить заявку по форме."""

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
        try:
            form = InquiryForm.objects.prefetch_related('fields').get(slug=slug, is_active=True)
        except InquiryForm.DoesNotExist:
            return Response({'error': 'Форма не найдена.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = InquirySubmissionSerializer(data=request.data, inquiry_form=form)
        if not serializer.is_valid():
            return Response(
                {'ok': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Сохраняем
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
        if ',' in ip:
            ip = ip.split(',')[0].strip()

        submission = InquirySubmission.objects.create(
            form=form,
            ip_address=ip or None,
        )

        # Сохраняем значения полей
        data = serializer.validated_data['data']
        fields_by_key = {f.key: f for f in form.fields.all()}
        field_values = []
        for key, value in data.items():
            if key in fields_by_key and value:
                field_values.append(InquiryFieldValue(
                    submission=submission,
                    field=fields_by_key[key],
                    value=str(value),
                ))
        if field_values:
            InquiryFieldValue.objects.bulk_create(field_values)

        # Email-уведомление администратору
        from .emails import send_inquiry_notification
        send_inquiry_notification(submission)

        return Response({
            'ok': True,
            'success_title': form.success_title,
            'success_text': form.success_text,
        }, status=status.HTTP_201_CREATED)
