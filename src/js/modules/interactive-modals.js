import { initInquiryForm } from '../lib/inquiry-form.js';
import { openModal, closeModal, goToStep } from '../lib/modal-core.js';

// --------------------------------------------
// 17.0 ИНТЕРАКТИВНЫЕ МОДАЛКИ (_interactive_modal.html)
// Открытие по data-open-modal="slug", шаги, закрытие. Жило в инлайн-скрипте
// главной — вынесено сюда, когда модалка понадобилась на странице товара
// (гид «Как выбрать размер» у категории)
// --------------------------------------------
export function initInteractiveModals() {
    document.querySelectorAll('[data-modal-slug]').forEach(overlay => {
        const slug = overlay.dataset.modalSlug;

        document.querySelectorAll(`[data-open-modal="${slug}"]`).forEach(btn => {
            btn.addEventListener('click', () => openModal(overlay));
        });

        overlay.querySelectorAll('.modal-close-interactive').forEach(btn => {
            btn.addEventListener('click', () => closeModal(overlay));
        });

        overlay.querySelectorAll('[data-next-step]').forEach(btn => {
            btn.addEventListener('click', () => goToStep(overlay, btn.dataset.nextStep));
        });
        overlay.querySelectorAll('[data-prev-step]').forEach(btn => {
            btn.addEventListener('click', () => goToStep(overlay, btn.dataset.prevStep));
        });

        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeModal(overlay);
        });
    });
}

// --------------------------------------------
// 17.1 ФОРМЫ ЗАЯВОК В МОДАЛКАХ (партнёрская, тату)
// Разметку даёт _interactive_modal.html, отправку — общий initInquiryForm
// --------------------------------------------
export function initInteractiveModalForms() {
    document.querySelectorAll('.interactive-modal-form').forEach(form => {
        initInquiryForm(form, {
            onSuccess: (result) => {
                closeModal(document.getElementById(`modal-${form.dataset.modalSlug}`));
                form.reset();

                const successOverlay = document.getElementById('modalSuccess');
                if (!successOverlay) return;
                const titleEl = document.getElementById('successTitle');
                const textEl = document.getElementById('successText');
                if (titleEl) titleEl.textContent = result.success_title || '';
                if (textEl) textEl.textContent = result.success_text || '';
                openModal(successOverlay);
                // Модалка сама фокус не забирает — уводим на заголовок,
                // иначе скринридер об успехе не скажет
                if (titleEl) titleEl.focus();
            },
        });
    });
}
