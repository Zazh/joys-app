"""Перенос моделей EmailTemplate (из pages) и EmailLog (из orders) в приложение emails.

Таблицы уже существуют — миграция только обновляет состояние Django (state_operations).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('orders', '0007_emaillog'),
        ('pages', '0013_emailtemplate'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='EmailTemplate',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('slug', models.SlugField(help_text='email_verify, password_reset, welcome, order_created, order_paid, order_shipped', max_length=100, unique=True, verbose_name='Ключ')),
                        ('subject', models.CharField(help_text='Можно использовать {плейсхолдеры}: {order_number}, {user_name} и т.д.', max_length=300, verbose_name='Тема письма')),
                        ('body', models.TextField(help_text='Плейн-текст. Плейсхолдеры: {user_name}, {verify_url}, {order_number} и т.д.', verbose_name='Текст письма')),
                        ('description', models.TextField(blank=True, help_text='Какие плейсхолдеры доступны, когда отправляется', verbose_name='Описание (для админа)')),
                    ],
                    options={
                        'verbose_name': 'Шаблон письма',
                        'verbose_name_plural': 'Шаблоны писем',
                        'db_table': 'pages_emailtemplate',
                        'ordering': ['slug'],
                    },
                ),
                migrations.CreateModel(
                    name='EmailLog',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('to_email', models.EmailField(max_length=254, verbose_name='Получатель')),
                        ('template_slug', models.CharField(max_length=100, verbose_name='Шаблон')),
                        ('subject', models.CharField(max_length=300, verbose_name='Тема')),
                        ('body', models.TextField(verbose_name='Текст')),
                        ('status', models.CharField(choices=[('sent', 'Отправлено'), ('retry', 'Ожидает повтора'), ('failed', 'Ошибка')], default='sent', max_length=10, verbose_name='Статус')),
                        ('attempts', models.PositiveSmallIntegerField(default=0, verbose_name='Попыток')),
                        ('next_retry_at', models.DateTimeField(blank=True, null=True, verbose_name='Повторить после')),
                        ('error', models.TextField(blank=True, verbose_name='Ошибка')),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создан')),
                        ('sent_at', models.DateTimeField(blank=True, null=True, verbose_name='Отправлен')),
                    ],
                    options={
                        'verbose_name': 'Лог email',
                        'verbose_name_plural': 'Логи email',
                        'db_table': 'orders_emaillog',
                        'ordering': ['-created_at'],
                        'indexes': [models.Index(fields=['status', 'next_retry_at'], name='orders_emai_status_12a3c6_idx')],
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
