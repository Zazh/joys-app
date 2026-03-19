from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.views import View


class LoginView(View):
    def get(self, request):
        if request.user.is_authenticated and hasattr(request.user, 'is_staff_role') and request.user.is_staff_role:
            return redirect('backoffice:dashboard')
        return render(request, 'backoffice/auth/login.html')

    def post(self, request):
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        error = None

        user = authenticate(request, email=email, password=password)
        if user is None:
            error = 'Неверный email или пароль.'
        elif not user.is_staff_role:
            error = 'У вас нет доступа к бэкофису.'
        else:
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('backoffice:dashboard')

        return render(request, 'backoffice/auth/login.html', {
            'error': error,
            'email': email,
        })


class LogoutView(View):
    def post(self, request):
        logout(request)
        return redirect('backoffice:login')
