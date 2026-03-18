from django import forms


class CheckoutForm(forms.Form):
    """Форма оформления заказа — данные доставки."""

    country = forms.CharField(max_length=10, label='Страна')
    city = forms.CharField(max_length=100, label='Город')
    street = forms.CharField(max_length=200, label='Улица')
    house = forms.CharField(max_length=50, label='Дом')
    apt = forms.CharField(max_length=50, required=False, label='Квартира')
    first_name = forms.CharField(max_length=100, label='Имя')
    last_name = forms.CharField(max_length=100, label='Фамилия')
    phone = forms.CharField(max_length=20, label='Телефон')
    email = forms.EmailField(required=False, label='Email')

    def get_address(self):
        """Собрать улицу, дом, квартиру в одну строку."""
        parts = [
            self.cleaned_data.get('street', ''),
            self.cleaned_data.get('house', ''),
            self.cleaned_data.get('apt', ''),
        ]
        return ', '.join(p for p in parts if p)
