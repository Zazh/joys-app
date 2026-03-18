from django.core.management.base import BaseCommand

from regions.models import Region


REGIONS = [
    {
        'code': 'kz',
        'name': '\u041a\u0430\u0437\u0430\u0445\u0441\u0442\u0430\u043d',
        'currency_code': 'KZT',
        'currency_symbol': '\u20b8',
        'default_language': 'ru',
        'phone_code': '+7',
        'flag_emoji': '\U0001f1f0\U0001f1ff',
        'is_default': True,
        'is_active': True,
        'order': 1,
    },
    {
        'code': 'ru',
        'name': '\u0420\u043e\u0441\u0441\u0438\u044f',
        'currency_code': 'RUB',
        'currency_symbol': '\u20bd',
        'default_language': 'ru',
        'phone_code': '+7',
        'flag_emoji': '\U0001f1f7\U0001f1fa',
        'is_default': False,
        'is_active': True,
        'order': 2,
    },
]


class Command(BaseCommand):
    help = '\u0417\u0430\u0433\u0440\u0443\u0436\u0430\u0435\u0442 \u043d\u0430\u0447\u0430\u043b\u044c\u043d\u044b\u0435 \u0440\u0435\u0433\u0438\u043e\u043d\u044b (KZ, RU)'

    def handle(self, *args, **options):
        for data in REGIONS:
            obj, created = Region.objects.update_or_create(
                code=data['code'],
                defaults=data,
            )
            status = '\u0441\u043e\u0437\u0434\u0430\u043d' if created else '\u043e\u0431\u043d\u043e\u0432\u043b\u0451\u043d'
            self.stdout.write(f'  {obj.flag_emoji} {obj.name} \u2014 {status}')

        self.stdout.write(self.style.SUCCESS(
            f'\u0417\u0430\u0433\u0440\u0443\u0436\u0435\u043d\u043e {len(REGIONS)} \u0440\u0435\u0433\u0438\u043e\u043d\u043e\u0432'
        ))
