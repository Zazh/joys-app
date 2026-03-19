from django.utils.translation import gettext as _
from rest_framework import serializers

from .models import InquiryForm, InquiryField, InquirySubmission, InquiryFieldValue


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
        if not self.inquiry_form:
            return value

        errors = {}
        for field in self.inquiry_form.fields.all():
            val = value.get(field.key, '').strip() if isinstance(value.get(field.key), str) else value.get(field.key, '')

            # Required
            if field.is_required and not val:
                errors[field.key] = _('Поле «%(label)s» обязательно.') % {'label': field.label}
                continue

            if not val:
                continue

            # Email
            if field.field_type == 'email':
                if '@' not in val or '.' not in val.split('@')[-1]:
                    errors[field.key] = _('Некорректный email.')

            # Number
            if field.field_type == 'number':
                try:
                    num = int(val)
                    if field.min_value is not None and num < field.min_value:
                        errors[field.key] = _('Минимальное значение: %(value)s.') % {'value': field.min_value}
                    if field.max_value is not None and num > field.max_value:
                        errors[field.key] = _('Максимальное значение: %(value)s.') % {'value': field.max_value}
                except (ValueError, TypeError):
                    errors[field.key] = _('Введите число.')

            # Select / radio
            if field.field_type in ('select', 'radio'):
                valid_values = [c['value'] for c in field.get_choices()]
                if valid_values and val not in valid_values:
                    errors[field.key] = _('Недопустимое значение.')

        if errors:
            raise serializers.ValidationError(errors)

        return value
