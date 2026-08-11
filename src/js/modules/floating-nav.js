import { openModal } from '../lib/modal-core.js';

// --------------------------------------------
// 10. FLOATING NAV — открытие модалок
// --------------------------------------------
export function initFloatingNav() {
    document.querySelectorAll('[data-open-modal]').forEach(btn => {
        btn.addEventListener('click', () => {
            const modalId = btn.dataset.openModal;
            const modal = document.getElementById(modalId);
            // Тот же атрибут читает initInteractiveModals(), но как slug
            // CMS-модалки (её оверлей — id="modal-<slug>"). Без проверки на
            // .modal-overlay slug, совпавший с любым строчным id страницы
            // (reviews, contacts, office…), раскрыл бы произвольную секцию
            // и залочил скролл
            if (modal && modal.classList.contains('modal-overlay')) openModal(modal);
        });
    });
}
