import { apiPost } from '../lib/api.js';
import { closeModal } from '../lib/modal-core.js';
import { updateBadges } from '../lib/badges.js';
import { escapeHtml } from '../lib/escape.js';
import { formatMoney, formatPayment } from '../lib/money.js';

// --------------------------------------------
// 13. CART MODAL — загрузка из API, update, remove
// --------------------------------------------
export function initCartModal() {
    const cartOverlay = document.getElementById('modalCart');
    if (!cartOverlay) return;

    const needsConv = window.DRJOYS?.needsConversion || false;
    let cartData = { items: [], cart_total: '0', cart_old_total: '0', cart_count: 0 };
    // Счётчик поколений: ответы load/update/remove умеют приходить не в порядке
    // отправки — применяется только ответ самого свежего запроса
    let reqSeq = 0;

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
            const trashSvg = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>';

            listEl.innerHTML = items.map(item => {
                const hasOld = item.old_price && parseFloat(item.old_price) > parseFloat(item.price);
                const minusSvg = item.qty <= 1
                    ? trashSvg
                    : '<svg width="12" height="12" viewBox="0 0 16 16" fill="none"><path d="M3 8H13" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
                const minusAction = item.qty <= 1 ? 'remove' : 'minus';

                // Недоступная позиция: приглушение, метка вместо +/−, из
                // контролов только мусорка, цен нет (устарели/скрыты)
                const bottomRow = item.unavailable_label
                    ? `<span class="text-[10px] font-bold text-red-500 uppercase tracking-wider">${escapeHtml(item.unavailable_label)}</span>
                            <button class="cart-qty-btn" type="button" data-action="remove" aria-label="${window.DRJOYS.i18n.remove}">${trashSvg}</button>`
                    : `<div class="flex items-center gap-2">
                                <button class="cart-qty-btn" type="button" data-action="${minusAction}" aria-label="${window.DRJOYS.i18n.decrease}">${minusSvg}</button>
                                <span class="text-xs font-benzin min-w-5 text-center cart-item-qty">${escapeHtml(item.qty)}</span>
                                <button class="cart-qty-btn" type="button" data-action="plus" aria-label="${window.DRJOYS.i18n.increase}">
                                    <svg width="12" height="12" viewBox="0 0 16 16" fill="none"><path d="M8 3V13M3 8H13" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
                                </button>
                            </div>
                            <div class="flex items-center gap-1.5 flex-wrap justify-end">
                                <span class="text-[10px] text-stone-400 line-through cart-item-old-price ${hasOld ? '' : 'hidden'}">${hasOld ? formatMoney(parseFloat(item.old_price) * item.qty) : ''}</span>
                                <span class="text-xs font-bold cart-item-price">${formatMoney(item.subtotal)}</span>
                            </div>`;

                return `<div class="cart-item flex gap-3 py-3" data-size-id="${escapeHtml(item.size_id)}" data-price="${escapeHtml(item.price || '')}" data-old-price="${escapeHtml(item.old_price || '')}">
                    <div class="w-15 h-15 shrink-0 rounded-lg overflow-hidden bg-stone-50${item.unavailable_label ? ' opacity-50' : ''}">
                        <img src="${escapeHtml(item.image_url || window.DRJOYS?.placeholderUrl || '')}" class="w-full h-full object-cover" alt="${escapeHtml(item.name)}" loading="lazy">
                    </div>
                    <div class="flex-1 min-w-0">
                        <p class="text-xs font-bold truncate${item.unavailable_label ? ' text-stone-500' : ''}">${escapeHtml(item.name)}</p>
                        <p class="text-[10px] text-gray-500">${escapeHtml(item.size_name)}</p>
                        <div class="flex items-center justify-between mt-1">
                            ${bottomRow}
                        </div>
                    </div>
                </div>`;
            }).join('');
        }

        // Недоступные позиции: «Итого» без них уже посчитал сервер; ряд итога
        // прячем, когда доступных нет вовсе («Итого 0 ₸» показывать нельзя),
        // оформление блокируем, пока покупатель их не удалит
        const hasUnavailable = items.some(i => i.unavailable_label);
        const hasAvailable = items.some(i => !i.unavailable_label);
        const totalRowEl = document.getElementById('cartTotalRow');
        const hintEl = document.getElementById('cartUnavailableHint');
        const checkoutBtnEl = document.getElementById('cartCheckoutBtn');
        if (totalRowEl) totalRowEl.classList.toggle('hidden', !hasAvailable);
        if (hintEl) hintEl.classList.toggle('hidden', !hasUnavailable);
        if (checkoutBtnEl) checkoutBtnEl.disabled = hasUnavailable;

        // Totals: одна строка — одна величина (скидка / итог / списание в ₸),
        // ₸ юридически обязателен и стоит подписанной строкой, а не скобками
        const total = parseFloat(cartData.cart_total);
        const oldTotal = parseFloat(cartData.cart_old_total);
        const cartTotalEl = document.getElementById('cartTotal');
        const cartOldTotalEl = document.getElementById('cartOldTotal');
        const cartSavingsEl = document.getElementById('cartSavings');
        const discountRowEl = document.getElementById('cartDiscountRow');
        const paymentRowEl = document.getElementById('cartPaymentRow');
        const paymentTotalEl = document.getElementById('cartPaymentTotal');

        if (cartTotalEl) cartTotalEl.textContent = formatMoney(total);

        const showPay = needsConv && cartData.payment_total;
        if (paymentRowEl) paymentRowEl.classList.toggle('hidden', !showPay);
        if (showPay && paymentTotalEl) {
            paymentTotalEl.textContent = formatPayment(parseFloat(cartData.payment_total));
        }

        const savings = oldTotal - total;
        if (discountRowEl) discountRowEl.classList.toggle('hidden', !(savings > 0));
        if (savings > 0 && cartOldTotalEl && cartSavingsEl) {
            cartOldTotalEl.textContent = formatMoney(oldTotal);
            cartSavingsEl.textContent = '-' + Math.round((savings / oldTotal) * 100) + '%';
        }
    }

    async function loadCart() {
        const seq = ++reqSeq;
        try {
            const resp = await fetch('/orders/cart/');
            const data = await resp.json();
            if (seq !== reqSeq) return; // устаревший ответ — уже ушёл более новый запрос
            cartData = data;
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
        // У недоступной позиции счётчика нет — там возможен только remove
        const qtyEl = item.querySelector('.cart-item-qty');
        let qty = qtyEl ? (parseInt(qtyEl.textContent) || 1) : 1;

        // Бэкенд возвращает полную корзину — рендерим из ответа, без второго GET;
        // ответ обогнанного запроса молча выбрасывается (см. reqSeq)
        function applyCart(result, seq) {
            if (seq !== reqSeq) return;
            if (!result || !result.ok) return;
            cartData = result;
            renderCart();
            updateBadges(result.cart_count, null);
        }

        const seq = ++reqSeq;
        if (btn.dataset.action === 'remove') {
            try {
                applyCart(await apiPost('/orders/cart/remove/', { size_id: sizeId }), seq);
            } catch (err) {
                console.error('cart remove error:', err);
                loadCart();
            }
            return;
        }
        if (btn.dataset.action === 'minus' && qty > 1) {
            qty -= 1;
        } else if (btn.dataset.action === 'plus' && qty < 99) {
            qty += 1;
        }
        qtyEl.textContent = qty; // оптимистично, ответ сервера поправит
        try {
            applyCart(await apiPost('/orders/cart/update/', { size_id: sizeId, qty }), seq);
        } catch (err) {
            // Оптимистичное qty уже в DOM — перечитываем серверное состояние
            console.error('cart update error:', err);
            loadCart();
        }
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
