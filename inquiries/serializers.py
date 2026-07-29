from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext as _
from rest_framework import serializers

from .models import InquiryForm, InquiryField, InquirySubmission, InquiryFieldValue

# Потолок длины значения: без него в TextField уедет всё, что влезло в тело
# запроса (по умолчанию 2.5 МБ) — и оттуда же в письмо администратору
MAX_LENGTHS = {'textarea': 5000}
MAX_LENGTH_DEFAULT = 200


class InquiryFieldSerializer(serializers.ModelSerializer):
    choices = serializers.SerializerMethodField()

    class Meta:
        model = InquiryField
        fields = ['key', 'label', 'field_type', 'placeholder', 'choices', 'is_required', 'min_value', 'max_value']

    def get_choices(self, obj):
        return obj.get_choices() or None


class InquiryFormSerializer(serializers.ModelSerializer):
    fields = InquiryFieldSerializer(many=True, read_only=True)

    class Meta:
        model = InquiryForm
        fields = ['slug', 'title', 'description', 'success_title', 'success_text', 'submit_text', 'fields']


class InquirySubmissionSerializer(serializers.Serializer):
    """Валидация отправки формы — поля проверяются динамически."""
    data = serializers.DictField(child=serializers.CharField(allow_blank=True))

    def __init__(self, *args, inquiry_form=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.inquiry_form = inquiry_form

    def validate_data(self, value):
        """Проверяет присланные значения и отдаёт только поля формы, без пустых."""
        if not self.inquiry_form:
            return value

        errors = {}
        cleaned = {}
        for field in self.inquiry_form.fields.all():
            # DictField(child=CharField) уже привёл значения к строкам и обрезал пробелы
            val = value.get(field.key, '')
            if not val:
                if field.is_required:
                    errors[field.key] = _('Поле «%(label)s» обязательно.') % {'label': field.label}
                continue

            error = self._field_error(field, val)
            if error:
                errors[field.key] = error
            else:
                cleaned[field.key] = val

        if errors:
            raise serializers.ValidationError(errors)

        return cleaned

    @staticmethod
    def _field_error(field, val):
        """Текст ошибки для непустого значения или None, если всё в порядке."""
        max_length = MAX_LENGTHS.get(field.field_type, MAX_LENGTH_DEFAULT)
        if len(val) > max_length:
            return _('Слишком длинно: максимум %(max)s символов.') % {'max': max_length}

        if field.field_type == 'email':
            try:
                validate_email(val)
            except DjangoValidationError:
                return _('Некорректный email.')

        elif field.field_type == 'number':
            try:
                num = int(val)
            except (ValueError, TypeError):
                return _('Введите число.')
            if field.min_value is not None and num < field.min_value:
                return _('Минимальное значение: %(value)s.') % {'value': field.min_value}
            if field.max_value is not None and num > field.max_value:
                return _('Максимальное значение: %(value)s.') % {'value': field.max_value}

        elif field.field_type in ('select', 'radio'):
            valid_values = [c['value'] for c in field.get_choices()]
            if valid_values and val not in valid_values:
                return _('Недопустимое значение.')

        return None
