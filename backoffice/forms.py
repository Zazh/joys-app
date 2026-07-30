"""Формы бэкофиса.

Остальные разделы бэкофиса разбирают `request.POST` руками, но контакты —
единственная страница, где значения уходят в ссылки (`tel:`, `wa.me`, `t.me`)
и в разметку для поисковиков, а часть полей нужна на трёх языках. Здесь
`ModelForm` окупается: обязательность, `verbose_name` и `help_text` берутся
с модели, а не переписываются в разметке (docs/contact_settings.md §6).
"""

import re

from django import forms
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from modeltranslation.utils import get_translation_fields

from pages.models import ContactSettings

# Классы Tailwind у полей одни и те же — навешиваем в __init__, а не в widgets
INPUT_CLASS = ('w-full px-3 py-2 border border-stone-300 rounded-lg text-sm '
               'focus:outline-none focus:ring-2 focus:ring-stone-400')

# Табы редактора — языки проекта в их порядке: четвёртый язык появится сам
LANGUAGES = tuple((code, code.upper()) for code, _ in settings.LANGUAGES)

# Поля с языковыми колонками. Список задаёт и порядок в разметке, поэтому он свой,
# а не из pages/translation.py; что состав не разъехался, проверяет тест
TRANSLATED_FIELDS = ('legal_name', 'bin_label', 'address_locality', 'address_street', 'work_hours')

# Группировка для разметки: каналы связи и ссылки на профили
CHANNEL_FIELDS = ('phone', 'whatsapp_phone', 'telegram_username', 'email')
SOCIAL_FIELDS = ('instagram_url', 'tiktok_url', 'youtube_url', 'marketplace_url')

_BIN = re.compile(r'^[0-9]{12}$')


class CoordinateField(forms.DecimalField):
    """Широта/долгота, терпимая к запятой.

    Координаты копируют из 2ГИС, а тот на русском языке показывает их через
    запятую. `localize=True` эту проблему не решает, а создаёт: значение уехало
    бы с запятой в `<input type="number">`, который такого не понимает.
    """

    def to_python(self, value):
        if isinstance(value, str):
            value = value.replace(',', '.')
        return super().to_python(value)


