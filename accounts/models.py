from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('Email обязателен')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = 'customer', 'Покупатель'
        MANAGER = 'manager', 'Менеджер'
        SUPER_MANAGER = 'super_manager', 'Супер-менеджер'
        OWNER = 'owner', 'Владелец'

    username = None
    email = models.EmailField('Email', unique=True)
    phone = models.CharField('Телефон', max_length=20, blank=True)
    role = models.CharField(
        'Роль', max_length=20,
        choices=Role.choices, default=Role.CUSTOMER,
        db_index=True,
    )
    last_ip = models.GenericIPAddressField('Последний IP', null=True, blank=True)
    last_user_agent = models.CharField('Браузер', max_length=300, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        indexes = [
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return self.email

    def get_full_name(self):
        name = f'{self.first_name} {self.last_name}'.strip()
        return name

    @property
    def is_staff_role(self):
        return self.role in (self.Role.MANAGER, self.Role.SUPER_MANAGER, self.Role.OWNER)

    @property
    def is_senior_staff(self):
        return self.role in (self.Role.SUPER_MANAGER, self.Role.OWNER)
