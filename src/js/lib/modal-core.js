// --------------------------------------------
// 0. УНИВЕРСАЛЬНЫЕ УТИЛИТЫ МОДАЛОК
// --------------------------------------------
export function openModal(overlay) {
    if (!overlay) return;
    overlay.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    // Close burger menu if open
    if (window._closeMenu) window._closeMenu();
    // Dispatch custom event for modals that need to load data
    overlay.dispatchEvent(new CustomEvent('modal:open'));
}

export function closeModal(overlay) {
    if (!overlay) return;
    overlay.classList.add('hidden');
    document.body.style.overflow = '';
    // Reset to step 1
    const steps = overlay.querySelectorAll('.modal-step');
    steps.forEach((step, i) => {
        step.classList.toggle('hidden', i !== 0);
    });
}

export function goToStep(overlay, stepNum) {
    if (!overlay) return;
    overlay.querySelectorAll('.modal-step').forEach(step => {
        step.classList.toggle('hidden', step.dataset.step !== String(stepNum));
    });
}

// Escape key — закрывает все видимые модалки
document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    document.querySelectorAll('.modal-overlay:not(.hidden)').forEach(overlay => {
        closeModal(overlay);
    });
});

// Click on overlay background — закрывает модалку
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
        closeModal(e.target);
    }
});

// Click on .modal-close — закрывает ближайшую модалку
document.addEventListener('click', (e) => {
    const closeBtn = e.target.closest('.modal-close');
    if (!closeBtn) return;
    const overlay = closeBtn.closest('.modal-overlay');
    if (overlay) closeModal(overlay);
});
