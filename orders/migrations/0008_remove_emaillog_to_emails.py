"""Удаление EmailLog из orders state — модель перенесена в emails."""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0007_emaillog'),
        ('emails', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='EmailLog'),
            ],
            database_operations=[],
        ),
    ]
