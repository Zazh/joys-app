from django import forms
from django.utils.translation import gettext_lazy as _


class CheckoutForm(forms.Form):
    """Форма оформления заказа — данные доставки."""

    country = forms.CharField(max_length=10, label=_('Страна'))
    city = forms.CharField(max_length=100, label=_('Город'))
    street = forms.CharField(max_length=200, label=_('Улица'))
    house = forms.CharField(max_length=50, label=_('Дом'))
    apt = forms.CharField(max_length=50, required=False, label=_('Квартира'))
    first_name = forms.CharField(max_length=100, label=_('Имя'))
    last_name = forms.CharField(max_length=100, label=_('Фамилия'))
    phone = forms.CharField(max_length=20, label=_('Телефон'))
    email = forms.EmailField(required=False, label=_('Email'))

    def get_address(self):
        """Собрать улицу, дом, квартиру в одну строку."""
        parts = [
            self.cleaned_data.get('street', ''),
            self.cleaned_data.get('house', ''),
            self.cleaned_data.get('apt', ''),
        ]
        return ', '.join(p for p in parts if p)
