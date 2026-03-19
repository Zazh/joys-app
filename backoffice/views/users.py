from django.contrib import messages
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, DetailView

from accounts.models import User
from allauth.socialaccount.models import SocialAccount
from backoffice.mixins import BackofficeAccessMixin, SeniorStaffRequiredMixin


class UserListView(BackofficeAccessMixin, ListView):
    template_name = 'backoffice/users/list.html'
    context_object_name = 'users'
    paginate_by = 25

    def get_queryset(self):
        qs = User.objects.annotate(
            orders_count=Count('orders', distinct=True),
        ).order_by('-date_joined')

        role = self.request.GET.get('role')
        if role and role in User.Role.values:
            qs = qs.filter(role=role)

        active = self.request.GET.get('active')
        if active == '1':
            qs = qs.filter(is_active=True)
        elif active == '0':
            qs = qs.filter(is_active=False)

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(email__icontains=q) |
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(phone__icontains=q)
            )

        tab = self.request.GET.get('tab', 'all')
        if tab == 'staff':
            qs = qs.exclude(role=User.Role.CUSTOMER)
        elif tab == 'customers':
            qs = qs.filter(role=User.Role.CUSTOMER)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['roles'] = User.Role.choices
        ctx['current_role'] = self.request.GET.get('role', '')
        ctx['current_active'] = self.request.GET.get('active', '')
        ctx['current_q'] = self.request.GET.get('q', '')
        ctx['current_tab'] = self.request.GET.get('tab', 'all')
        ctx['total_staff'] = User.objects.exclude(role=User.Role.CUSTOMER).count()
        ctx['total_customers'] = User.objects.filter(role=User.Role.CUSTOMER).count()
        return ctx


class UserDetailView(BackofficeAccessMixin, DetailView):
    template_name = 'backoffice/users/detail.html'
    context_object_name = 'u'

    def get_object(self):
        return get_object_or_404(
            User.objects.prefetch_related('orders'),
            pk=self.kwargs['pk'],
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        u = self.object
        ctx['recent_orders'] = u.orders.select_related('region').order_by('-created_at')[:10]
        ctx['is_editable'] = self.request.user.is_senior_staff
        ctx['is_owner'] = self.request.user.role == User.Role.OWNER
        # Источник регистрации
        social = SocialAccount.objects.filter(user=u).first()
        if social:
            providers = {'google': 'Google', 'yandex': 'Yandex'}
            ctx['auth_source'] = providers.get(social.provider, social.provider)
        else:
            ctx['auth_source'] = 'Email'
        return ctx


class UserCreateView(SeniorStaffRequiredMixin, View):
    def get(self, request):
        from django.shortcuts import render
        return render(request, 'backoffice/users/create.html', {
            'roles': [
                (User.Role.MANAGER, 'Менеджер'),
                (User.Role.SUPER_MANAGER, 'Супер-менеджер'),
            ],
        })

    def post(self, request):
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        role = request.POST.get('role', User.Role.MANAGER)
        password = request.POST.get('password', '').strip()
        generate_pwd = request.POST.get('generate_password') == 'on'
        send_invite = request.POST.get('send_invite') == 'on'

        if not email:
            messages.error(request, 'Email обязателен.')
            return redirect('backoffice:user_create')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Пользователь с таким email уже существует.')
            return redirect('backoffice:user_create')

        if role not in (User.Role.MANAGER, User.Role.SUPER_MANAGER):
            messages.error(request, 'Недопустимая роль.')
            return redirect('backoffice:user_create')

        if generate_pwd:
            password = User.objects.make_random_password(length=12)
        elif not password or len(password) < 8:
            messages.error(request, 'Пароль должен быть не менее 8 символов.')
            return redirect('backoffice:user_create')

        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role=role,
        )

        msg = f'Сотрудник {user.email} создан.'
        if send_invite:
            from emails.service import send_staff_invite
            send_staff_invite(user, password)
            msg += ' Доступ отправлен на почту.'

        messages.success(request, msg)
        return redirect('backoffice:user_detail', pk=user.pk)


class UserEditView(SeniorStaffRequiredMixin, View):
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)

        # Only owner can edit other owners
        if user.role == User.Role.OWNER and request.user.role != User.Role.OWNER:
            messages.error(request, 'Недостаточно прав для редактирования владельца.')
            return redirect('backoffice:user_detail', pk=pk)

        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name = request.POST.get('last_name', '').strip()
        user.phone = request.POST.get('phone', '').strip()

        new_role = request.POST.get('role')
        if new_role and new_role in User.Role.values:
            if new_role != User.Role.OWNER or request.user.role == User.Role.OWNER:
                user.role = new_role

        password = request.POST.get('password', '').strip()
        if password and request.user.role == User.Role.OWNER:
            if len(password) < 8:
                messages.error(request, 'Пароль должен быть не менее 8 символов.')
                return redirect('backoffice:user_detail', pk=pk)
            user.set_password(password)

        user.save()
        messages.success(request, 'Данные обновлены.')
        return redirect('backoffice:user_detail', pk=pk)


class UserToggleActiveView(SeniorStaffRequiredMixin, View):
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if user == request.user:
            messages.error(request, 'Нельзя деактивировать свой аккаунт.')
            return redirect('backoffice:user_detail', pk=pk)
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        status = 'активирован' if user.is_active else 'деактивирован'
        messages.success(request, f'Пользователь {status}.')
        return redirect('backoffice:user_detail', pk=pk)
