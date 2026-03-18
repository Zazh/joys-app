import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from urllib.request import urlopen
from urllib.error import URLError

from django.core.management.base import BaseCommand
from django.utils import timezone

from regions.models import ExchangeRate

NATSBANK_URL = 'https://nationalbank.kz/rss/rates_all.xml'


class Command(BaseCommand):
    help = 'Обновить курсы валют с Нацбанка РК (nationalbank.kz)'

    def handle(self, *args, **options):
        self.stdout.write('Загрузка курсов с nationalbank.kz...')

        try:
            with urlopen(NATSBANK_URL, timeout=15) as resp:
                xml_data = resp.read()
        except URLError as e:
            self.stderr.write(self.style.ERROR(f'Ошибка загрузки: {e}'))
            return

        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError as e:
            self.stderr.write(self.style.ERROR(f'Ошибка парсинга XML: {e}'))
            return

        now = timezone.now()
        updated = 0

        for item in root.iter('item'):
            title = item.findtext('title', '').strip().upper()
            description = item.findtext('description', '').strip()
            quant_str = item.findtext('quant', '1').strip()

            if not title or not description:
                continue

            try:
                rate = Decimal(description)
                quant = int(quant_str)
            except (InvalidOperation, ValueError):
                continue

            ExchangeRate.objects.update_or_create(
                currency_code=title,
                defaults={
                    'rate': rate,
                    'quant': quant,
                    'fetched_at': now,
                },
            )
            updated += 1

        self.stdout.write(self.style.SUCCESS(f'Обновлено {updated} курсов.'))

        # Показать ключевые курсы
        for code in ('RUB', 'USD', 'EUR'):
            try:
                r = ExchangeRate.objects.get(currency_code=code)
                self.stdout.write(f'  {r.quant} {r.currency_code} = {r.rate} KZT')
            except ExchangeRate.DoesNotExist:
                pass
