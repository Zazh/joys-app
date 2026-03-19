from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.views import View

from backoffice.mixins import BackofficeAccessMixin
from pages.models import HeroSection, HeroCard, FeatureSlide, PromoBlock, PromoImage
from modals.models import InteractiveModal, ModalStep
from inquiries.models import InquiryForm
from quiz.models import QuizQuestion, QuizOption, QuizRule, QuizResultText, QuizBackground
from catalog.models import Product


# ─── Обзор главной ───

class HomepageOverviewView(BackofficeAccessMixin, View):
    def get(self, request):
        hero = HeroSection.objects.prefetch_related('cards').first()
        features = FeatureSlide.objects.all()
        promos = list(PromoBlock.objects.prefetch_related('images').all())
        # Привязать модалки к промо-блокам по slug
        modal_map = {}
        for modal in InteractiveModal.objects.all():
            modal_map[modal.slug] = modal
        for promo in promos:
            promo.linked_modal = modal_map.get(promo.slug)
        return TemplateResponse(request, 'backoffice/homepage/overview.html', {
            'hero': hero,
            'features': features,
            'promos': promos,
        })


# ─── Hero-секция ───

class HeroEditView(BackofficeAccessMixin, View):
    def get(self, request):
        hero = HeroSection.objects.prefetch_related('cards').first()
        if not hero:
            hero = HeroSection.objects.create(title='', is_active=True)
        return TemplateResponse(request, 'backoffice/homepage/hero_form.html', {'hero': hero})

    def post(self, request):
        hero = HeroSection.objects.first()
        if not hero:
            hero = HeroSection()

        hero.title_ru = request.POST.get('title_ru', '').strip()
        hero.title_kk = request.POST.get('title_kk', '').strip()
        hero.title_en = request.POST.get('title_en', '').strip()
        hero.subtitle_ru = request.POST.get('subtitle_ru', '').strip()
        hero.subtitle_kk = request.POST.get('subtitle_kk', '').strip()
        hero.subtitle_en = request.POST.get('subtitle_en', '').strip()
        hero.button_catalog_text_ru = request.POST.get('button_catalog_text_ru', '').strip()
        hero.button_catalog_text_kk = request.POST.get('button_catalog_text_kk', '').strip()
        hero.button_catalog_text_en = request.POST.get('button_catalog_text_en', '').strip()
        hero.button_buy_text_ru = request.POST.get('button_buy_text_ru', '').strip()
        hero.button_buy_text_kk = request.POST.get('button_buy_text_kk', '').strip()
        hero.button_buy_text_en = request.POST.get('button_buy_text_en', '').strip()
        hero.button_buy_url = request.POST.get('button_buy_url', '').strip()
        hero.is_active = request.POST.get('is_active') == 'on'
        hero.save()

        messages.success(request, 'Hero-секция сохранена.')
        return redirect('backoffice:homepage_hero')


class HeroCardUploadView(BackofficeAccessMixin, View):
    def post(self, request):
        hero = HeroSection.objects.first()
        if not hero:
            messages.error(request, 'Сначала сохраните Hero-секцию.')
            return redirect('backoffice:homepage_hero')

        image = request.FILES.get('image')
        count_image = request.FILES.get('count_image')
        if image:
            order = hero.cards.count()
            card = HeroCard(hero=hero, image=image, order=order)
            if count_image:
                card.count_image = count_image
            card.save()
            messages.success(request, 'Карточка добавлена.')
        return redirect('backoffice:homepage_hero')


class HeroCardUpdateView(BackofficeAccessMixin, View):
    """Обновить существующую карточку: заменить image, count_image, порядок."""
    def post(self, request, card_pk):
        card = get_object_or_404(HeroCard, pk=card_pk)
        if 'image' in request.FILES:
            card.image = request.FILES['image']
        if 'count_image' in request.FILES:
            card.count_image = request.FILES['count_image']
        if request.POST.get('clear_count_image') == 'on':
            card.count_image = ''
        order = request.POST.get('order')
        if order is not None:
            card.order = int(order or 0)
        card.save()
        messages.success(request, f'Карточка #{card.order} обновлена.')
        return redirect('backoffice:homepage_hero')


class HeroCardDeleteView(BackofficeAccessMixin, View):
    def post(self, request):
        card_id = request.POST.get('card_id')
        if card_id:
            HeroCard.objects.filter(pk=card_id).delete()
            messages.success(request, 'Карточка удалена.')
        return redirect('backoffice:homepage_hero')


# ─── Feature-слайды ───

class FeatureSlideListView(BackofficeAccessMixin, View):
    def get(self, request):
        slides = FeatureSlide.objects.all()
        return TemplateResponse(request, 'backoffice/homepage/feature_list.html', {
            'slides': slides,
        })


