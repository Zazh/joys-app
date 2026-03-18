import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('catalog', '0016_image_alt_text_i18n'),
        ('modals', '0001_initial'),
    ]

    operations = [
        # QuizRule — переносим из modals: state-only CreateModel + DB rename
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='QuizRule',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('q1_important', models.CharField(blank=True, choices=[('texture', 'Текстура'), ('aroma', 'Аромат'), ('feel', 'Неощутимость')], max_length=20, verbose_name='Q1: Что важнее?')),
                        ('q2_aroma', models.CharField(blank=True, choices=[('banana', 'Банан'), ('strawberry', 'Клубника'), ('chocolate', 'Шоколад'), ('none', 'Без аромата')], max_length=20, verbose_name='Q2: Аромат')),
                        ('q3_frequency', models.CharField(blank=True, choices=[('daily', 'Каждый день'), ('weekly', 'Несколько раз в неделю'), ('monthly', 'Несколько раз в месяц'), ('yearly', 'Редко')], max_length=20, verbose_name='Q3: Частота')),
                        ('q4_lube', models.CharField(blank=True, choices=[('yes', 'Да'), ('no', 'Нет')], max_length=10, verbose_name='Q4: Доп. смазка?')),
                        ('priority', models.IntegerField(default=0, help_text='Чем выше — тем приоритетнее. При совпадении нескольких правил побеждает с высшим.', verbose_name='Приоритет')),
                        ('is_active', models.BooleanField(default=True, verbose_name='Активно')),
                        ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='quiz_rules', to='catalog.product', verbose_name='Рекомендуемый товар')),
                    ],
                    options={
                        'verbose_name': 'Правило квиза',
                        'verbose_name_plural': 'Правила квиза',
                        'ordering': ['-priority'],
                    },
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql='ALTER TABLE modals_quizrule RENAME TO quiz_quizrule;',
                    reverse_sql='ALTER TABLE quiz_quizrule RENAME TO modals_quizrule;',
                ),
            ],
        ),
        # QuizBackground — переносим из modals
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='QuizBackground',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('key', models.SlugField(help_text='banana, strawberry, chocolate, dotted-ribbed, triple-lube', unique=True, verbose_name='Ключ')),
                        ('image', models.ImageField(upload_to='quiz/backgrounds/', verbose_name='Изображение')),
                        ('is_dark_theme', models.BooleanField(default=False, help_text='Белый текст на тёмном фоне', verbose_name='Тёмная тема')),
                        ('is_active', models.BooleanField(default=True, verbose_name='Активно')),
                    ],
                    options={
                        'verbose_name': 'Фон квиза',
                        'verbose_name_plural': 'Фоны квиза',
                    },
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql='ALTER TABLE modals_quizbackground RENAME TO quiz_quizbackground;',
                    reverse_sql='ALTER TABLE quiz_quizbackground RENAME TO modals_quizbackground;',
                ),
            ],
        ),
    ]
