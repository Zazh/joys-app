from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password1 = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    def validate_email(self, value):
        email = value.lower()
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError('Пользователь с таким email уже существует.')
        return email

    def validate(self, data):
        if data['password1'] != data['password2']:
            raise serializers.ValidationError({'password2': 'Пароли не совпадают.'})
        validate_password(data['password1'])
        return data

    def create(self, validated_data):
        return User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password1'],
        )


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class ProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone', 'full_name']
        read_only_fields = ['email']

    def get_full_name(self, obj):
        return obj.get_full_name()


class UserDataSerializer(serializers.Serializer):
    """Краткие данные пользователя для ответа после login/register."""
    email = serializers.EmailField()
    full_name = serializers.CharField()
    phone = serializers.CharField(required=False)