class FeatureSlideEditView(BackofficeAccessMixin, View):
    def get(self, request, pk):
        slide = get_object_or_404(FeatureSlide, pk=pk)
        return TemplateResponse(request, 'backoffice/homepage/feature_form.html', {
            'slide': slide,
        })

    def post(self, request, pk):
        slide = get_object_or_404(FeatureSlide, pk=pk)
        self._fill(slide, request)
        slide.save()
        messages.success(request, f'Слайд «{slide.title_ru}» сохранён.')
        return redirect('backoffice:homepage_feature_edit', pk=slide.pk)

    @staticmethod
    def _fill(slide, request):
        slide.title_ru = request.POST.get('title_ru', '').strip()
        slide.title_kk = request.POST.get('title_kk', '').strip()
        slide.title_en = request.POST.get('title_en', '').strip()
        slide.text_ru = request.POST.get('text_ru', '').strip()
        slide.text_kk = request.POST.get('text_kk', '').strip()
        slide.text_en = request.POST.get('text_en', '').strip()
        slide.media_type = request.POST.get('media_type', 'image')
        slide.order = int(request.POST.get('order', 0) or 0)
        slide.is_active = request.POST.get('is_active') == 'on'
        if 'image' in request.FILES:
            slide.image = request.FILES['image']
        if 'video' in request.FILES:
            slide.video = request.FILES['video']
        if 'video_poster' in request.FILES:
            slide.video_poster = request.FILES['video_poster']


class FeatureSlideCreateView(BackofficeAccessMixin, View):
    def get(self, request):
        return TemplateResponse(request, 'backoffice/homepage/feature_form.html', {
            'slide': None,
        })

    def post(self, request):
        slide = FeatureSlide()
        FeatureSlideEditView._fill(slide, request)
        if not slide.title_ru:
            messages.error(request, 'Заголовок (RU) обязателен.')
            return TemplateResponse(request, 'backoffice/homepage/feature_form.html', {
                'slide': None,
            })
        slide.save()
        messages.success(request, f'Слайд «{slide.title_ru}» создан.')
        return redirect('backoffice:homepage_feature_edit', pk=slide.pk)


class FeatureSlideDeleteView(BackofficeAccessMixin, View):
    def post(self, request, pk):
        slide = get_object_or_404(FeatureSlide, pk=pk)
        title = slide.title_ru
        slide.delete()
        messages.success(request, f'Слайд «{title}» удалён.')
        return redirect('backoffice:homepage_features')


# ─── Промо-блоки ───

class PromoBlockEditView(BackofficeAccessMixin, View):
    def get(self, request, pk):
        promo = get_object_or_404(PromoBlock.objects.prefetch_related('images'), pk=pk)
        modal = InteractiveModal.objects.filter(slug=promo.slug).first()
        return TemplateResponse(request, 'backoffice/homepage/promo_form.html', {
            'promo': promo,
            'modal': modal,
        })

    def post(self, request, pk):
        promo = get_object_or_404(PromoBlock, pk=pk)

        promo.title_ru = request.POST.get('title_ru', '').strip()
        promo.title_kk = request.POST.get('title_kk', '').strip()
        promo.title_en = request.POST.get('title_en', '').strip()
        promo.subtitle_ru = request.POST.get('subtitle_ru', '').strip()
        promo.subtitle_kk = request.POST.get('subtitle_kk', '').strip()
        promo.subtitle_en = request.POST.get('subtitle_en', '').strip()
        promo.text_ru = request.POST.get('text_ru', '').strip()
        promo.text_kk = request.POST.get('text_kk', '').strip()
        promo.text_en = request.POST.get('text_en', '').strip()
        promo.button_text_ru = request.POST.get('button_text_ru', '').strip()
        promo.button_text_kk = request.POST.get('button_text_kk', '').strip()
        promo.button_text_en = request.POST.get('button_text_en', '').strip()
        promo.button_url = request.POST.get('button_url', '').strip()
        promo.is_active = request.POST.get('is_active') == 'on'
        if 'image' in request.FILES:
            promo.image = request.FILES['image']
        promo.save()

        messages.success(request, f'Промо-блок «{promo.slug}» сохранён.')
        return redirect('backoffice:homepage_promo_edit', pk=promo.pk)


class PromoGalleryUploadView(BackofficeAccessMixin, View):
    def post(self, request, pk):
        promo = get_object_or_404(PromoBlock, pk=pk)
        images = request.FILES.getlist('images')
        order = promo.images.count()
        for img in images:
            PromoImage.objects.create(promo=promo, image=img, order=order)
            order += 1
        if images:
            messages.success(request, f'{len(images)} фото загружено.')
        return redirect('backoffice:homepage_promo_edit', pk=promo.pk)


