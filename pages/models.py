import re
from urllib.parse import unquote, urlsplit

from django.db import models
from django.urls import reverse, NoReverseMatch

# Префикс ссылки на телеграм — срезаем, чтобы из вставленной ссылки осталось имя
_TELEGRAM_URL_PREFIX = re.compile(r'^(?:https?://)?(?:www\.)?t(?:elegram)?\.me/', re.I)
# Что телеграм разрешает в имени пользователя: латиница, цифры, подчёркивание, 5–32 знака
_TELEGRAM_USERNAME = re.compile(r'^[A-Za-z0-9_]{5,32}$')

# Координаты в ссылке 2ГИС (после unquote): пара «долгота,широта» в конце пути
# карточки (…/firm/…/76.898728,43.204689) или в параметре m= — центре карты
_GIS_PATH_POINT = re.compile(r'/(\d{1,3}\.\d+),(\d{1,3}\.\d+)/?$')
_GIS_MAP_CENTER = re.compile(r'(?:^|&)m=(\d{1,3}\.\d+),(\d{1,3}\.\d+)(?:/(\d+(?:\.\d+)?))?')


class PageCategory(models.Model):
    """Категория страниц (Правовая информация, Помощь и т.д.)."""
    name = models.CharField('Название', max_length=200)
    slug = models.SlugField('Slug', max_length=200, unique=True)
    description = models.TextField('Описание', blank=True)
    order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Категория страниц'
        verbose_name_plural = 'Категории страниц'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('pages:category_detail', kwargs={'slug': self.slug})


class Page(models.Model):
    """Статичная страница (about, partners, contacts и т.д.)."""
    title = models.CharField('Заголовок', max_length=300)
    slug = models.SlugField('Slug', max_length=300, unique=True,
        help_text='URL страницы: about, partners, contacts',
    )
    category = models.ForeignKey(
        PageCategory, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pages', verbose_name='Категория',
    )
    body = models.TextField('Контент', help_text='HTML-контент страницы')
    meta_title = models.CharField('META Title', max_length=200, blank=True)
    meta_description = models.TextField('META Description', blank=True)
    og_image = models.ImageField('OG Image', upload_to='pages/og/', blank=True)
    is_published = models.BooleanField('Опубликована', default=True)
    order = models.PositiveIntegerField('Порядок', default=0)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class Meta:
        verbose_name = 'Страница'
        verbose_name_plural = 'Страницы'
        ordering = ['order', 'title']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('pages:page_detail', kwargs={'slug': self.slug})


class BlogCategory(models.Model):
    """Категория блога."""
    name = models.CharField('Название', max_length=200)
    slug = models.SlugField('Slug', max_length=200, unique=True)

    class Meta:
        verbose_name = 'Категория блога'
        verbose_name_plural = 'Категории блога'
        ordering = ['name']

    def __str__(self):
        return self.name


