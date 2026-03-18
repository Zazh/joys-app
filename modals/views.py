from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import InteractiveModal
from .serializers import InteractiveModalSerializer


class InteractiveModalDetailView(APIView):
    """Получить интерактивную модалку по slug."""

    @extend_schema(
        summary='Получить модалку',
        description='Возвращает модалку с шагами для рендеринга на клиенте.',
        responses={200: InteractiveModalSerializer},
        parameters=[
            OpenApiParameter(name='slug', location='path', description='Slug модалки'),
        ],
    )
    def get(self, request, slug):
        try:
            modal = InteractiveModal.objects.prefetch_related(
                'steps', 'steps__inquiry_form'
            ).get(slug=slug, is_active=True)
        except InteractiveModal.DoesNotExist:
            return Response({'error': 'Модалка не найдена.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = InteractiveModalSerializer(modal)
        return Response(serializer.data)
