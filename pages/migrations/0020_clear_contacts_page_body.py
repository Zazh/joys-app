from django.db import migrations

# Slug страницы контактов. Дублировать backoffice.views.contacts не хочется:
# миграции обязаны работать в отрыве от текущего кода приложений.
CONTACTS_SLUG = 'contacts'


def clear_body(apps, schema_editor):
    """Убираем мёртвый контент страницы контактов.

    С редизайна (docs/contacts_page_redesign.md) `/contacts/` рисуется своим
    шаблоном, и `body` он не читает — там осталась старая Quill-таблица с
    реквизитами. На деве её почистили руками в Сессии 5R, на проде она всё ещё
    лежит в базе, а с закрытием общего редактора страницы (её контент теперь
    правится в разделе «Контакты») почистить её оттуда стало нечем.

    Терять нечего: полные реквизиты живут в CMS-странице «Условия покупки».
    """
    Page = apps.get_model('pages', 'Page')
    Page.objects.filter(slug=CONTACTS_SLUG).update(
        body='', body_ru='', body_kk='', body_en='',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0019_contactsettings_initial_data'),
    ]

    # Необратима намеренно: восстанавливать вёрстку, которую нигде не показывают,
    # незачем — при откате поле просто остаётся пустым
    operations = [
        migrations.RunPython(clear_body, migrations.RunPython.noop),
    ]
