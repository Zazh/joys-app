import { openModal, goToStep } from '../lib/modal-core.js';

// --------------------------------------------
// 1. БУРГЕР-МЕНЮ
// --------------------------------------------
export function initMobileMenu() {
    const menuBtn = document.getElementById('menuBtn');
    const mainNav = document.getElementById('mainNav');
    const navWrapper = document.querySelector('.nav_wrapper');
    if (!menuBtn || !mainNav || !navWrapper) return;

    let isMenuActive = false;

    function openMenu() {
        isMenuActive = true;
        const lines = menuBtn.querySelectorAll('span');
        lines[0].style.opacity = '0';
        lines[1].style.transform = 'rotate(45deg)';
        lines[2].style.transform = 'rotate(-45deg)';
        lines[3].style.opacity = '0';

        mainNav.classList.remove('hidden');
        mainNav.classList.add('flex');
        navWrapper.classList.add('bottom-0');
        navWrapper.classList.add('bg-white/75', 'backdrop-blur-xl');
    }

    function closeMenu() {
        isMenuActive = false;
        const lines = menuBtn.querySelectorAll('span');
        lines[0].style.opacity = '1';
        lines[1].style.transform = 'rotate(0deg)';
        lines[2].style.transform = 'rotate(0deg)';
        lines[3].style.opacity = '1';

        mainNav.classList.add('hidden');
        mainNav.classList.remove('flex');
        navWrapper.classList.remove('bottom-0');
        navWrapper.classList.remove('bg-white/75', 'backdrop-blur-xl');
    }

    menuBtn.addEventListener('click', () => {
        if (isMenuActive) closeMenu();
        else openMenu();
    });

    // Click on dark area (nav_wrapper, outside mainNav) closes menu
    navWrapper.addEventListener('click', (e) => {
        if (isMenuActive && e.target === navWrapper) closeMenu();
    });

    // Expose closeMenu for use by modals
    window._closeMenu = closeMenu;
}

// --------------------------------------------
// 18. DROPDOWN ВЫБОРА РЕГИОНА
// --------------------------------------------
export function initRegionDropdown() {
    const dropdown = document.getElementById('regionDropdown');
    const btn = document.getElementById('regionSwitcherBtn');
    const menu = document.getElementById('regionMenu');
    if (!dropdown || !btn || !menu) return;

    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = !menu.classList.contains('hidden');
        if (isOpen) {
            menu.classList.add('hidden');
            dropdown.classList.remove('open');
        } else {
            menu.classList.remove('hidden');
            dropdown.classList.add('open');
        }
    });

    // Закрытие по клику вне dropdown
    document.addEventListener('click', (e) => {
        if (!dropdown.contains(e.target)) {
            menu.classList.add('hidden');
            dropdown.classList.remove('open');
        }
    });

    // Автопоказ модалки при первом визите (нет cookie)
    const regionModal = document.getElementById('modalRegion');
    if (regionModal && !regionModal.classList.contains('hidden')) {
        openModal(regionModal);
    }

    // Шаги модалки: «Выбрать другой» → список регионов, «Назад» → шаг 1
    if (regionModal) {
        const showListBtn = document.getElementById('regionShowList');
        const regionBackBtn = document.getElementById('regionBackBtn');
        if (showListBtn) {
            showListBtn.addEventListener('click', () => {
                goToStep(regionModal, '2');
                if (regionBackBtn) regionBackBtn.classList.remove('hidden');
            });
        }
        if (regionBackBtn) {
            regionBackBtn.addEventListener('click', () => {
                goToStep(regionModal, '1');
                regionBackBtn.classList.add('hidden');
            });
        }
        // closeModal сбрасывает шаги на первый — прячем «Назад» на любом
        // пути закрытия (Escape, фон, крестик) по событию modal:close (SB-07)
        if (regionBackBtn) {
            regionModal.addEventListener('modal:close', () => regionBackBtn.classList.add('hidden'));
        }
    }
}

// --------------------------------------------
// 19. ВЫПАДАЮЩЕЕ МЕНЮ ЯЗЫКА
// --------------------------------------------
export function initLangDropdown() {
    const dropdown = document.getElementById('langDropdown');
    const btn = document.getElementById('langSwitcherBtn');
    const menu = document.getElementById('langMenu');
    if (!dropdown || !btn || !menu) return;

    // Toggle dropdown
    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = !menu.classList.contains('hidden');
        if (isOpen) {
            menu.classList.add('hidden');
            dropdown.classList.remove('open');
        } else {
            menu.classList.remove('hidden');
            dropdown.classList.add('open');
        }
    });

    // Выбор языка — ссылки с href уже ведут на /kk/..., /en/..., /ru/...
    // Навигация происходит через обычный переход по <a href>.

    // Закрытие по клику вне dropdown
    document.addEventListener('click', (e) => {
        if (!dropdown.contains(e.target)) {
            menu.classList.add('hidden');
            dropdown.classList.remove('open');
        }
    });
}
