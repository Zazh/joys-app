from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.views import View

from backoffice.ratelimit import is_rate_limited, record_failed_attempt, clear_attempts


class LoginView(View):
    def get(self, request):
        if request.user.is_authenticated and hasattr(request.user, 'is_staff_role') and request.user.is_staff_role:
            return redirect('backoffice:dashboard')
        return render(request, 'backoffice/auth/login.html')

    def post(self, request):
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        error = None

        limited, remaining = is_rate_limited(request, scope='backoffice', max_attempts=5, window=300)
        if limited:
            minutes = remaining // 60 + 1
            error = f'Слишком много попыток. Попробуйте через {minutes} мин.'
            return render(request, 'backoffice/auth/login.html', {
                'error': error,
                'email': email,
            })

        user = authenticate(request, email=email, password=password)
        if user is None:
            record_failed_attempt(request, scope='backoffice', max_attempts=5, window=300)
            error = 'Неверный email или пароль.'
        elif not user.is_staff_role:
            record_failed_attempt(request, scope='backoffice', max_attempts=5, window=300)
            error = 'У вас нет доступа к бэкофису.'
        else:
            clear_attempts(request, scope='backoffice')
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
