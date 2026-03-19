"""Удаление EmailTemplate из pages state — модель перенесена в emails."""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0014_servicepage'),
        ('emails', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='EmailTemplate'),
            ],
            database_operations=[],
        ),
    ]
