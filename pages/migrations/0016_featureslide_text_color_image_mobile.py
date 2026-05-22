from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0015_remove_emailtemplate_to_emails'),
    ]

    operations = [
        migrations.AddField(
            model_name='featureslide',
            name='text_color',
            field=models.CharField(
                choices=[
                    ('black', 'Чёрный (на светлом фоне)'),
                    ('white', 'Белый (на тёмном фоне)'),
                ],
                default='black',
                help_text='Цвет заголовка и текста. На светлом фоне — чёрный, на тёмном — белый.',
                max_length=10,
                verbose_name='Цвет текста',
            ),
        ),
        migrations.AddField(
            model_name='featureslide',
            name='image_mobile',
            field=models.ImageField(
                blank=True,
                help_text='Опционально. Если не указана — используется десктопная.',
                upload_to='features/mobile/',
                verbose_name='Картинка (мобильная)',
            ),
        ),
        migrations.AlterField(
            model_name='featureslide',
            name='image',
            field=models.ImageField(
                blank=True,
                help_text='Фоновое изображение слайда. Используется на десктопе и как фолбэк для мобильных.',
                upload_to='features/',
                verbose_name='Картинка (десктоп)',
            ),
        ),
        migrations.AlterField(
            model_name='featureslide',
            name='text',
            field=models.TextField(
                help_text='Поддерживает HTML-теги. Для ссылок используйте &lt;a href="..."&gt;...&lt;/a&gt;',
                verbose_name='Текст',
            ),
        ),
    ]
