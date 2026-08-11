import { apiPost } from '../lib/api.js';
import { openModal, closeModal } from '../lib/modal-core.js';
import { updateBadges } from '../lib/badges.js';

// --------------------------------------------
// 12. ORDER QUANTITY — счётчик + цена (API-aware)
// --------------------------------------------
export function initOrderQuantity() {
    const qtyMinus = document.getElementById('qtyMinus');
    const qtyPlus = document.getElementById('qtyPlus');
    const qtyValue = document.getElementById('qtyValue');

    if (!qtyMinus || !qtyPlus || !qtyValue) return;

    qtyMinus.addEventListener('click', () => {
        let val = parseInt(qtyValue.textContent) || 1;
        if (val > 1) {
            qtyValue.textContent = val - 1;
            updateOrderTotal();
        }
    });

    qtyPlus.addEventListener('click', () => {
        let val = parseInt(qtyValue.textContent) || 1;
        if (val < 99) {
            qtyValue.textContent = val + 1;
            updateOrderTotal();
        }
    });

    // Add to cart button → API
    const addToCartBtn = document.getElementById('addToCartBtn');
    if (addToCartBtn) {
        addToCartBtn.addEventListener('click', async () => {
            const sizeId = addToCartBtn.dataset.sizeId;
            const qty = parseInt(qtyValue.textContent) || 1;
            if (!sizeId) return;
            addToCartBtn.disabled = true;
            const result = await apiPost('/orders/cart/add/', { size_id: parseInt(sizeId), qty });
            addToCartBtn.disabled = false;
            if (result.ok) {
                updateBadges(result.cart_count, null);
                closeModal(document.getElementById('modalOrderQuantity'));
                // Открыть корзину
                const cartModal = document.getElementById('modalCart');
                if (cartModal) openModal(cartModal);
            }
        });
    }

    // Go to checkout page
    const goToDeliveryBtn = document.getElementById('goToDeliveryBtn');
    if (goToDeliveryBtn) {
        goToDeliveryBtn.addEventListener('click', async () => {
            // Сначала кладём выбранный размер в корзину — иначе checkout
            // увидит пустую корзину и средиректит обратно в каталог
            const sizeId = addToCartBtn ? addToCartBtn.dataset.sizeId : '';
            if (sizeId) {
                const qty = parseInt(qtyValue.textContent) || 1;
                goToDeliveryBtn.disabled = true;
                const result = await apiPost('/orders/cart/add/', { size_id: parseInt(sizeId), qty });
                goToDeliveryBtn.disabled = false;
                if (!result.ok) return;
                updateBadges(result.cart_count, null);
            }
            closeModal(document.getElementById('modalOrderQuantity'));
            window.location.href = '/orders/checkout/';
        });
    }
}

// data-price заполняет modules/product-buy.js (выбор размера), туда же пишется
// #addToCartBtn[data-size-id]. Повторная нормализация ниже сегодня холостая —
// оставлена страховкой на случай второго писателя атрибута
function updateOrderTotal() {
    const qtyValue = document.getElementById('qtyValue');
    const totalEl = document.getElementById('orderTotalPrice');
    const unitEl = document.getElementById('orderUnitPrice');
    if (!qtyValue || !totalEl || !unitEl) return;

    // data-price хранит чистое число (без пробелов/валюты)
    const priceStr = (unitEl.dataset.price || '0').replace(/\s/g, '').replace(',', '.');
    const unitPrice = parseFloat(priceStr) || 0;
    const qty = parseInt(qtyValue.textContent) || 1;
    const total = unitPrice * qty;
    const sym = window.DRJOYS?.currencySymbol || '₸';
    totalEl.textContent = total.toLocaleString('ru-RU') + ' ' + sym;
}