class HttpsURLField(forms.URLField):
    """Ссылка без схемы — `https://`, а не `http://`.

    Django 5 схемой по умолчанию подставляет `http` (это меняется только в
    Django 6), так что «instagram.com/drjoysoriginal» уехало бы в `sameAs`
    и в `href` небезопасной ссылкой.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault('assume_scheme', 'https')
        super().__init__(**kwargs)


class ContactSettingsForm(forms.ModelForm):
    """Контакты компании: каналы, реквизиты, адрес офиса.

    Языковые колонки перечислены вместо базовых полей: базовое поле у
    modeltranslation — прокси на активный язык, и через него заполнить kk и en
    невозможно. Порядок полей в `fields` задаёт порядок в разметке.
    """

    # Обязательные переводы лежат на скрытых табах, а невидимое поле браузер
    # отчитать не может — он молча блокирует отправку, и «Сохранить» выглядит
    # нерабочей кнопкой. Снимаем только атрибут `required`: проверки type=email,
    # type=url и границы координат браузеру оставляем, ошибки по существу всё
    # равно приходят с сервера, а таб с ошибкой открывается сам (error_tab).
    # Звёздочка у подписи рисуется из field.field.required и не страдает.
    use_required_attribute = False

    class Meta:
        model = ContactSettings
        fields = [
            *CHANNEL_FIELDS,
            *SOCIAL_FIELDS,
            'bin',
            *get_translation_fields('legal_name'),
            *get_translation_fields('bin_label'),
            *get_translation_fields('address_locality'),
            *get_translation_fields('address_street'),
            *get_translation_fields('work_hours'),
            'office_lat', 'office_lng',
        ]
        field_classes = {
            **{name: HttpsURLField for name in SOCIAL_FIELDS},
            'office_lat': CoordinateField,
            'office_lng': CoordinateField,
        }
        widgets = {
            # step Django выводит из decimal_places, границы Земли — наши
            'office_lat': forms.NumberInput(attrs={'min': -90, 'max': 90, 'x-model': 'lat'}),
            'office_lng': forms.NumberInput(attrs={'min': -180, 'max': 180, 'x-model': 'lng'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', INPUT_CLASS)

        # Языковые колонки modeltranslation всегда blank=True, поэтому обязательность
        # берём с базового поля: иначе заказчик сохранит только русский, а на /kk/ и
        # /en/ проступит он же через фолбэк (docs/contact_settings.md §4).
        for base in TRANSLATED_FIELDS:
            base_field = ContactSettings._meta.get_field(base)
            for name in get_translation_fields(base):
                self.fields[name].required = not base_field.blank
                # modeltranslation дописывает к подписи язык («Город [kk]»), но язык
                # уже выбран табом — в каждой строке это лишний шум
                self.fields[name].label = base_field.verbose_name

        # Колонка nullable ради load(), но обнулить координаты из формы нельзя: без
        # них нет ни карты, ни маршрутов (§3.1). Границы — чтобы опечатка «851»
        # вместо «51» не уехала на сайт молча: метка ушла бы с карты, маршруты в никуда
        for name, limit in (('office_lat', 90), ('office_lng', 180)):
            self.fields[name].required = True
            self.fields[name].validators += [MinValueValidator(-limit), MaxValueValidator(limit)]

    def clean_phone(self):
        return self._canonical_phone('phone')

    def clean_whatsapp_phone(self):
        return self._canonical_phone('whatsapp_phone')

    def clean_bin(self):
        # БИН печатается в футере и уходит в taxID разметки — там не должно быть «abc»
        value = self.cleaned_data['bin']
        if not _BIN.match(value):
            raise forms.ValidationError('БИН — это ровно 12 цифр, без пробелов.')
        return value

    def clean_telegram_username(self):
        # Ни нормализацию, ни проверку имени форма не пишет сама: и то и другое —
        # знание модели, форма добавляет только человеческий текст ошибки (§6)
        handle = ContactSettings.normalize_telegram_username(self.cleaned_data['telegram_username'])
        if handle and not ContactSettings.is_telegram_username(handle):
            raise forms.ValidationError(
                'Похоже, это не имя пользователя: в нём только латиница, цифры и '
                'подчёркивание, 5–32 символа. Иначе ссылка t.me соберётся битой.')
        return handle

    def clean(self):
        cleaned = super().clean()
        # Часы работы необязательны, но «наполовину заполненные» хуже пустых:
        # пустой перевод у modeltranslation отдаёт фолбэк, то есть русский текст
        work_hours = get_translation_fields('work_hours')
        filled = [name for name in work_hours if cleaned.get(name)]
        if filled and len(filled) < len(work_hours):
            for name in work_hours:
                if not cleaned.get(name):
                    self.add_error(name, 'Заполните часы работы на всех трёх языках '
                                         'или очистите все три — иначе здесь покажется русский текст.')
        return cleaned

    def _canonical_phone(self, name):
        """Номер в колонку — сразу в E.164: заказчик видит, что сохранилось.

        Ссылка цела и без этого (`to_e164` чистит номер на чтении), здесь —
        наглядность и опечатки: `8 776…` приводим к `+7 776…` (в модели такого
        нет намеренно — это допущение про страну, а форма про Казахстан знает).
        """
        value = self.cleaned_data[name]
        digits = ContactSettings.to_e164(value).lstrip('+')
        if not digits:
            if value:
                raise forms.ValidationError('Не похоже на номер: здесь нет ни одной цифры.')
            return ''
        if len(digits) == 11 and digits[0] == '8':
            digits = '7' + digits[1:]
        if not 10 <= len(digits) <= 15:
            raise forms.ValidationError('Похоже на опечатку: в номере от 10 до 15 цифр.')
        return f'+{digits}'

    # ─── Группировка для шаблона ───

    def channel_fields(self):
        return [self[name] for name in CHANNEL_FIELDS]

    def social_fields(self):
        return [self[name] for name in SOCIAL_FIELDS]

    def translated_groups(self):
        """Языковые табы: по группе полей на каждый язык.

        `has_errors` нужен разметке, чтобы отметить таб точкой и открыть его
        первым: без этого ошибка в kk выглядела бы как «кнопка не работает».
        """
        groups = []
        for code, label in LANGUAGES:
            fields = [self[f'{base}_{code}'] for base in TRANSLATED_FIELDS]
            groups.append({
                'code': code,
                'label': label,
                'fields': fields,
                'has_errors': any(field.errors for field in fields),
            })
        return groups

    def error_tab(self):
        """Язык, который открыть при ошибке валидации."""
        for group in self.translated_groups():
            if group['has_errors']:
                return group['code']
        return LANGUAGES[0][0]
