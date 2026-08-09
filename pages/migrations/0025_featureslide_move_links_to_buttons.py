import re

from django.db import migrations

LINK_RE = re.compile(r'\s*<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
TRAILING_BR_RE = re.compile(r'(\s*<br\s*/?>\s*)+$')


def move_links_to_buttons(apps, schema_editor):
    """Перенести ссылки из текста слайдов features в новую кнопку.

    Из каждого языка вынимается первый <a href>: его текст становится текстом
    кнопки на этом языке, href (из русской версии) — ссылкой кнопки. Сам тег
    из текста удаляется вместе с хвостовыми <br>.
    """
    FeatureSlide = apps.get_model('pages', 'FeatureSlide')
    for slide in FeatureSlide.objects.all():
        match_ru = LINK_RE.search(slide.text_ru or '')
        if not match_ru:
            continue
        slide.button_url = match_ru.group(1)
        slide.button_color = 'white'
        for lang in ('ru', 'kk', 'en'):
            text = getattr(slide, f'text_{lang}') or ''
            match = LINK_RE.search(text)
            label = (match or match_ru).group(2).strip()
            setattr(slide, f'button_text_{lang}', label)
            if match:
                text = LINK_RE.sub('', text, count=1)
                text = TRAILING_BR_RE.sub('', text).strip()
                setattr(slide, f'text_{lang}', text)
        slide.save()


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0024_featureslide_button_color_featureslide_button_text_and_more'),
    ]

    operations = [
        migrations.RunPython(move_links_to_buttons, migrations.RunPython.noop),
    ]
