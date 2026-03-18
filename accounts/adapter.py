from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from orders.cart import merge_session_to_db


class AccountAdapter(DefaultAccountAdapter):
    """Redirect после allauth-логина → SSO callback страницу."""

    def login(self, request, user):
        super().login(request, user)
        merge_session_to_db(request)

    def get_login_redirect_url(self, request):
        return '/accounts/sso-callback/'


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Кастомный адаптер для SSO.
    - Redirect после OAuth → popup callback страницу
    - Авто-заполнение first_name/last_name из провайдера
    """

    def get_login_redirect_url(self, request):
        return '/accounts/sso-callback/'

    def get_connect_redirect_url(self, request, socialaccount):
        return '/accounts/sso-callback/'

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        data = sociallogin.account.extra_data
        updated = []
        if not user.first_name:
            # Google: given_name, Yandex: first_name
            name = data.get('given_name', '') or data.get('first_name', '')
            if name:
                user.first_name = name
                updated.append('first_name')
        if not user.last_name:
            # Google: family_name, Yandex: last_name
            name = data.get('family_name', '') or data.get('last_name', '')
            if name:
                user.last_name = name
                updated.append('last_name')
        if updated:
            user.save(update_fields=updated)
        return user

    def is_auto_signup_allowed(self, request, sociallogin):
        """Авто-создание юзера без промежуточной формы."""
        return True
