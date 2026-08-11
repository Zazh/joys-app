import { openModal } from '../lib/modal-core.js';

// --------------------------------------------
// 10. FLOATING NAV — открытие модалок
// --------------------------------------------
export function initFloatingNav() {
    document.querySelectorAll('[data-open-modal]').forEach(btn => {
        btn.addEventListener('click', () => {
            const modalId = btn.dataset.openModal;
            const modal = document.getElementById(modalId);
            if (modal) openModal(modal);
        });
    });
}