class BlogPost(models.Model):
    """Статья блога."""
    title = models.CharField('Заголовок', max_length=300)
    slug = models.SlugField('Slug', max_length=300, unique=True)
    excerpt = models.TextField('Краткое описание', blank=True,
        help_text='Текст для карточки в списке блога',
    )
    body = models.TextField('Контент', help_text='HTML-контент статьи')
    cover_image = models.ImageField('Обложка', upload_to='blog/covers/', blank=True)
    author = models.CharField('Автор', max_length=200, blank=True)
    category = models.ForeignKey(
        BlogCategory, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='posts', verbose_name='Категория',
    )
    meta_title = models.CharField('META Title', max_length=200, blank=True)
    meta_description = models.TextField('META Description', blank=True)
    is_published = models.BooleanField('Опубликована', default=True)
    published_at = models.DateTimeField('Дата публикации')
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class Meta:
        verbose_name = 'Статья'
        verbose_name_plural = 'Статьи'
        ordering = ['-published_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['-published_at', 'is_published']),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('pages:blog_detail', kwargs={'slug': self.slug})


class MenuItem(models.Model):
    """Пункт навигации, управляемый из админки."""

    class LinkType(models.TextChoices):
        ROUTE = 'route', 'Маршрут Django'
        PAGE = 'page', 'Страница CMS'
        CATEGORY = 'category', 'Категория страниц'
        URL = 'url', 'Внешняя ссылка'

    title = models.CharField('Название', max_length=100)
    link_type = models.CharField(
        'Тип ссылки', max_length=10,
        choices=LinkType.choices, default=LinkType.ROUTE,
    )
    named_url = models.CharField(
        'Маршрут Django', max_length=200, blank=True,
        help_text='Например: home, catalog:catalog, pages:blog_list',
    )
    page = models.ForeignKey(
        Page, on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Страница CMS',
        help_text='Выбрать страницу (для типа «Страница CMS»)',
    )
    page_category = models.ForeignKey(
        PageCategory, on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Категория страниц',
        help_text='Выбрать категорию (для типа «Категория страниц»)',
    )
    external_url = models.URLField(
        'Внешняя ссылка', blank=True,
        help_text='URL для редиректа (для типа «Внешняя ссылка»)',
    )
    open_in_new_tab = models.BooleanField('Открывать в новой вкладке', default=False)
    order = models.PositiveIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активен', default=True)

    class Meta:
        verbose_name = 'Пункт меню'
        verbose_name_plural = 'Навигация'
        ordering = ['order']
        indexes = [
            models.Index(fields=['is_active', 'order']),
        ]

    def __str__(self):
        return self.title

    def get_url(self):
        """Возвращает URL пункта меню."""
        if self.link_type == self.LinkType.PAGE and self.page:
            return self.page.get_absolute_url()
        if self.link_type == self.LinkType.CATEGORY and self.page_category:
            return self.page_category.get_absolute_url()
        if self.link_type == self.LinkType.URL and self.external_url:
            return self.external_url
        if self.link_type == self.LinkType.ROUTE and self.named_url:
            try:
                return reverse(self.named_url)
            except NoReverseMatch:
                return '#'
        return '#'


class HeroSection(models.Model):
    """Hero-секция главной страницы."""
    title = models.TextField('Заголовок (H1)')
    subtitle = models.TextField('Подзаголовок (H2)', blank=True)
    button_catalog_text = models.CharField(
        'Текст кнопки «Каталог»', max_length=100, default='В каталог',
    )
    button_buy_text = models.CharField(
        'Текст кнопки «Купить»', max_length=100, default='Купить',
    )
    button_buy_url = models.CharField(
        'Ссылка кнопки «Купить»', max_length=500, blank=True,
        help_text='Произвольный URL, например: https://example.com/promo',
    )
    is_active = models.BooleanField('Активна', default=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class Meta:
        verbose_name = 'Hero главной'
        verbose_name_plural = 'Hero главной'

    def __str__(self):
        return self.title or 'Hero Section'

    def get_catalog_url(self):
        try:
            return reverse('catalog:catalog')
        except NoReverseMatch:
            return '/catalog/'


class HeroCard(models.Model):
    """Карточка товара в hero-секции."""
    hero = models.ForeignKey(
        HeroSection, on_delete=models.CASCADE,
        related_name='cards', verbose_name='Hero',
    )
    image = models.ImageField(
        'Изображение товара', upload_to='hero/cards/',
    )
    count_image = models.FileField(
        'SVG кол-ва', upload_to='hero/counter/',
        help_text='SVG-картинка с числом (5.svg, 17.svg, 30.svg)',
        blank=True,
    )
    order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Карточка hero'
        verbose_name_plural = 'Карточки hero'
        ordering = ['order']

    def __str__(self):
        return f'Карточка #{self.order}'


class FeatureSlide(models.Model):
    """Слайд секции Features на главной."""

    class MediaType(models.TextChoices):
        IMAGE = 'image', 'Картинка'
        VIDEO = 'video', 'Видео'

    class TextColor(models.TextChoices):
        BLACK = 'black', 'Чёрный (на светлом фоне)'
        WHITE = 'white', 'Белый (на тёмном фоне)'

    title = models.CharField('Заголовок', max_length=300)
    text = models.TextField(
        'Текст',
        help_text='Поддерживает HTML-теги. Для ссылок используйте &lt;a href="..."&gt;...&lt;/a&gt;',
    )
    text_color = models.CharField(
        'Цвет текста', max_length=10,
        choices=TextColor.choices, default=TextColor.BLACK,
        help_text='Цвет заголовка и текста. На светлом фоне — чёрный, на тёмном — белый.',
    )
    media_type = models.CharField(
        'Тип контента', max_length=5,
        choices=MediaType.choices, default=MediaType.IMAGE,
    )
    image = models.ImageField(
        'Картинка (десктоп)', upload_to='features/', blank=True,
        help_text='Фоновое изображение слайда. Используется на десктопе и как фолбэк для мобильных.',
    )
    image_mobile = models.ImageField(
        'Картинка (мобильная)', upload_to='features/mobile/', blank=True,
        help_text='Опционально. Если не указана — используется десктопная.',
    )
    video = models.FileField(
        'Видео (десктоп)', upload_to='features/videos/', blank=True,
        help_text='MP4 видео для фона слайда. Используется на десктопе и как фолбэк для мобильных.',
    )
    video_mobile = models.FileField(
        'Видео (мобильное)', upload_to='features/videos/mobile/', blank=True,
        help_text='Опционально. Вертикальный кроп для мобильных. Если не указано — '
                  'используется десктопное, но у горизонтального видео на узкой карточке '
                  'будут обрезаны бока.',
    )
    video_poster = models.ImageField(
        'Обложка видео', upload_to='features/posters/', blank=True,
        help_text='Превью-картинка пока видео загружается',
    )
    order = models.PositiveIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активен', default=True)

    class Meta:
        verbose_name = 'Слайд Features'
        verbose_name_plural = 'Слайды Features'
        ordering = ['order']

    def __str__(self):
        return self.title


class PromoBlock(models.Model):
    """Промо-блок на главной (квиз, партнёры, тату и т.д.)."""
    slug = models.SlugField('Ключ', max_length=50, unique=True,
        help_text='Уникальный ключ: quiz, partners, tattoo',
    )
    title = models.TextField('Заголовок')
    subtitle = models.TextField('Подзаголовок', blank=True)
    text = models.TextField('Текст', blank=True)
    button_text = models.CharField('Текст кнопки', max_length=200, blank=True)
    button_url = models.CharField('Ссылка кнопки', max_length=500, blank=True,
        help_text='URL или пусто если кнопка открывает модалку',
    )
    image = models.ImageField('Основная картинка', upload_to='promo/', blank=True)
    is_active = models.BooleanField('Активен', default=True)

    class Meta:
        verbose_name = 'Промо-блок'
        verbose_name_plural = 'Промо-блоки'

    def __str__(self):
        return f'{self.slug} — {self.title[:50]}'


class ServicePage(models.Model):
    """Служебная страница (подтверждение email, ошибки и т.д.), редактируемая из админки."""
    slug = models.SlugField('Ключ', max_length=100, unique=True,
        help_text='check_email, email_verified, email_error',
    )
    title = models.CharField('Заголовок', max_length=300)
    description = models.TextField('Описание', blank=True)
    button_text = models.CharField('Текст кнопки', max_length=200, blank=True)
    button_url = models.CharField('Ссылка кнопки', max_length=500, blank=True, default='/')

    class Meta:
        verbose_name = 'Служебная страница'
        verbose_name_plural = 'Служебные страницы'
        ordering = ['slug']

    def __str__(self):
        return f'{self.slug} — {self.title}'


class PromoImage(models.Model):
    """Картинка галереи промо-блока (тату и т.д.)."""
    promo = models.ForeignKey(
        PromoBlock, on_delete=models.CASCADE,
        related_name='images', verbose_name='Промо-блок',
    )
    image = models.ImageField('Изображение', upload_to='promo/gallery/')
    order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Картинка промо'
        verbose_name_plural = 'Картинки промо'
        ordering = ['order']

    def __str__(self):
        return f'Фото #{self.order}'


class ContactSettings(models.Model):
    """Контакты компании: телефоны, соцсети, реквизиты, адрес офиса.

    Singleton (pk=1): единственный источник контактных данных для футера,
    страницы контактов, карты, маршрутов и JSON-LD. Раньше всё это было
    захардкожено в шаблонах — см. docs/contact_settings.md.

    Форматирование (телефон для показа, ссылки мессенджеров, строка адреса)
    живёт здесь, а не в шаблонах: одни и те же значения нужны в нескольких
    местах, а собирать их вручную в каждом — путь к расхождениям.
    """

    phone = models.CharField(
        'Телефон', max_length=32,
        help_text='В международном формате, только + и цифры: +77766103836',
    )
    whatsapp_phone = models.CharField(
        'Телефон WhatsApp', max_length=32, blank=True,
        help_text='Если пусто — используется основной телефон',
    )
    telegram_username = models.CharField(
        'Telegram', max_length=64, blank=True,
        help_text='Имя пользователя: drjoysoriginal. Можно вставить с @ или ссылкой — '
                  'приведём к имени сами. Пусто — канал не показывается',
    )
    email = models.EmailField(
        'Email', blank=True,
        help_text='Пусто — канал не показывается',
    )

    # Пустая ссылка = канала нет: ни иконки в футере, ни sameAs в JSON-LD. Подсказка
    # стоит у каждого поля, а не только у первого: в форме бэкофиса они идут вразбивку
    instagram_url = models.URLField(
        'Instagram', max_length=300, blank=True,
        help_text='Полная ссылка. Пусто — иконка не показывается',
    )
    tiktok_url = models.URLField(
        'TikTok', max_length=300, blank=True,
        help_text='Полная ссылка. Пусто — иконка не показывается',
    )
    youtube_url = models.URLField(
        'YouTube', max_length=300, blank=True,
        help_text='Полная ссылка. Пусто — иконка не показывается',
    )
    marketplace_url = models.URLField(
        'Маркетплейс', max_length=300, blank=True,
        help_text='Витрина на Wildberries или другом маркетплейсе. Пусто — ссылки нет',
    )

    legal_name = models.CharField(
        'Юридическое название', max_length=200,
        help_text='Как в свидетельстве: ТОО «DR JOYS»',
    )
    bin = models.CharField(
        'БИН', max_length=12,
        help_text='12 цифр',
    )
    bin_label = models.CharField(
        'Подпись БИН', max_length=16,
        help_text='Как называется код на этом языке: БИН / БСН / BIN',
    )

    address_locality = models.CharField(
        'Город', max_length=100,
        help_text='Без приставки «г.»: Астана',
    )
    address_street = models.CharField(
        'Улица, дом', max_length=255,
        help_text='Без города: р-н Байконыр, ул. А. Бараева, д. 13, н.п. 5',
    )
    work_hours = models.CharField(
        'Часы работы', max_length=120, blank=True,
        help_text='Пн–Пт 10:00–19:00. Пусто — адрес показывается без графика',
    )
    # Координаты nullable, хотя офис у нас один и всегда известен: load() создаёт
    # синглтон через get_or_create() без аргументов, и NOT NULL без default уронил бы
    # контекст-процессор с IntegrityError на каждой странице, если строки вдруг нет.
    office_lat = models.DecimalField(
        'Широта', max_digits=9, decimal_places=6, null=True, blank=True,
        help_text='Широта офиса, как в 2ГИС: 51.158240',
    )
    office_lng = models.DecimalField(
        'Долгота', max_digits=9, decimal_places=6, null=True, blank=True,
        help_text='Долгота офиса, как в 2ГИС: 71.435760',
    )

    class Meta:
        verbose_name = 'Контакты компании'
        verbose_name_plural = 'Контакты компании'

    def __str__(self):
        return 'Контакты компании'

    def save(self, *args, **kwargs):
        # Singleton: всегда pk=1
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @staticmethod
    def _digits(value):
        return ''.join(ch for ch in (value or '') if ch.isdigit())

    @staticmethod
    def normalize_telegram_username(value):
        """Имя пользователя из того, что удобно вставить: @name, t.me/name, ссылка.

        Чистим при чтении, а не в save(): так ссылка цела при любом содержимом колонки,
        включая запись в обход save() (`queryset.update()`, перенос базы с прода).
        Приводить саму колонку к чистому виду — дело формы бэкофиса (§6): там заказчик
        видит результат. Отсюда же форма и берёт эту функцию, чтобы не плодить второй
        регексп. Ровно та же схема, что у телефона: `_digits` чистит на чтении.
        """
        value = (value or '').strip()
        return _TELEGRAM_URL_PREFIX.sub('', value).strip('@/ ')

    @staticmethod
    def is_telegram_username(handle):
        """Соберётся ли с этим именем рабочая ссылка t.me.

        Применяется к уже нормализованному имени. Живёт здесь, а не в форме
        бэкофиса: правило одно, а мест два — форма отбивает кривой ввод понятной
        ошибкой, а чтение (ниже) считает битое имя пустым. Второго регекспа
        в проекте быть не должно (§6).
        """
        return bool(_TELEGRAM_USERNAME.match(handle))

    @classmethod
    def _format_phone(cls, value):
        """Телефон для показа человеку: +7 776 610 38 36.

        Форматируем только казахстанские номера (+7 и 11 цифр) — правила
        группировки у каждой страны свои, выдумывать их для стран, которых
        у нас нет, незачем: такой номер отдаём как есть.
        """
        digits = cls._digits(value)
        if len(digits) == 11 and digits[0] == '7':
            return f'+{digits[0]} {digits[1:4]} {digits[4:7]} {digits[7:9]} {digits[9:]}'
        return value

    @property
    def phone_display(self):
        return self._format_phone(self.phone)

    @classmethod
    def to_e164(cls, value):
        """«+» и цифры — вид, в котором номер годится для ссылки и для разметки.

        Пробел в `tel:` URI недопустим по RFC 3966, а в JSON-LD `telephone`
        Google ждёт международный формат — из `+7 (776) 610-38-36` ссылка
        должна собраться как `tel:+77766103836`. Человеку номер по-прежнему
        показывает `phone_display`: группировку мы не съедаем (§3.2).

        Публичный и параметризованный по образцу `normalize_telegram_username`:
        форма бэкофиса (§6) обязана канонизировать телефон в колонке и зовёт
        отсюда, а не пишет второе такое же выражение.
        """
        digits = cls._digits(value)
        return f'+{digits}' if digits else ''

    @property
    def phone_e164(self):
        return self.to_e164(self.phone)

    @property
    def _whatsapp_number(self):
        """Номер WhatsApp: свой, если задан, иначе основной.

        Одно место на карточку и на ссылку: у дистрибьюторского WhatsApp (§1)
        номер отличается от основного, и если бы карточка выбирала его по
        непустой строке, а ссылка — по наличию цифр, то на значении вроде
        «уточняется» карточка показала бы одно, а ссылка повела на другое.
        """
        return self.whatsapp_phone if self._digits(self.whatsapp_phone) else self.phone

    @property
    def whatsapp_display(self):
        return self._format_phone(self._whatsapp_number)

    @property
    def whatsapp_url(self):
        digits = self._digits(self._whatsapp_number)
        return f'https://wa.me/{digits}' if digits else ''

    @property
    def _telegram_handle(self):
        """Имя из колонки — но только если ссылка t.me с ним будет рабочей.

        Тот же инвариант, что у `tel:` (§2R): ссылка цела при любом содержимом
        колонки, включая запись в обход формы. На имени вроде «др джойс» канал
        ведёт себя как пустой — не рисуется вовсе, вместо битой ссылки в футере
        и в `sameAs`.
        """
        handle = self.normalize_telegram_username(self.telegram_username)
        return handle if self.is_telegram_username(handle) else ''

    @property
    def telegram_url(self):
        handle = self._telegram_handle
        return f'https://t.me/{handle}' if handle else ''

    @property
    def telegram_display(self):
        handle = self._telegram_handle
        return f'@{handle}' if handle else ''

    @property
    def address_line(self):
        """Адрес одной строкой — так он выводится в фолбэке карты и в попапе метки."""
        parts = [self.address_locality, self.address_street, self.work_hours]
        return ', '.join(p for p in parts if p)

    @property
    def geo(self):
        """Координаты офиса для карты, маршрутов и JSON-LD — или None, если их нет.

        Пара, а не два поля: карту, попап и три deep-link'а маршрутов закрывает
        одна проверка `{% if contacts.geo %}`, а не две на каждый из них (§3.1).

        Отдаём float, а не Decimal: json.dumps Decimal не сериализует вообще,
        а в шаблоне он печатается со незначащими нулями — `data-lat="51.158240"`
        вместо `51.15824`.
        """
        if self.office_lat is None or self.office_lng is None:
            return None
        return {'lat': float(self.office_lat), 'lng': float(self.office_lng)}

    @property
    def social_links(self):
        """Непустые профили компании — для sameAs в JSON-LD.

        Порядок совпадает с прежним списком SAME_AS в pages/jsonld.py, чтобы после
        переезда (Сессия 2) разметка сошлась с эталоном. Telegram здесь наравне с
        соцсетями — он всегда был в sameAs; витрина маркетплейса тоже официальный
        профиль компании, её место здесь же.
        """
        links = [
            self.instagram_url,
            self.tiktok_url,
            self.youtube_url,
            self.telegram_url,
            self.marketplace_url,
        ]
        return [link for link in links if link]


class OfflineStore(models.Model):
    """Оффлайн-точка продаж: магазин партнёра на странице /partners/.

    Раньше точки жили HTML-таблицами в body страницы partners — карта по такой
    вёрстке не собирается. Теперь каждая точка — запись: карта, чипы городов,
    карточки списка и JSON-LD берут данные отсюда. Первичный перенос из body —
    команда import_offline_stores, дальше точки правятся в бэкофисе.
    """

    class Fulfillment(models.TextChoices):
        PICKUP_DELIVERY = 'pickup_delivery', 'Самовывоз и доставка'
        PICKUP = 'pickup', 'Только самовывоз'

    # ?m= с зумом мельче — центр города из ссылки на список филиалов, а не точка
    MIN_CENTER_ZOOM = 14

    city = models.CharField(
        'Город', max_length=100,
        help_text='Без приставки «г.»: Алматы. Чипы городов на странице собираются из этого поля',
    )
    name = models.CharField('Магазин', max_length=200)
    address = models.CharField(
        'Адрес', max_length=255,
        help_text='Без города: Ермека Серкебаева, 287Б',
    )
    # Координаты nullable: точка без них показывается в списке, но не на карте —
    # это штатное состояние для новых точек, пока не вставлена ссылка 2ГИС
    lat = models.DecimalField(
        'Широта', max_digits=9, decimal_places=6, null=True, blank=True,
        help_text='Пусто — возьмём из ссылки 2ГИС при сохранении',
    )
    lng = models.DecimalField(
        'Долгота', max_digits=9, decimal_places=6, null=True, blank=True,
    )
    map_url = models.URLField(
        'Ссылка 2ГИС', max_length=500, blank=True,
        help_text='Ссылка на карточку точки в 2ГИС — из неё же извлекаются координаты',
    )
    fulfillment = models.CharField(
        'Формат', max_length=20,
        choices=Fulfillment.choices, default=Fulfillment.PICKUP_DELIVERY,
    )
    is_active = models.BooleanField('Активна', default=True)
    order = models.PositiveIntegerField('Порядок', default=0)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class Meta:
        verbose_name = 'Оффлайн точка'
        verbose_name_plural = 'Оффлайн точки'
        ordering = ['city', 'order', 'name', 'address']
        indexes = [
            models.Index(fields=['is_active', 'city']),
        ]

    def __str__(self):
        return f'{self.name} — {self.city}, {self.address}'

    @property
    def geo(self):
        """Пара координат для карты и JSON-LD или None — как ContactSettings.geo:
        одна проверка на карту, попап и разметку; float, потому что Decimal
        не переживает json.dumps и печатается с незначащими нулями."""
        if self.lat is None or self.lng is None:
            return None
        return {'lat': float(self.lat), 'lng': float(self.lng)}

    @classmethod
    def coords_from_2gis(cls, url):
        """(lat, lng) из ссылки 2ГИС или None.

        Единственный разбор таких ссылок в проекте: им пользуются и разовый
        импорт из body страницы, и форма бэкофиса (вставил ссылку — координаты
        заполнились сами). В пути карточки координаты — сама точка, берём всегда;
        в m= — центр карты, который годится только при крупном зуме: на мелком
        это центр города из ссылки на список филиалов.
        """
        if not url:
            return None
        parts = urlsplit(unquote(url))
        m = _GIS_PATH_POINT.search(parts.path)
        if m:
            return cls._valid_pair(m.group(2), m.group(1))
        m = _GIS_MAP_CENTER.search(parts.query)
        if m and float(m.group(3) or 0) >= cls.MIN_CENTER_ZOOM:
            return cls._valid_pair(m.group(2), m.group(1))
        return None

    @staticmethod
    def _valid_pair(lat_str, lng_str):
        """Отсекает пары, не похожие на координаты в наших краях: регексп мог
        зацепить в URL что-то другое, и точка уехала бы в океан."""
        lat, lng = float(lat_str), float(lng_str)
        if 35 <= lat <= 60 and 40 <= lng <= 95:
            return lat, lng
        return None
