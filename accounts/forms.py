from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()


class RegisterForm(forms.Form):
    email = forms.EmailField(max_length=254)
    password1 = forms.CharField()
    password2 = forms.CharField()

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError('Пользователь с таким email уже существует.')
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise ValidationError({'password2': 'Пароли не совпадают.'})
        if p1:
            try:
                validate_password(p1)
            except ValidationError as e:
                raise ValidationError({'password1': list(e.messages)})
        return cleaned

    def save(self):
        return User.objects.create_user(
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password1'],
        )


class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField()


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'phone')
