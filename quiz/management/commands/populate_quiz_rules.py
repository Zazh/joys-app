from django.core.management.base import BaseCommand

from catalog.models import Product
from quiz.models import QuizRule


RULES = [
    # (priority, q1, q2, q3, q4, product_slug)
    # Аромат → конкретный вкус (5 шт)
    (10, 'aroma', 'banana', '', '', 'banana-5'),
    (10, 'aroma', 'strawberry', '', '', 'strawberry-5'),
    (10, 'aroma', 'chocolate', '', '', 'chocolate-5'),
    # Текстура + частое использование → средняя пачка (17 шт)
    (8, 'texture', '', 'daily', '', 'dotted-ribbed-17'),
    (8, 'texture', '', 'weekly', '', 'dotted-ribbed-17'),
    # Текстура (остальное) → маленькая пачка (5 шт)
    (7, 'texture', '', '', '', 'dotted-ribbed-5'),
    # Неощутимость + смазка
    (5, 'feel', '', '', 'yes', 'triple-lube-5'),
    # Неощутимость + частое использование → средняя пачка
    (4, 'feel', '', 'daily', '', 'dotted-ribbed-17'),
    (4, 'feel', '', 'weekly', '', 'dotted-ribbed-17'),
    # Неощутимость (остальное)
    (3, 'feel', '', '', '', 'triple-lube-5'),
    # Fallback — любой ответ
    (0, '', '', '', '', 'classic-5'),
]


class Command(BaseCommand):
    help = 'Создать начальные правила квиза'

    def handle(self, *args, **options):
        products = {p.slug: p for p in Product.objects.all()}
        if not products:
            self.stderr.write(self.style.ERROR('Нет товаров в БД. Сначала заполните каталог.'))
            return

        created = 0
        skipped = 0
        for priority, q1, q2, q3, q4, slug in RULES:
            product = products.get(slug)
            if not product:
                self.stderr.write(self.style.WARNING(
                    f'Товар не найден: slug="{slug}", пропускаю правило'
                ))
                skipped += 1
                continue

            _, was_created = QuizRule.objects.get_or_create(
                q1_important=q1,
                q2_aroma=q2,
                q3_frequency=q3,
                q4_lube=q4,
                defaults={
                    'product': product,
                    'priority': priority,
                    'is_active': True,
                },
            )
            if was_created:
                created += 1
                self.stdout.write(f'  + [{priority}] {q1 or "*"}/{q2 or "*"}/{q3 or "*"}/{q4 or "*"} → {product.name}')
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(f'Создано: {created}, пропущено: {skipped}'))
