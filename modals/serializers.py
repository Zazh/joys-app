from rest_framework import serializers

from .models import InteractiveModal, ModalStep


class ModalStepSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    inquiry_form_slug = serializers.SerializerMethodField()

    class Meta:
        model = ModalStep
        fields = [
            'order', 'step_type',
            'image_url', 'text', 'button_text', 'badge_text',
            'inquiry_form_slug',
            'cta_text', 'cta_url',
        ]

    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return None

    def get_inquiry_form_slug(self, obj):
        if obj.inquiry_form:
            return obj.inquiry_form.slug
        return None


class InteractiveModalSerializer(serializers.ModelSerializer):
    steps = ModalStepSerializer(many=True, read_only=True)

    class Meta:
        model = InteractiveModal
        fields = ['slug', 'title', 'theme', 'trigger_text', 'steps']
