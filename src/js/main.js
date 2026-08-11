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

// --------------------------------------------
// 13. CART MODAL — загрузка из API, update, remove
// --------------------------------------------
function initCartModal() {
    const cartOverlay = document.getElementById('modalCart');
    if (!cartOverlay) return;

    const sym = window.DRJOYS?.currencySymbol || '₸';
    const paySym = window.DRJOYS?.paymentCurrencySymbol || '';
    const needsConv = window.DRJOYS?.needsConversion || false;
    let cartData = { items: [], cart_total: '0', cart_old_total: '0', cart_count: 0 };

    function fmtPrice(val) {
        return parseFloat(val).toLocaleString('ru-RU') + ' ' + sym;
    }

    function fmtPayment(val) {
        return parseFloat(val).toLocaleString('ru-RU') + ' ' + paySym;
    }

    function renderCart() {
        const listEl = document.getElementById('cartItemsList');
        const emptyEl = document.getElementById('cartEmpty');
        const footerEl = document.getElementById('cartFooter');
        const items = cartData.items;

        if (!items.length) {
            if (listEl) listEl.innerHTML = '';
            if (emptyEl) { emptyEl.classList.remove('hidden'); emptyEl.classList.add('flex'); }
            if (footerEl) footerEl.classList.add('hidden');
            return;
        }

        if (emptyEl) { emptyEl.classList.add('hidden'); emptyEl.classList.remove('flex'); }
        if (footerEl) footerEl.classList.remove('hidden');

        if (listEl) {
            listEl.innerHTML = items.map(item => {
                const hasOld = item.old_price && parseFloat(item.old_price) > parseFloat(item.price);
                const minusSvg = item.qty <= 1
                    ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>'
                    : '<svg width="12" height="12" viewBox="0 0 16 16" fill="none"><path d="M3 8H13" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
                const minusAction = item.qty <= 1 ? 'remove' : 'minus';

                return `<div class="cart-item flex gap-3 py-3" data-size-id="${item.size_id}" data-price="${item.price}" data-old-price="${item.old_price || ''}">
                    <div class="w-15 h-15 shrink-0 rounded-lg overflow-hidden bg-stone-50">
                        <img src="${item.image_url || window.DRJOYS?.placeholderUrl || ''}" class="w-full h-full object-cover" alt="${item.name}" loading="lazy">
                    </div>
                    <div class="flex-1 min-w-0">
                        <p class="text-xs font-bold truncate">${item.name}</p>
                        <p class="text-[10px] text-gray-500">${item.size_name}</p>
                        <div class="flex items-center justify-between mt-1">
                            <div class="flex items-center gap-2">
                                <button class="cart-qty-btn" type="button" data-action="${minusAction}" aria-label="${window.DRJOYS.i18n.decrease}">${minusSvg}</button>
                                <span class="text-xs font-benzin min-w-5 text-center cart-item-qty">${item.qty}</span>
                                <button class="cart-qty-btn" type="button" data-action="plus" aria-label="${window.DRJOYS.i18n.increase}">
                                    <svg width="12" height="12" viewBox="0 0 16 16" fill="none"><path d="M8 3V13M3 8H13" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
                                </button>
                            </div>
                            <div class="flex items-center gap-1.5 flex-wrap justify-end">
                                <span class="text-[10px] text-stone-400 line-through cart-item-old-price ${hasOld ? '' : 'hidden'}">${hasOld ? fmtPrice(parseFloat(item.old_price) * item.qty) : ''}</span>
                                <span class="text-xs font-bold cart-item-price">${fmtPrice(item.subtotal)}</span>
                                ${item.payment_subtotal ? `<span class="text-[10px] text-stone-400">(${fmtPayment(item.payment_subtotal)})</span>` : ''}
                            </div>
                        </div>
                    </div>
                </div>`;
            }).join('');
        }

        // Totals
        const total = parseFloat(cartData.cart_total);
        const oldTotal = parseFloat(cartData.cart_old_total);
        const cartTotalEl = document.getElementById('cartTotal');
        const cartOldTotalEl = document.getElementById('cartOldTotal');
        const cartSavingsEl = document.getElementById('cartSavings');

        if (cartTotalEl) {
            let totalText = fmtPrice(total);
            if (needsConv && cartData.payment_total) {
                totalText += ' (' + fmtPayment(parseFloat(cartData.payment_total)) + ')';
            }
            cartTotalEl.textContent = totalText;
        }

        const savings = oldTotal - total;
        if (savings > 0 && cartOldTotalEl && cartSavingsEl) {
            cartOldTotalEl.textContent = fmtPrice(oldTotal);
            cartOldTotalEl.classList.remove('hidden');
            const percent = Math.round((savings / oldTotal) * 100);
            cartSavingsEl.textContent = '-' + percent + '%';
            cartSavingsEl.classList.remove('hidden');
        } else {
            if (cartOldTotalEl) cartOldTotalEl.classList.add('hidden');
            if (cartSavingsEl) cartSavingsEl.classList.add('hidden');
        }
    }

    async function loadCart() {
        try {
            const resp = await fetch('/orders/cart/');
            cartData = await resp.json();
            if (cartData.ok) {
                renderCart();
                updateBadges(cartData.cart_count, null);
            }
        } catch (e) {
            console.error('loadCart error:', e);
        }
    }

    // Load cart when modal opens
    cartOverlay.addEventListener('modal:open', () => loadCart());

    // Qty/remove via delegation
    cartOverlay.addEventListener('click', async (e) => {
        const btn = e.target.closest('.cart-qty-btn');
        if (!btn) return;

        const item = btn.closest('.cart-item');
        const sizeId = parseInt(item.dataset.sizeId);
        const qtyEl = item.querySelector('.cart-item-qty');
        let qty = parseInt(qtyEl.textContent) || 1;

        // Бэкенд возвращает полную корзину — рендерим из ответа, без второго GET
        function applyCart(result) {
            if (!result || !result.ok) return;
            cartData = result;
            renderCart();
            updateBadges(result.cart_count, null);
        }

        if (btn.dataset.action === 'remove') {
            applyCart(await apiPost('/orders/cart/remove/', { size_id: sizeId }));
            return;
        }
        if (btn.dataset.action === 'minus' && qty > 1) {
            qty -= 1;
        } else if (btn.dataset.action === 'plus' && qty < 99) {
            qty += 1;
        }
        qtyEl.textContent = qty; // оптимистично, ответ сервера поправит
        applyCart(await apiPost('/orders/cart/update/', { size_id: sizeId, qty }));
    });

    // Checkout → auth check → delivery
    // Checkout → страница оформления заказа
    const checkoutBtn = document.getElementById('cartCheckoutBtn');
    if (checkoutBtn) {
        checkoutBtn.addEventListener('click', () => {
            closeModal(cartOverlay);
            window.location.href = '/orders/checkout/';
        });
    }

    // Continue shopping
    const continueBtn = document.getElementById('cartContinueBtn');
    if (continueBtn) {
        continueBtn.addEventListener('click', () => closeModal(cartOverlay));
    }
}

