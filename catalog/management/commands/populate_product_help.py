"""Справка на странице товара: страницы CMS + привязки к категориям.

Идемпотентная (канон populate_*): существующие страницы не перезаписывает,
заполненные поля категорий не трогает — тексты и привязки дальше живут
в бэкофисе. На проде запускается один раз при выкате фичи.
"""

from django.core.management.base import BaseCommand

from catalog.models import Category
from modals.models import InteractiveModal
from pages.models import Page

PAGES = [
    {
        'slug': 'kak-vybrat-lubrikant',
        'title': 'Как выбрать лубрикант?',
        'body': (
            '<h3>Основа</h3>'
            '<p>Лубриканты DR.JOYS сделаны на водной основе — она универсальна: '
            'не разрушает латекс, совместима с презервативами и игрушками, '
            'легко смывается водой и не оставляет следов.</p>'
            '<h3>Объём</h3>'
            '<p>Для знакомства с продуктом хватит небольшого флакона. Если '
            'пользуетесь смазкой регулярно — выгоднее взять больший объём.</p>'
            '<h3>Аромат и ощущения</h3>'
            '<p>Классическая смазка нейтральна и не отвлекает. Ароматизированные '
            'варианты добавляют разнообразия — выбирайте вкус под настроение.</p>'
        ),
    },
    {
        'slug': 'instrukciya-po-primeneniyu',
        'title': 'Инструкция по применению',
        'body': (
            '<h3>Презервативы</h3>'
            '<ul>'
            '<li>Проверьте срок годности и целостность упаковки.</li>'
            '<li>Вскрывайте упаковку пальцами по насечке — не ножницами и не зубами.</li>'
            '<li>Надевайте презерватив до начала контакта, придерживая накопитель.</li>'
            '<li>Презерватив одноразовый: для каждого контакта — новый.</li>'
            '</ul>'
            '<h3>Лубриканты</h3>'
            '<ul>'
            '<li>Нанесите небольшое количество и распределите — при необходимости добавьте.</li>'
            '<li>Смазка на водной основе совместима с латексными презервативами.</li>'
            '<li>После использования закройте флакон; храните вдали от прямого солнца.</li>'
            '</ul>'
        ),
    },
    {
        'slug': 'protivopokazaniya',
        'title': 'Противопоказания',
        'body': (
            '<ul>'
            '<li>Индивидуальная непереносимость латекса или компонентов состава.</li>'
            '<li>При появлении раздражения, зуда или дискомфорта прекратите '
            'использование и обратитесь к врачу.</li>'
            '<li>Не используйте изделия с повреждённой упаковкой или истёкшим '
            'сроком годности.</li>'
            '<li>При хронических заболеваниях кожи и слизистых предварительно '
            'проконсультируйтесь со специалистом.</li>'
            '</ul>'
        ),
    },
]


class Command(BaseCommand):
    help = 'Создаёт страницы справки товара и привязывает их к категориям'

    def handle(self, *args, **options):
        pages = {}
        for data in PAGES:
            page, created = Page.objects.get_or_create(
                slug=data['slug'],
                defaults={'title': data['title'], 'body': data['body']},
            )
            pages[data['slug']] = page
            self.stdout.write(f'{"создана" if created else "уже есть"}: /{page.slug}/')

        size_modal = InteractiveModal.objects.filter(slug='tattoo', is_active=True).first()

        for category in Category.objects.all():
            changed = []
            if category.slug == 'prezervativy' and size_modal and not category.size_guide_modal_id:
                category.size_guide_modal = size_modal
                changed.append('модалка размера')
            if category.slug == 'smazki' and not category.size_guide_page_id:
                category.size_guide_page = pages['kak-vybrat-lubrikant']
                changed.append('страница размера')
            if not category.usage_page_id:
                category.usage_page = pages['instrukciya-po-primeneniyu']
                changed.append('инструкция')
            if not category.contraindications_page_id:
                category.contraindications_page = pages['protivopokazaniya']
                changed.append('противопоказания')
            if changed:
                category.save()
                self.stdout.write(f'{category.name_ru}: {", ".join(changed)}')
