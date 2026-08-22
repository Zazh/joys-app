// ============================================
// MAIN.JS - Общие скрипты для всего сайта
// ============================================
import { apiPost } from './lib/api.js';
import { onReady } from './lib/on-ready.js';
import { openModal, closeModal, goToStep } from './lib/modal-core.js';
import { initPhoneMasks } from './lib/phone-mask.js';
import { initMobileMenu, initRegionDropdown, initLangDropdown } from './modules/nav.js';
import { initProductGridGap } from './modules/product-grid.js';
import { initProductImageSlider, initProductSlider, initDragCarousel } from './modules/sliders.js';
import { initFAQ, initHeroTitleFit } from './modules/home-widgets.js';
import { initInteractiveModals, initInteractiveModalForms } from './modules/interactive-modals.js';
import { initModalTriggers } from './modules/modal-triggers.js';
import { initProductBuy } from './modules/product-buy.js';
import { initOrderQuantity } from './modules/order-quantity.js';
import { initCartModal } from './modules/cart.js';
import { initFavoritesModal } from './modules/favorites.js';
import { initProfileModal } from './modules/profile.js';
import { initAuthModal } from './modules/auth.js';

// Глобальный доступ для inline-скриптов в шаблонах
window.openModal = openModal;
window.closeModal = closeModal;
window.goToStep = goToStep;
window.apiPost = apiPost;

// Инициализация масок телефона при загрузке
onReady(initPhoneMasks);

onReady(initMobileMenu);

initProductGridGap();

onReady(initProductImageSlider);

onReady(initFAQ);

onReady(initProductSlider);

onReady(initDragCarousel);

// ============================================
// SHOP — МОДАЛКИ МАГАЗИНА
// ============================================

onReady(initModalTriggers);

onReady(initProductBuy);

onReady(initOrderQuantity);

onReady(initCartModal);

onReady(initFavoritesModal);

onReady(initProfileModal);

onReady(initAuthModal);

onReady(initInteractiveModals);
onReady(initInteractiveModalForms);

onReady(initRegionDropdown);
onReady(initLangDropdown);
onReady(initHeroTitleFit);
