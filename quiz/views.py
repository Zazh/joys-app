from django.utils.translation import get_language
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import ProductCharacteristic
from .models import QuizRule, QuizBackground, QuizSubmission
from .serializers import QuizAnswersSerializer, QuizProductSerializer


class QuizResultView(APIView):
    """POST: подбор товара по ответам квиза."""

    @extend_schema(
        summary='Результат квиза',
        description='Возвращает подходящие товары по ответам на вопросы квиза.',
        request=QuizAnswersSerializer,
        responses={200: QuizProductSerializer(many=True)},
    )
    def post(self, request):
        serializer = QuizAnswersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        products = QuizRule.get_results(d['q1'], d['q2'], d['q3'], d['q4'])

        # Сохранить ответы для аналитики
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        ip = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')
        session_key = request.session.session_key or ''
        QuizSubmission.objects.create(
            q1=d['q1'], q2=d['q2'], q3=d['q3'], q4=d['q4'],
            result_product=products[0] if products else None,
            ip_address=ip,
            session_key=session_key,
        )

        if not products:
            return Response({'ok': False, 'error': 'No matching product'})

        bg_map = {
            bg.key: bg
            for bg in QuizBackground.objects.filter(is_active=True)
        }

        items = [self._serialize_product(p, bg_map) for p in products]
        return Response({'ok': True, 'products': items})

    # Маппинг значений характеристик → ключ фона
    BG_KEY_MAP = {
        'Банан': 'banana',
        'Клубника': 'strawberry',
        'Шоколад': 'chocolate',
        'Точечно-ребристая': 'dotted-ribbed',
        'Точечная (кошачий язык)': 'dotted-ribbed',
    }

    def _serialize_product(self, product, bg_map):
        lang = get_language()
        if lang == 'kk' and product.transparent_image_kk:
            image_url = product.transparent_image_kk.url
        elif product.transparent_image:
            image_url = product.transparent_image.url
        else:
            cover = product.get_cover_image()
            if cover:
                if lang == 'kk' and cover.thumbnail_kk:
                    image_url = cover.thumbnail_kk.url
                elif lang == 'kk' and cover.image_kk:
                    image_url = cover.image_kk.url
                elif cover.thumbnail:
                    image_url = cover.thumbnail.url
                else:
                    image_url = cover.image.url
            else:
                image_url = ''

        bg_key = self._get_bg_key(product)
        bg = bg_map.get(bg_key)

        return {
            'name': str(product.name),
            'slug': product.slug,
            'bg_key': bg_key,
            'bg_url': bg.image.url if bg else '',
            'bg_dark': bg.is_dark_theme if bg else False,
            'url': product.get_absolute_url(),
            'image_url': image_url,
        }

    def _get_bg_key(self, product):
        chars = dict(
            ProductCharacteristic.objects
            .filter(product=product, characteristic__name_ru__in=['Аромат', 'Текстура', 'Объём смазки'])
            .values_list('characteristic__name_ru', 'value_ru')
        )

        aroma = chars.get('Аромат', '')
        if aroma and aroma != 'Без аромата':
            return self.BG_KEY_MAP.get(aroma, '')

        texture = chars.get('Текстура', '')
        if texture and texture != 'Гладкая':
            return self.BG_KEY_MAP.get(texture, '')

        lube_vol = chars.get('Объём смазки', '')
        if lube_vol and int(lube_vol) > 1000:
            return 'triple-lube'

        return ''
