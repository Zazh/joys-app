import { apiPost } from '../lib/api.js';
import { closeModal } from '../lib/modal-core.js';
import { updateBadges } from '../lib/badges.js';

// --------------------------------------------
// 13. CART MODAL — загрузка из API, update, remove
// --------------------------------------------
export function initCartModal() {
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
