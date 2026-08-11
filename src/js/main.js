// ============================================
// MAIN.JS - Общие скрипты для всего сайта
// ============================================
import { apiPost } from './lib/api.js';
import { onReady } from './lib/on-ready.js';
import { openModal, closeModal, goToStep } from './lib/modal-core.js';
import { updateBadges } from './lib/badges.js';
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

// --------------------------------------------
// 15. PROFILE MODAL — навигация по шагам
// --------------------------------------------
function initProfileModal() {
    const profileOverlay = document.getElementById('modalProfile');
    if (!profileOverlay) return;

    const backBtn = document.getElementById('profileBackBtn');
    let stepHistory = ['1'];
    let ordersLoaded = false;
    let ordersData = [];

    const STATUS_CSS = {
        pending: 'order-status--processing',
        paid: 'order-status--processing',
        shipped: 'order-status--shipped',
        delivered: 'order-status--delivered',
        cancelled: 'order-status--processing',
    };

    function resetProfile() {
        stepHistory = ['1'];
        if (backBtn) backBtn.classList.add('hidden');
        closeModal(profileOverlay);
    }

    function goToProfileStep(stepNum) {
        if (stepHistory[stepHistory.length - 1] !== stepNum) {
            stepHistory.push(stepNum);
        }
        goToStep(profileOverlay, stepNum);

        if (backBtn) {
            backBtn.classList.toggle('hidden', stepHistory.length <= 1);
        }
    }

    function formatDate(isoStr) {
        const d = new Date(isoStr);
        return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
    }

    function formatAmount(amount, symbol) {
        const num = parseFloat(amount);
        return num.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) + ' ' + symbol;
    }

    async function loadOrders() {
        if (ordersLoaded) return;
        const loadingEl = document.getElementById('ordersLoading');
        const emptyEl = document.getElementById('ordersEmpty');
        const listEl = document.getElementById('ordersHistoryList');

        try {
            const resp = await fetch('/orders/history/', { credentials: 'same-origin' });
            const data = await resp.json();
            ordersLoaded = true;

            if (loadingEl) loadingEl.classList.add('hidden');

            if (!data.ok || !data.orders || data.orders.length === 0) {
                if (emptyEl) emptyEl.classList.remove('hidden');
                return;
            }

            ordersData = data.orders;

            ordersData.forEach(order => {
                const symbol = order.currency_symbol || '₸';
                const amount = order.display_amount || order.total_amount;
                const statusCls = STATUS_CSS[order.status] || 'order-status--processing';

                const btn = document.createElement('button');
                btn.className = 'order-card w-full text-left p-3 rounded-xl bg-stone-50 hover:bg-gray-200';
                btn.type = 'button';
                btn.dataset.orderId = order.id;
                btn.innerHTML = `
                    <div class="flex justify-between items-start">
                        <div>
                            <p class="text-sm font-bold">#${order.number}</p>
                            <p class="text-[10px] text-gray-500">${formatDate(order.created_at)}</p>
                        </div>
                        <span class="order-status ${statusCls} text-[10px] font-bold px-2 py-0.5 rounded-full">${order.status_display}</span>
                    </div>
                    <p class="text-xs font-benzin text-red-500 mt-2">${formatAmount(amount, symbol)}</p>
                `;

                btn.addEventListener('click', () => showOrderDetail(order));
                listEl.appendChild(btn);
            });
        } catch (err) {
            if (loadingEl) loadingEl.textContent = window.DRJOYS.i18n.loadError;
            console.error('Orders load error:', err);
        }
    }

    function showOrderDetail(order) {
        const titleEl = document.getElementById('orderDetailTitle');
        const contentEl = document.getElementById('orderDetailContent');
        const symbol = order.currency_symbol || '₸';
        const amount = order.display_amount || order.total_amount;
        const statusCls = STATUS_CSS[order.status] || 'order-status--processing';

        titleEl.textContent = `${window.DRJOYS.i18n.orderNum} #${order.number}`;

        let itemsHtml = '';
        (order.items || []).forEach(item => {
            itemsHtml += `
                <div class="flex gap-3 py-2">
                    <div class="w-12 h-12 shrink-0 rounded-lg overflow-hidden bg-stone-50">
                        <div class="w-full h-full bg-stone-50"></div>
                    </div>
                    <div class="flex-1">
                        <p class="text-xs font-bold">${item.product_name}</p>
                        <p class="text-[10px] text-gray-500">${window.DRJOYS.i18n.sizeLbl}: ${item.size_name} &middot; ${item.quantity} ${window.DRJOYS.i18n.pcsLbl}</p>
                        <p class="text-xs font-bold mt-1">${formatAmount(item.subtotal, symbol)}</p>
                    </div>
                </div>
            `;
        });

        contentEl.innerHTML = `
            <div class="flex justify-between items-center">
                <p class="text-xs text-gray-500">${formatDate(order.created_at)}</p>
                <span class="order-status ${statusCls} text-[10px] font-bold px-2 py-0.5 rounded-full">${order.status_display}</span>
            </div>
            <div class="flex flex-col divide-y divide-stone-50">
                ${itemsHtml}
            </div>
            <div>
                <p class="text-xs font-bold pb-1">${window.DRJOYS.i18n.deliveryAddr}</p>
                <p class="text-xs text-gray-500">${order.city}, ${order.address}</p>
            </div>
            <div class="flex justify-between items-center pt-2 border-t border-stone-50">
                <span class="font-benzin uppercase text-sm">${window.DRJOYS.i18n.totalLbl}</span>
                <span class="font-benzin text-red-500">${formatAmount(amount, symbol)}</span>
            </div>
        `;

        goToProfileStep('2-detail');
    }

    // Menu buttons
    profileOverlay.querySelectorAll('[data-profile-step]').forEach(btn => {
        btn.addEventListener('click', () => {
            const step = btn.dataset.profileStep;
            if (step === '2') loadOrders();
            goToProfileStep(step);
        });
    });

    // Back button
    if (backBtn) {
        backBtn.addEventListener('click', () => {
            stepHistory.pop();
            const prevStep = stepHistory[stepHistory.length - 1] || '1';
            goToStep(profileOverlay, prevStep);
            backBtn.classList.toggle('hidden', stepHistory.length <= 1);
        });
    }

    // Close button (remove inline onclick, use JS)
    const closeBtn = profileOverlay.querySelector('.modal-close');
    if (closeBtn) {
        closeBtn.removeAttribute('onclick');
        closeBtn.addEventListener('click', resetProfile);
    }

    // Logout
    const logoutBtn = document.getElementById('profileLogoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            await apiPost(`/${window.DRJOYS.lang}/accounts/logout/`, {});
            location.reload();
        });
    }

    // Close on overlay click
    profileOverlay.addEventListener('click', (e) => {
        if (e.target === profileOverlay) resetProfile();
    });
}

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