class PromoGalleryDeleteView(BackofficeAccessMixin, View):
    def post(self, request, pk):
        image_id = request.POST.get('image_id')
        if image_id:
            PromoImage.objects.filter(pk=image_id, promo_id=pk).delete()
            messages.success(request, 'Фото удалено.')
        return redirect('backoffice:homepage_promo_edit', pk=pk)


# ─── Модалки (отдельный раздел) ───

class ModalListView(BackofficeAccessMixin, View):
    def get(self, request):
        modals = list(InteractiveModal.objects.prefetch_related('steps').all())
        promo_map = {}
        for promo in PromoBlock.objects.all():
            promo_map.setdefault(promo.slug, []).append(promo)
        for modal in modals:
            modal.linked_promos = promo_map.get(modal.slug, [])
        return TemplateResponse(request, 'backoffice/homepage/modal_list.html', {
            'modals': modals,
        })


class ModalEditView(BackofficeAccessMixin, View):
    def get(self, request, pk):
        modal = get_object_or_404(
            InteractiveModal.objects.prefetch_related('steps', 'steps__inquiry_form'),
            pk=pk,
        )
        forms = InquiryForm.objects.filter(is_active=True).order_by('title')
        # Связанный промо-блок
        promo = PromoBlock.objects.filter(slug=modal.slug).first()
        return TemplateResponse(request, 'backoffice/homepage/modal_form.html', {
            'modal': modal,
            'inquiry_forms': forms,
            'promo': promo,
        })

    def post(self, request, pk):
        modal = get_object_or_404(InteractiveModal, pk=pk)

        modal.title = request.POST.get('title', '').strip()
        modal.slug = request.POST.get('slug', '').strip()
        modal.theme = request.POST.get('theme', 'dark')
        modal.trigger_text_ru = request.POST.get('trigger_text_ru', '').strip()
        modal.trigger_text_kk = request.POST.get('trigger_text_kk', '').strip()
        modal.trigger_text_en = request.POST.get('trigger_text_en', '').strip()
        modal.is_active = request.POST.get('is_active') == 'on'
        modal.save()

        for step in modal.steps.all():
            prefix = f'step_{step.pk}_'
            step.step_type = request.POST.get(f'{prefix}step_type', step.step_type)
            step.text_ru = request.POST.get(f'{prefix}text_ru', '').strip()
            step.text_kk = request.POST.get(f'{prefix}text_kk', '').strip()
            step.text_en = request.POST.get(f'{prefix}text_en', '').strip()
            step.button_text_ru = request.POST.get(f'{prefix}button_text_ru', '').strip()
            step.button_text_kk = request.POST.get(f'{prefix}button_text_kk', '').strip()
            step.button_text_en = request.POST.get(f'{prefix}button_text_en', '').strip()
            step.badge_text_ru = request.POST.get(f'{prefix}badge_text_ru', '').strip()
            step.badge_text_kk = request.POST.get(f'{prefix}badge_text_kk', '').strip()
            step.badge_text_en = request.POST.get(f'{prefix}badge_text_en', '').strip()
            step.cta_text_ru = request.POST.get(f'{prefix}cta_text_ru', '').strip()
            step.cta_text_kk = request.POST.get(f'{prefix}cta_text_kk', '').strip()
            step.cta_text_en = request.POST.get(f'{prefix}cta_text_en', '').strip()
            step.cta_url = request.POST.get(f'{prefix}cta_url', '').strip()
            step.order = int(request.POST.get(f'{prefix}order', step.order) or 0)
            form_id = request.POST.get(f'{prefix}inquiry_form')
            step.inquiry_form_id = form_id if form_id else None
            if f'{prefix}image' in request.FILES:
                step.image = request.FILES[f'{prefix}image']
            step.save()

        messages.success(request, f'Модалка «{modal.title}» сохранена.')
        return redirect('backoffice:modal_edit', pk=modal.pk)


class ModalStepCreateView(BackofficeAccessMixin, View):
    def post(self, request, pk):
        modal = get_object_or_404(InteractiveModal, pk=pk)
        order = modal.steps.count()
        step_type = request.POST.get('step_type', 'content')
        ModalStep.objects.create(modal=modal, order=order, step_type=step_type)
        messages.success(request, 'Шаг добавлен.')
        return redirect('backoffice:modal_edit', pk=modal.pk)


class ModalStepDeleteView(BackofficeAccessMixin, View):
    def post(self, request, pk, step_pk):
        ModalStep.objects.filter(pk=step_pk, modal_id=pk).delete()
        messages.success(request, 'Шаг удалён.')
        return redirect('backoffice:modal_edit', pk=pk)


# ─── Квиз ───

