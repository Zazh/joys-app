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
import { initHeartbeat, initFAQ, initHeroTitleFit } from './modules/home-widgets.js';
import { initInteractiveModals, initInteractiveModalForms } from './modules/interactive-modals.js';
import { initFloatingNav } from './modules/floating-nav.js';
import { initProductBuy } from './modules/product-buy.js';
import { initOrderQuantity } from './modules/order-quantity.js';
import { initCartModal } from './modules/cart.js';
import { initFavoritesModal } from './modules/favorites.js';
import { initProfileModal } from './modules/profile.js';
import { openDeliveryWithProfile, initDeliveryModal } from './modules/delivery.js';

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

onReady(initHeartbeat);

onReady(initFAQ);

onReady(initProductSlider);

onReady(initDragCarousel);

// ============================================
// SHOP — МОДАЛКИ МАГАЗИНА
// ============================================

onReady(initFloatingNav);

onReady(initProductBuy);

onReady(initOrderQuantity);

onReady(initCartModal);

onReady(initFavoritesModal);

onReady(initProfileModal);

// --------------------------------------------
// 16. AUTH MODAL — Email Login / Register / SSO
// --------------------------------------------
function initPasswordToggles() {
    document.querySelectorAll('[data-toggle-password]').forEach(btn => {
        btn.addEventListener('click', () => {
            const inputId = btn.dataset.togglePassword;
            const input = document.getElementById(inputId);
            if (!input) return;
            const isPassword = input.type === 'password';
            input.type = isPassword ? 'text' : 'password';
            btn.querySelector('.eye-open').classList.toggle('hidden', !isPassword);
            btn.querySelector('.eye-closed').classList.toggle('hidden', isPassword);
        });
    });
}

