from rest_framework import serializers


class QuizAnswersSerializer(serializers.Serializer):
    q1 = serializers.CharField(required=False, allow_blank=True, default='')
    q2 = serializers.CharField(required=False, allow_blank=True, default='')
    q3 = serializers.CharField(required=False, allow_blank=True, default='')
    q4 = serializers.CharField(required=False, allow_blank=True, default='')


class QuizProductSerializer(serializers.Serializer):
    name = serializers.CharField()
    slug = serializers.CharField()
    bg_key = serializers.CharField()
    bg_url = serializers.CharField()
    bg_dark = serializers.BooleanField()
    url = serializers.CharField()
    image_url = serializers.CharField()