class QuizOverviewView(BackofficeAccessMixin, View):
    def get(self, request):
        questions = QuizQuestion.objects.prefetch_related('options').all()
        rules = QuizRule.objects.select_related('product').all()
        result_text = QuizResultText.load()
        backgrounds = QuizBackground.objects.all()
        products = Product.objects.filter(is_active=True).order_by('name_ru')
        return TemplateResponse(request, 'backoffice/homepage/quiz.html', {
            'questions': questions,
            'rules': rules,
            'result_text': result_text,
            'backgrounds': backgrounds,
            'products': products,
            'q1_choices': QuizRule.Q1_CHOICES,
            'q2_choices': QuizRule.Q2_CHOICES,
            'q3_choices': QuizRule.Q3_CHOICES,
            'q4_choices': QuizRule.Q4_CHOICES,
        })


class QuizQuestionSaveView(BackofficeAccessMixin, View):
    """Сохранить все вопросы + варианты inline."""
    def post(self, request):
        for q in QuizQuestion.objects.prefetch_related('options').all():
            prefix = f'q_{q.pk}_'
            q.text_ru = request.POST.get(f'{prefix}text_ru', '').strip()
            q.text_kk = request.POST.get(f'{prefix}text_kk', '').strip()
            q.text_en = request.POST.get(f'{prefix}text_en', '').strip()
            q.order = int(request.POST.get(f'{prefix}order', q.order) or 0)
            q.is_active = request.POST.get(f'{prefix}is_active') == 'on'
            q.save()

            for opt in q.options.all():
                op = f'opt_{opt.pk}_'
                opt.label_ru = request.POST.get(f'{op}label_ru', '').strip()
                opt.label_kk = request.POST.get(f'{op}label_kk', '').strip()
                opt.label_en = request.POST.get(f'{op}label_en', '').strip()
                opt.value = request.POST.get(f'{op}value', '').strip()
                opt.bg_color = request.POST.get(f'{op}bg_color', '').strip()
                opt.text_color = request.POST.get(f'{op}text_color', '').strip()
                opt.order = int(request.POST.get(f'{op}order', opt.order) or 0)
                opt.save()

        messages.success(request, 'Вопросы квиза сохранены.')
        return redirect('backoffice:quiz_overview')


class QuizResultTextSaveView(BackofficeAccessMixin, View):
    def post(self, request):
        rt = QuizResultText.load()
        rt.title_ru = request.POST.get('title_ru', '').strip()
        rt.title_kk = request.POST.get('title_kk', '').strip()
        rt.title_en = request.POST.get('title_en', '').strip()
        rt.button_text_ru = request.POST.get('button_text_ru', '').strip()
        rt.button_text_kk = request.POST.get('button_text_kk', '').strip()
        rt.button_text_en = request.POST.get('button_text_en', '').strip()
        rt.more_text_ru = request.POST.get('more_text_ru', '').strip()
        rt.more_text_kk = request.POST.get('more_text_kk', '').strip()
        rt.more_text_en = request.POST.get('more_text_en', '').strip()
        rt.save()
        messages.success(request, 'Тексты результата сохранены.')
        return redirect('backoffice:quiz_overview')


class QuizRuleCreateView(BackofficeAccessMixin, View):
    def post(self, request):
        product_id = request.POST.get('product')
        if not product_id:
            messages.error(request, 'Выберите товар.')
            return redirect('backoffice:quiz_overview')
        QuizRule.objects.create(
            q1_important=request.POST.get('q1_important', ''),
            q2_aroma=request.POST.get('q2_aroma', ''),
            q3_frequency=request.POST.get('q3_frequency', ''),
            q4_lube=request.POST.get('q4_lube', ''),
            product_id=product_id,
            priority=int(request.POST.get('priority', 0) or 0),
            is_active=True,
        )
        messages.success(request, 'Правило добавлено.')
        return redirect('backoffice:quiz_overview')


class QuizRuleDeleteView(BackofficeAccessMixin, View):
    def post(self, request, pk):
        QuizRule.objects.filter(pk=pk).delete()
        messages.success(request, 'Правило удалено.')
        return redirect('backoffice:quiz_overview')


class QuizBackgroundSaveView(BackofficeAccessMixin, View):
    def post(self, request):
        for bg in QuizBackground.objects.all():
            prefix = f'bg_{bg.pk}_'
            bg.is_dark_theme = request.POST.get(f'{prefix}is_dark') == 'on'
            bg.is_active = request.POST.get(f'{prefix}is_active') == 'on'
            if f'{prefix}image' in request.FILES:
                bg.image = request.FILES[f'{prefix}image']
            bg.save()
        messages.success(request, 'Фоны сохранены.')
        return redirect('backoffice:quiz_overview')
