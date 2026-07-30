"""Формы бэкофиса.

Остальные разделы бэкофиса разбирают `request.POST` руками, но контакты —
единственная страница, где значения уходят в ссылки (`tel:`, `wa.me`, `t.me`)
и в разметку для поисковиков, а часть полей нужна на трёх языках. Здесь
`ModelForm` окупается: обязательность, `verbose_name` и `help_text` берутся
с модели, а не переписываются в разметке (docs/contact_settings.md §6).
"""

from django import forms

from pages.models import ContactSettings

# Классы Tailwind у полей одни и те же — навешиваем в __init__, а не в widgets
INPUT_CLASS = ('w-full px-3 py-2 border border-stone-300 rounded-lg text-sm '
               'focus:outline-none focus:ring-2 focus:ring-stone-400')

LANGUAGES = (('ru', 'RU'), ('kk', 'KK'), ('en', 'EN'))

# Поля с языковыми колонками — список тот же, что в pages/translation.py
TRANSLATED_FIELDS = ('legal_name', 'bin_label', 'address_locality', 'address_street', 'work_hours')


def _lang_names(base):
    return [f'{base}_{code}' for code, _ in LANGUAGES]


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


class ContactSettingsForm(forms.ModelForm):
    """Контакты компании: каналы, реквизиты, адрес офиса.

    Языковые колонки перечислены вместо базовых полей: базовое поле у
    modeltranslation — прокси на активный язык, и через него заполнить kk и en
    невозможно. Порядок полей в `fields` задаёт порядок в разметке.
    """

    class Meta:
        model = ContactSettings
        fields = [
            'phone', 'whatsapp_phone', 'telegram_username', 'email',
            'instagram_url', 'tiktok_url', 'youtube_url', 'marketplace_url',
            'bin',
            *_lang_names('legal_name'),
            *_lang_names('bin_label'),
            *_lang_names('address_locality'),
            *_lang_names('address_street'),
            *_lang_names('work_hours'),
            'office_lat', 'office_lng',
        ]
        field_classes = {
            'office_lat': CoordinateField,
            'office_lng': CoordinateField,
        }
        widgets = {
            'office_lat': forms.NumberInput(attrs={'step': '0.000001', 'x-model': 'lat'}),
            'office_lng': forms.NumberInput(attrs={'step': '0.000001', 'x-model': 'lng'}),
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
            for name in _lang_names(base):
                self.fields[name].required = not base_field.blank
                # modeltranslation дописывает к подписи язык («Город [kk]»), но язык
                # уже выбран табом — в каждой строке это лишний шум
                self.fields[name].label = base_field.verbose_name

        # Колонка nullable ради load(), но обнулить координаты из формы нельзя:
        # без них нет ни карты, ни маршрутов (docs/contact_settings.md §3.1)
        self.fields['office_lat'].required = True
        self.fields['office_lng'].required = True

    def clean_phone(self):
        return self._canonical_phone('phone')

    def clean_whatsapp_phone(self):
        return self._canonical_phone('whatsapp_phone')

    def clean_telegram_username(self):
        # Регексп не пишем: модель уже чистит имя на чтении этой же функцией (§6)
        return ContactSettings.normalize_telegram_username(self.cleaned_data['telegram_username'])

    def clean(self):
        cleaned = super().clean()
        # Часы работы необязательны, но «наполовину заполненные» хуже пустых:
        # пустой перевод у modeltranslation отдаёт фолбэк, то есть русский текст
        filled = [name for name in _lang_names('work_hours') if cleaned.get(name)]
        if filled and len(filled) < len(LANGUAGES):
            for name in _lang_names('work_hours'):
                if not cleaned.get(name):
                    self.add_error(name, 'Заполните часы работы на всех трёх языках '
                                         'или очистите все три — иначе здесь покажется русский текст.')
        return cleaned

    def _canonical_phone(self, name):
        """Номер в колонку — сразу в E.164: заказчик видит, что сохранилось.

        Модель и так чистит номер на чтении (`to_e164`), так что ссылка цела при
        любом содержимом колонки. Здесь — наглядность и опечатки: `8 776…`
        приводим к `+7 776…` (в модели такого нет намеренно — это допущение про
        страну, а форма про Казахстан знает).
        """
        e164 = ContactSettings.to_e164(self.cleaned_data[name])
        digits = e164.lstrip('+')
        if len(digits) == 11 and digits[0] == '8':
            digits = '7' + digits[1:]
            e164 = f'+{digits}'
        if digits and not 10 <= len(digits) <= 15:
            raise forms.ValidationError('Похоже на опечатку: в номере от 10 до 15 цифр.')
        return e164

    # ─── Группировка для шаблона ───

    def channel_fields(self):
        return [self[name] for name in ('phone', 'whatsapp_phone', 'telegram_username', 'email')]

    def social_fields(self):
        return [self[name] for name in
                ('instagram_url', 'tiktok_url', 'youtube_url', 'marketplace_url')]

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
