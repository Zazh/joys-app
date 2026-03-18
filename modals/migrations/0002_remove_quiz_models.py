from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('modals', '0001_initial'),
        ('quiz', '0001_initial'),
    ]

    operations = [
        # Удаляем из state (таблицы уже переименованы в quiz/0001)
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='QuizRule'),
                migrations.DeleteModel(name='QuizBackground'),
            ],
            database_operations=[],
        ),
    ]
