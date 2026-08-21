import { apiPost } from '../lib/api.js';
import { updateBadges } from '../lib/badges.js';
import { escapeHtml } from '../lib/escape.js';
import { formatMoney, formatPayment } from '../lib/money.js';

// --------------------------------------------
// 14. FAVORITES MODAL — загрузка из API, удаление
// --------------------------------------------
export function initFavoritesModal() {
    const favOverlay = document.getElementById('modalFavorites');
    if (!favOverlay) return;

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
            listEl.innerHTML = items.map(item => {
                // Ссылка на страницу товара (SB-08); пустой product_url — без ссылки
                const url = item.product_url ? escapeHtml(item.product_url) : '';
                const imgHtml = `<img src="${escapeHtml(item.image_url || window.DRJOYS?.placeholderUrl || '')}" class="w-full h-full object-cover" alt="${escapeHtml(item.name)}" loading="lazy">`;
                return `
                <div class="fav-item flex gap-3 p-2 rounded-xl bg-stone-50" data-product-id="${escapeHtml(item.product_id)}" data-first-size-id="${escapeHtml(item.first_size_id || '')}">
                    <div class="w-20 h-20 shrink-0 rounded-lg overflow-hidden bg-stone-50">
                        ${url ? `<a href="${url}">${imgHtml}</a>` : imgHtml}
                    </div>
                    <div class="flex-1 min-w-0 flex flex-col justify-between py-1">
                        <div>
                            <p class="text-xs font-bold leading-tight">${url ? `<a href="${url}">${escapeHtml(item.name)}</a>` : escapeHtml(item.name)}</p>
                            ${item.price ? `<p class="text-xs text-red-500 font-benzin mt-1">${formatMoney(item.price)}${item.payment_price ? ` <span class="text-stone-400 font-normal">(${formatPayment(item.payment_price)})</span>` : ''}</p>` : ''}
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
            `;
            }).join('');
        }
    }

    async function loadFavorites() {
        try {
            // /orders/ вне i18n_patterns — язык ответа задаёт заголовок (см. lib/api.js)
            const resp = await fetch('/orders/favorites/', {
                headers: { 'Accept-Language': document.documentElement.lang },
            });
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
            try {
                const result = await apiPost('/orders/favorites/remove/', { product_id: productId });
                if (result.ok) updateBadges(null, result.fav_count);
            } catch (err) {
                console.error('favorites remove error:', err);
            }
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
            try {
                const result = await apiPost('/orders/cart/add/', { size_id: parseInt(sizeId), qty: 1 });
                if (result.ok) {
                    updateBadges(result.cart_count, null);
                    cartBtn.textContent = '✓';
                    setTimeout(() => { cartBtn.textContent = window.DRJOYS.i18n.addToCart; }, 800);
                }
            } catch (err) {
                console.error('favorites add-to-cart error:', err);
            } finally {
                cartBtn.disabled = false;
            }
        }
    });
}
