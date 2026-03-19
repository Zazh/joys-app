from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import redirect
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.translation import get_language, gettext as _
from django.views.generic import TemplateView

from pages.models import ServicePage
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.cart import merge_session_to_db
from emails.service import send_welcome_email, send_password_reset, send_email_verification
from .models import User
from .serializers import RegisterSerializer, LoginSerializer, ProfileSerializer


class RegisterView(APIView):
    """Регистрация нового пользователя."""

    @extend_schema(
        summary='Регистрация',
        request=RegisterSerializer,
        responses={201: ProfileSerializer},
    )
    def post(self, request):
        if request.user.is_authenticated:
            return Response(
                {'ok': False, 'errors': {'__all__': [_('Вы уже авторизованы.')]}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'ok': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        merge_session_to_db(request)

        # Refresh user из БД чтобы last_login был актуальным после login()
        user.refresh_from_db()

        send_welcome_email(user)

        # Генерируем токен ПОСЛЕ login() — чтобы last_login в токене совпал с БД
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        lang = get_language() or 'ru'
        verify_url = f'{settings.SITE_URL}/{lang}/accounts/verify-email/{uid}/{token}/'
        send_email_verification(user, verify_url)

        return Response({
            'ok': True,
            'redirect_url': f'/{lang}/accounts/check-email/',
            'data': {
                'email': user.email,
                'full_name': user.get_full_name(),
            },
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """Вход по email + пароль."""

    @extend_schema(
        summary='Вход',
        request=LoginSerializer,
        responses={200: ProfileSerializer},
    )
    def post(self, request):
        if request.user.is_authenticated:
            return Response(
                {'ok': False, 'errors': {'__all__': [_('Вы уже авторизованы.')]}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'ok': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(
            request,
            email=serializer.validated_data['email'],
            password=serializer.validated_data['password'],
        )
        if user is None:
            return Response(
                {'ok': False, 'errors': {'__all__': [_('Неверный email или пароль.')]}},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        login(request, user)
        merge_session_to_db(request)
        return Response({
            'ok': True,
            'data': {
                'email': user.email,
                'full_name': user.get_full_name(),
                'phone': user.phone,
            },
        })


class LogoutView(APIView):
    """Выход."""

    @extend_schema(summary='Выход')
    def post(self, request):
        logout(request)
        return Response({'ok': True})


class ProfileView(APIView):
    """Профиль — чтение и обновление."""

    @extend_schema(summary='Получить профиль', responses={200: ProfileSerializer})
    def get(self, request):
        if not request.user.is_authenticated:
            return Response(
                {'ok': False, 'errors': {'__all__': [_('Требуется авторизация.')]}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        user = request.user
        return Response({
            'ok': True,
            'data': ProfileSerializer(user).data,
        })

    @extend_schema(summary='Обновить профиль', request=ProfileSerializer, responses={200: ProfileSerializer})
    def post(self, request):
        if not request.user.is_authenticated:
            return Response(
                {'ok': False, 'errors': {'__all__': [_('Требуется авторизация.')]}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'ok': True,
                'data': ProfileSerializer(request.user).data,
            })
        return Response({'ok': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetRequestView(APIView):
    """Запрос сброса пароля — отправляет email со ссылкой."""

    @extend_schema(summary='Запрос сброса пароля')
    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        if not email:
            return Response(
                {'ok': False, 'errors': {'email': [_('Укажите email.')]}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Всегда отвечаем 200 чтобы не раскрывать наличие аккаунта
        try:
            user = User.objects.get(email=email)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            lang = get_language() or 'ru'
            reset_url = f'{settings.SITE_URL}/{lang}/accounts/password-reset/{uid}/{token}/'
            send_password_reset(user, reset_url)
        except User.DoesNotExist:
            pass

        return Response({'ok': True, 'message': _('Если аккаунт существует, письмо отправлено.')})


class PasswordResetConfirmView(APIView):
    """Установка нового пароля по токену из email."""

    @extend_schema(summary='Установка нового пароля')
    def post(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {'ok': False, 'errors': {'__all__': [_('Недействительная ссылка.')]}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not default_token_generator.check_token(user, token):
            return Response(
                {'ok': False, 'errors': {'__all__': [_('Ссылка истекла или уже использована.')]}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        password = request.data.get('password', '')
        if len(password) < 8:
            return Response(
                {'ok': False, 'errors': {'password': [_('Минимум 8 символов.')]}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(password)
        user.save()
        return Response({'ok': True, 'message': _('Пароль успешно изменён.')})


class EmailVerifyView(TemplateView):
    """Подтверждение email по ссылке из письма — показывает страницу."""

    template_name = 'accounts/email_verified.html'

    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            page = ServicePage.objects.filter(slug='email_error').first()
            return self.render_to_response({
                'success': False,
                'page': page,
                'page_type': 'email_verify',
            })

        if not default_token_generator.check_token(user, token):
            page = ServicePage.objects.filter(slug='email_error').first()
            return self.render_to_response({
                'success': False,
                'page': page,
                'page_type': 'email_verify',
            })

        user.is_active = True
        user.save(update_fields=['is_active'])

        # Автоматически залогинить пользователя
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')

        page = ServicePage.objects.filter(slug='email_verified').first()
        return self.render_to_response({
            'success': True,
            'page': page,
            'page_type': 'email_verify',
        })


class CheckEmailView(TemplateView):
    """Страница «Проверьте почту» после регистрации."""

    template_name = 'accounts/check_email.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_type'] = 'check_email'
        ctx['page'] = ServicePage.objects.filter(slug='check_email').first()
        if self.request.user.is_authenticated:
            ctx['user_email'] = self.request.user.email
        return ctx


class SSOCallbackView(TemplateView):
    """Popup callback page — sends postMessage to parent and closes."""

    template_name = 'accounts/sso_callback.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['sso_success'] = self.request.user.is_authenticated
        return ctx
