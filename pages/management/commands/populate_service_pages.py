from django.core.management.base import BaseCommand
from pages.models import ServicePage


PAGES = [
    {
        'slug': 'check_email',
        'title_ru': 'ПРОВЕРЬТЕ ПОЧТУ',
        'title_kk': 'ПОШТАҢЫЗДЫ ТЕКСЕРІҢІЗ',
        'title_en': 'CHECK YOUR EMAIL',
        'description_ru': 'Мы отправили письмо с ссылкой для подтверждения на',
        'description_kk': 'Біз растау сілтемесі бар хат жібердік',
        'description_en': 'We sent a confirmation link to',
        'button_text_ru': 'НА ГЛАВНУЮ',
        'button_text_kk': 'БАСТЫ БЕТКЕ',
        'button_text_en': 'GO TO HOME',
        'button_url': '/',
    },
    {
        'slug': 'email_verified',
        'title_ru': 'EMAIL ПОДТВЕРЖДЁН',
        'title_kk': 'EMAIL РАСТАЛДЫ',
        'title_en': 'EMAIL VERIFIED',
        'description_ru': 'Ваш email успешно подтверждён. Теперь вы можете пользоваться всеми функциями сайта.',
        'description_kk': 'Сіздің email сәтті расталды. Енді сайттың барлық мүмкіндіктерін пайдалана аласыз.',
        'description_en': 'Your email has been verified. You can now use all site features.',
        'button_text_ru': 'ПЕРЕЙТИ К ПОКУПКАМ',
        'button_text_kk': 'САТЫП АЛУҒА ӨТУ',
        'button_text_en': 'START SHOPPING',
        'button_url': '/',
    },
    {
        'slug': 'email_error',
        'title_ru': 'ОШИБКА',
        'title_kk': 'ҚАТЕ',
        'title_en': 'ERROR',
        'description_ru': 'Ссылка истекла или недействительна.',
        'description_kk': 'Сілтеме мерзімі өтіп кеткен немесе жарамсыз.',
        'description_en': 'The link has expired or is invalid.',
        'button_text_ru': 'НА ГЛАВНУЮ',
        'button_text_kk': 'БАСТЫ БЕТКЕ',
        'button_text_en': 'GO TO HOME',
        'button_url': '/',
    },
]


class Command(BaseCommand):
    help = 'Создать/обновить служебные страницы'

    def handle(self, *args, **options):
        for data in PAGES:
            slug = data.pop('slug')
            obj, created = ServicePage.objects.update_or_create(slug=slug, defaults=data)
            action = 'создана' if created else 'обновлена'
            self.stdout.write(f'  {slug} — {action}')
        self.stdout.write(self.style.SUCCESS('Готово'))
