import { apiPost } from '../lib/api.js';
import { openModal } from '../lib/modal-core.js';
import { updateBadges } from '../lib/badges.js';

// --------------------------------------------
// 11. PRODUCT BUY — размеры + добавление в корзину (API)
// --------------------------------------------
export function initProductBuy() {
    const sym = window.DRJOYS?.currencySymbol || '₸';
    let sizeSelected = false;
    let selectedSizeId = null;

    // --- Size dropdown (Lamoda-style) ---
    const dropdown = document.getElementById('sizeDropdown');
    const triggerBtn = document.getElementById('sizeDropdownBtn');
    const menu = document.getElementById('sizeMenu');
    const selectedName = document.getElementById('selectedSizeName');

    function openDropdown() {
        if (!menu || !dropdown) return;
        menu.classList.remove('hidden');
        dropdown.classList.add('open');
    }

    function closeDropdown() {
        if (!menu || !dropdown) return;
        menu.classList.add('hidden');
        dropdown.classList.remove('open');
    }

    function selectSize(item) {
        sizeSelected = true;
        selectedSizeId = parseInt(item.dataset.sizeId);

        // Update active state
        menu.querySelectorAll('.size-dropdown__item--active').forEach(el => el.classList.remove('size-dropdown__item--active'));
        item.classList.add('size-dropdown__item--active');

        // Update trigger: remove placeholder style, show size name
        triggerBtn.classList.remove('size-dropdown__trigger--placeholder');
        if (selectedName) selectedName.textContent = item.dataset.size;

        // Show & update SKU
        const skuBlock = document.getElementById('skuBlock');
        const skuEl = document.getElementById('productSku');
        if (skuBlock) skuBlock.classList.remove('hidden');
        if (skuEl) skuEl.textContent = item.dataset.sku;

        // Show & update price
        const priceRow = document.getElementById('priceRow');
        const priceCurrentEl = document.getElementById('priceCurrent');
        const priceOldEl = document.getElementById('priceOld');
        const priceDiscountEl = document.getElementById('priceDiscount');

        if (priceRow) priceRow.classList.remove('hidden');
        if (priceCurrentEl) priceCurrentEl.textContent = item.dataset.price + ' ' + sym;

        if (priceOldEl && priceDiscountEl) {
            if (item.dataset.oldPrice) {
                priceOldEl.textContent = item.dataset.oldPrice + ' ' + sym;
                priceDiscountEl.textContent = '-' + item.dataset.discount + '%';
                priceOldEl.classList.remove('hidden');
                priceDiscountEl.classList.remove('hidden');
            } else {
                priceOldEl.classList.add('hidden');
                priceDiscountEl.classList.add('hidden');
            }
        }

        // Двойная валюта (payment price)
        const pricePaymentEl = document.getElementById('pricePayment');
        if (pricePaymentEl) {
            const paymentPrice = item.dataset.paymentPrice;
            if (paymentPrice) {
                pricePaymentEl.textContent = '(' + paymentPrice + ' ' + (window.DRJOYS?.paymentCurrencySymbol || '') + ')';
                pricePaymentEl.classList.remove('hidden');
            } else {
                pricePaymentEl.classList.add('hidden');
            }
        }

        closeDropdown();
    }

    if (dropdown && triggerBtn && menu) {
        triggerBtn.addEventListener('click', () => {
            const isOpen = !menu.classList.contains('hidden');
            if (isOpen) closeDropdown();
            else openDropdown();
        });

        document.addEventListener('click', (e) => {
            const buyBtn = document.getElementById('buyAnonymousBtn');
            if (!dropdown.contains(e.target) && e.target !== buyBtn) closeDropdown();
        });

        menu.querySelectorAll('.size-dropdown__item:not(.size-dropdown__item--disabled)').forEach(item => {
            item.addEventListener('click', () => selectSize(item));
        });
    }

    // --- Buy button → open Order Quantity modal ---
    const buyBtn = document.getElementById('buyAnonymousBtn');

    if (buyBtn) {
        buyBtn.addEventListener('click', () => {
            if (!sizeSelected || !selectedSizeId) {
                openDropdown();
                return;
            }

            // Найти выбранный элемент размера
            const activeItem = menu ? menu.querySelector('.size-dropdown__item--active') : null;
            if (!activeItem) return;

            const productBuyEl = document.getElementById('productBuy');
            const productName = productBuyEl ? productBuyEl.dataset.productName : '';
            const sizeName = activeItem.dataset.size || '';
            const price = activeItem.dataset.price || '0';

            // Заполнить модалку Order Quantity
            const nameEl = document.getElementById('orderProductName');
            const sizeEl = document.getElementById('orderProductSize');
            const unitEl = document.getElementById('orderUnitPrice');
            const totalEl = document.getElementById('orderTotalPrice');
            const qtyEl = document.getElementById('qtyValue');
            const addBtn = document.getElementById('addToCartBtn');

            // Пишем DOM-контракт модалки количества: #orderUnitPrice[data-price]
            // (нормализованное число) и #addToCartBtn[data-size-id] — их читает
            // modules/order-quantity.js, импорта между модулями нет
            if (nameEl) nameEl.textContent = productName;
            if (sizeEl) sizeEl.textContent = sizeName;
            if (unitEl) {
                unitEl.dataset.price = price.replace(/\s/g, '').replace(',', '.');
                unitEl.textContent = price + ' ' + sym;
            }
            if (qtyEl) qtyEl.textContent = '1';
            if (totalEl) totalEl.textContent = price + ' ' + sym;
            if (addBtn) addBtn.dataset.sizeId = selectedSizeId;

            // Открыть модалку
            const modal = document.getElementById('modalOrderQuantity');
            if (modal) openModal(modal);
        });
    }

    // --- Favorite button toggle → API ---
    const favBtn = document.getElementById('productFavoriteBtn');
    const productBuy = document.getElementById('productBuy');
    const productId = productBuy ? productBuy.dataset.productId : null;

    if (favBtn && productId) {
        const favPath = favBtn.querySelector('svg path');
        favBtn.addEventListener('click', async () => {
            favBtn.disabled = true;
            const result = await apiPost('/orders/favorites/toggle/', { product_id: parseInt(productId) });
            favBtn.disabled = false;

            if (result.ok) {
                const isActive = result.added;
                favBtn.classList.toggle('active', isActive);
                if (favPath) favPath.setAttribute('fill', isActive ? 'currentColor' : 'none');
                updateBadges(null, result.fav_count);
            }
        });
    }
}