function initAuthModal() {
    const authOverlay = document.getElementById('modalAuth');
    if (!authOverlay) return;

    initPasswordToggles();

    const backBtn = document.getElementById('authBackBtn');
    let ssoPopup = null;
    let ssoPopupTimer = null;

    function resetAuth() {
        if (backBtn) backBtn.classList.add('hidden');
        authOverlay.querySelectorAll('input').forEach(i => { i.value = ''; });
        authOverlay.querySelectorAll('.text-red-500').forEach(el => {
            el.textContent = '';
            el.classList.add('hidden');
        });
        closeModal(authOverlay);
    }

    function showError(el, errors) {
        if (!el) return;
        const msgs = [];
        for (const key in errors) {
            const val = errors[key];
            if (Array.isArray(val)) msgs.push(...val);
            else msgs.push(val);
        }
        el.textContent = msgs.join(' ');
        el.classList.remove('hidden');
    }

    function handleAuthSuccess() {
        window.DRJOYS.isAuthenticated = true;
        if (window._afterAuthAction === 'delivery') {
            window._afterAuthAction = null;
            closeModal(authOverlay);
            const deliveryModal = document.getElementById('modalDelivery');
            if (deliveryModal) setTimeout(() => openDeliveryWithProfile(deliveryModal), 200);
        } else {
            location.reload();
        }
    }

    // --- Step navigation ---
    authOverlay.querySelectorAll('[data-auth-method]').forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.dataset.authMethod;
            goToStep(authOverlay, target);
            if (backBtn) backBtn.classList.toggle('hidden', target === '1');
        });
    });

    if (backBtn) {
        backBtn.addEventListener('click', () => {
            goToStep(authOverlay, '1');
            backBtn.classList.add('hidden');
        });
    }

    // --- EMAIL LOGIN ---
    const loginForm = document.getElementById('authLoginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const loginBtn = document.getElementById('authLoginBtn');
            const email = document.getElementById('authLoginEmail').value.trim();
            const password = document.getElementById('authLoginPassword').value;
            const errorEl = document.getElementById('authLoginError');
            errorEl.classList.add('hidden');

            loginBtn.disabled = true;
            try {
                const result = await apiPost(`/${window.DRJOYS.lang}/accounts/login/`, { email, password });
                loginBtn.disabled = false;
                if (result.ok) {
                    handleAuthSuccess();
                } else {
                    showError(errorEl, result.errors || {__all__: [window.DRJOYS.i18n.loginError]});
                }
            } catch (err) {
                loginBtn.disabled = false;
                showError(errorEl, {__all__: [window.DRJOYS.i18n.networkError]});
                console.error('Login error:', err);
            }
        });
    }

    // --- REGISTER ---
    const registerForm = document.getElementById('authRegisterForm');
    if (registerForm) {
        let registerSubmitting = false;
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (registerSubmitting) return;
            registerSubmitting = true;

            const registerBtn = document.getElementById('authRegisterBtn');
            const email = document.getElementById('authRegEmail').value.trim();
            const password1 = document.getElementById('authRegPassword1').value;
            const password2 = document.getElementById('authRegPassword2').value;
            const errorEl = document.getElementById('authRegError');
            errorEl.classList.add('hidden');

            const originalText = registerBtn.textContent;
            registerBtn.disabled = true;
            registerBtn.textContent = '...';
            try {
                const result = await apiPost(`/${window.DRJOYS.lang}/accounts/register/`, { email, password1, password2 });
                if (result.ok) {
                    if (result.redirect_url) {
                        window.location.href = result.redirect_url;
                        return; // Не разблокируем — идёт редирект
                    }
                    handleAuthSuccess();
                    return;
                }
                showError(errorEl, result.errors || {__all__: [window.DRJOYS.i18n.registerError]});
            } catch (err) {
                showError(errorEl, {__all__: [window.DRJOYS.i18n.networkError]});
                console.error('Register error:', err);
            }
            registerBtn.disabled = false;
            registerBtn.textContent = originalText;
            registerSubmitting = false;
        });
    }

    // --- SSO POPUP ---
    // ssoPopup.closed и window.opener ненадёжны: COOP рвёт связь окон,
    // как только popup уходит на страницу провайдера. Поэтому основной
    // канал — поллинг профиля до успеха или таймаута, а postMessage и
    // BroadcastChannel из sso_callback.html лишь ускоряют реакцию.
    function stopSSOWait() {
        clearInterval(ssoPopupTimer);
        ssoPopupTimer = null;
        ssoPopup = null;
    }

    function handleSSOComplete(success) {
        stopSSOWait();
        if (success) handleAuthSuccess();
    }

    authOverlay.querySelectorAll('[data-sso-provider]').forEach(btn => {
        btn.addEventListener('click', () => {
            stopSSOWait();
            const provider = btn.dataset.ssoProvider;
            const w = 500, h = 600;
            const left = (screen.width - w) / 2;
            const top = (screen.height - h) / 2;
            ssoPopup = window.open(
                `/accounts/${provider}/login/?process=login`,
                'drjoys_sso',
                'width=' + w + ',height=' + h + ',left=' + left + ',top=' + top + ',toolbar=no,menubar=no,scrollbars=yes'
            );
            let attempts = 0;
            ssoPopupTimer = setInterval(async () => {
                if (++attempts > 90) { stopSSOWait(); return; } // ~3 мин на вход
                try {
                    const resp = await fetch(`/${window.DRJOYS.lang}/accounts/profile/`);
                    const data = await resp.json();
                    if (data.ok) handleSSOComplete(true);
                } catch (e) { /* ещё не авторизован — ждём дальше */ }
            }, 2000);
        });
    });

    // Мгновенный сигнал из sso_callback.html — переживает COOP
    if (typeof BroadcastChannel !== 'undefined') {
        const ssoChannel = new BroadcastChannel('drjoys_sso');
        ssoChannel.addEventListener('message', (event) => {
            if (!event.data || event.data.type !== 'sso_complete') return;
            handleSSOComplete(event.data.success);
        });
    }

    // Listen for postMessage from SSO popup
    window.addEventListener('message', (event) => {
        if (event.origin !== window.location.origin) return;
        if (!event.data || event.data.type !== 'sso_complete') return;
        handleSSOComplete(event.data.success);
    });

    // --- Close handlers ---
    const closeBtn = authOverlay.querySelector('.modal-close');
    if (closeBtn) {
        closeBtn.removeAttribute('onclick');
        closeBtn.addEventListener('click', resetAuth);
    }

    authOverlay.addEventListener('click', (e) => {
        if (e.target === authOverlay) resetAuth();
    });
}

onReady(initAuthModal);

onReady(initDeliveryModal);

onReady(initInteractiveModals);
onReady(initInteractiveModalForms);

onReady(initRegionDropdown);
onReady(initLangDropdown);
onReady(initHeroTitleFit);
