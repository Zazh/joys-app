from django.db import models
from django.urls import reverse, NoReverseMatch


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

    title = models.CharField('Заголовок', max_length=300)
    text = models.TextField('Текст')
    media_type = models.CharField(
        'Тип контента', max_length=5,
        choices=MediaType.choices, default=MediaType.IMAGE,
    )
    image = models.ImageField(
        'Картинка', upload_to='features/', blank=True,
        help_text='Фоновое изображение слайда',
    )
    video = models.FileField(
        'Видео', upload_to='features/videos/', blank=True,
        help_text='MP4 видео для фона слайда',
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


class EmailTemplate(models.Model):
    """Шаблон email-письма, редактируемый из админки."""
    slug = models.SlugField('Ключ', max_length=100, unique=True,
        help_text='email_verify, password_reset, welcome, order_created, order_paid, order_shipped',
    )
    subject = models.CharField('Тема письма', max_length=300,
        help_text='Можно использовать {плейсхолдеры}: {order_number}, {user_name} и т.д.',
    )
    body = models.TextField('Текст письма',
        help_text='Плейн-текст. Плейсхолдеры: {user_name}, {verify_url}, {order_number} и т.д.',
    )
    description = models.TextField('Описание (для админа)', blank=True,
        help_text='Какие плейсхолдеры доступны, когда отправляется',
    )

    class Meta:
        verbose_name = 'Шаблон письма'
        verbose_name_plural = 'Шаблоны писем'
        ordering = ['slug']

    def __str__(self):
        return f'{self.slug} — {self.subject}'

    def render(self, context: dict) -> tuple:
        """Рендерит subject и body, подставляя плейсхолдеры.

        Returns:
            (subject, body) — готовые строки.
        """
        safe = _SafeDict(context)
        return self.subject.format_map(safe), self.body.format_map(safe)


class _SafeDict(dict):
    """dict, который возвращает {key} для отсутствующих ключей."""
    def __missing__(self, key):
        return '{' + key + '}'


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