onReady(initCartModal);

// --------------------------------------------
// 14. FAVORITES MODAL — загрузка из API, удаление
// --------------------------------------------
function initFavoritesModal() {
    const favOverlay = document.getElementById('modalFavorites');
    if (!favOverlay) return;

    const sym = window.DRJOYS?.currencySymbol || '₸';

    function renderFavorites(data) {
        const listEl = document.getElementById('favoritesList');
        const emptyEl = document.getElementById('favoritesEmpty');
        const items = data.items || [];

        if (!items.length) {
            if (listEl) listEl.innerHTML = '';
            if (emptyEl) { emptyEl.classList.remove('hidden'); emptyEl.classList.add('flex'); }
            return;
        }

        if (emptyEl) { emptyEl.classList.add('hidden'); emptyEl.classList.remove('flex'); }

        if (listEl) {
            listEl.innerHTML = items.map(item => `
                <div class="fav-item flex gap-3 p-2 rounded-xl bg-stone-50" data-product-id="${item.product_id}" data-first-size-id="${item.first_size_id || ''}">
                    <div class="w-20 h-20 shrink-0 rounded-lg overflow-hidden bg-stone-50">
                        <img src="${item.image_url || window.DRJOYS?.placeholderUrl || ''}" class="w-full h-full object-cover" alt="${item.name}" loading="lazy">
                    </div>
                    <div class="flex-1 min-w-0 flex flex-col justify-between py-1">
                        <div>
                            <p class="text-xs font-bold leading-tight">${item.name}</p>
                            ${item.price ? `<p class="text-xs text-red-500 font-benzin mt-1">${parseFloat(item.price).toLocaleString('ru-RU')} ${sym}${item.payment_price ? ` <span class="text-stone-400 font-normal">(${parseFloat(item.payment_price).toLocaleString('ru-RU')} ${window.DRJOYS?.paymentCurrencySymbol || ''})</span>` : ''}</p>` : ''}
                        </div>
                        ${item.first_size_id ? `<button class="fav-to-cart-btn text-[10px] uppercase font-bold text-gray-500 hover:text-black text-left" type="button">${window.DRJOYS.i18n.addToCart}</button>` : ''}
                    </div>
                    <button class="fav-remove-btn shrink-0 self-start text-gray-500 hover:text-red-500 p-1" type="button" aria-label="${window.DRJOYS.i18n.removeFromFav}">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="3 6 5 6 21 6"/>
                            <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                            <line x1="10" y1="11" x2="10" y2="17"/>
                            <line x1="14" y1="11" x2="14" y2="17"/>
                        </svg>
                    </button>
                </div>
            `).join('');
        }
    }

    async function loadFavorites() {
        try {
            const resp = await fetch('/orders/favorites/');
            const data = await resp.json();
            if (data.ok) {
                renderFavorites(data);
                updateBadges(null, data.fav_count);
            }
        } catch (e) {
            console.error('loadFavorites error:', e);
        }
    }

    // Load when modal opens
    favOverlay.addEventListener('modal:open', () => loadFavorites());

    // Remove + Add to cart via delegation
    favOverlay.addEventListener('click', async (e) => {
        // Remove
        const removeBtn = e.target.closest('.fav-remove-btn');
        if (removeBtn) {
            const item = removeBtn.closest('.fav-item');
            const productId = parseInt(item.dataset.productId);
            const result = await apiPost('/orders/favorites/remove/', { product_id: productId });
            if (result.ok) updateBadges(null, result.fav_count);
            loadFavorites();
            return;
        }

        // Add to cart
        const cartBtn = e.target.closest('.fav-to-cart-btn');
        if (cartBtn) {
            const item = cartBtn.closest('.fav-item');
            const sizeId = item.dataset.firstSizeId;
            if (!sizeId) return;
            cartBtn.disabled = true;
            const result = await apiPost('/orders/cart/add/', { size_id: parseInt(sizeId), qty: 1 });
            cartBtn.disabled = false;
            if (result.ok) {
                updateBadges(result.cart_count, null);
                cartBtn.textContent = '✓';
                setTimeout(() => { cartBtn.textContent = window.DRJOYS.i18n.addToCart; }, 800);
            }
        }
    });
}

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