// --------------------------------------------
// 16.5. OPEN DELIVERY WITH PROFILE PRE-FILL
// --------------------------------------------
async function openDeliveryWithProfile(deliveryOverlay) {
    openModal(deliveryOverlay);
    try {
        const resp = await fetch(`/${window.DRJOYS.lang}/accounts/profile/`);
        const data = await resp.json();
        if (data.ok && data.data) {
            const d = data.data;
            const set = (id, val) => { const el = document.getElementById(id); if (el && val) el.value = val; };
            set('deliveryFirstName', d.first_name);
            set('deliveryLastName', d.last_name);
            set('deliveryPhone', d.phone);
            set('deliveryEmail', d.email);
        }
    } catch (e) {
        // Profile fetch failed — form stays empty, user fills manually
    }
}

// --------------------------------------------
// 17. DELIVERY MODAL — форма → checkout API → успех
// --------------------------------------------
function initDeliveryModal() {
    const deliveryOverlay = document.getElementById('modalDelivery');
    if (!deliveryOverlay) return;

    const form = document.getElementById('deliveryForm');
    const submitBtn = form ? form.querySelector('button[type="submit"]') : null;

    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            // Clear previous errors
            form.querySelectorAll('.modal-error').forEach(el => el.remove());

            const data = {
                first_name: form.querySelector('#deliveryFirstName')?.value || '',
                last_name: form.querySelector('#deliveryLastName')?.value || '',
                phone: form.querySelector('#deliveryPhone')?.value || '',
                email: form.querySelector('#deliveryEmail')?.value || '',
                city: form.querySelector('#deliveryCity')?.value || '',
                address: [
                    form.querySelector('#deliveryStreet')?.value || '',
                    form.querySelector('#deliveryHouse')?.value || '',
                    form.querySelector('#deliveryApt')?.value || '',
                ].filter(Boolean).join(', '),
            };

            if (submitBtn) submitBtn.disabled = true;
            const result = await apiPost('/orders/checkout/', data);
            if (submitBtn) submitBtn.disabled = false;

            if (result.ok) {
                updateBadges(0, null);

                if (result.payment_url) {
                    // Редирект на платёжную страницу VTB
                    window.location.href = result.payment_url;
                } else {
                    // Fallback — показать модалку успеха
                    closeModal(deliveryOverlay);
                    form.reset();
                    const successModal = document.getElementById('modalSuccess');
                    if (successModal) {
                        const sym = window.DRJOYS?.currencySymbol || '₸';
                        const title = document.getElementById('successTitle');
                        const text = document.getElementById('successText');
                        if (title) title.innerHTML = window.DRJOYS.i18n.orderPlaced;
                        if (text) text.textContent = `${window.DRJOYS.i18n.orderSummary} #${result.order_number} ${window.DRJOYS.i18n.orderSumPrefix} ${parseFloat(result.total).toLocaleString('ru-RU')} ${sym}`;
                        setTimeout(() => openModal(successModal), 200);
                    }
                }
            } else {
                // Show errors
                if (result.errors) {
                    for (const [field, msg] of Object.entries(result.errors)) {
                        const input = form.querySelector(`[name="${field}"]`);
                        if (input) {
                            const errEl = document.createElement('p');
                            errEl.className = 'modal-error text-xs text-red-500 mt-1';
                            errEl.textContent = msg;
                            input.parentElement.appendChild(errEl);
                        }
                    }
                } else if (result.error) {
                    const errEl = document.createElement('p');
                    errEl.className = 'modal-error text-xs text-red-500 mt-1';
                    errEl.textContent = result.error;
                    form.prepend(errEl);
                }
            }
        });
    }

    // Close on overlay click
    deliveryOverlay.addEventListener('click', (e) => {
        if (e.target === deliveryOverlay) closeModal(deliveryOverlay);
    });
}

onReady(initDeliveryModal);

onReady(initInteractiveModals);
onReady(initInteractiveModalForms);

onReady(initRegionDropdown);
onReady(initLangDropdown);
onReady(initHeroTitleFit);
