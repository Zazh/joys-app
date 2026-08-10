// Обновить бейджи корзины и избранного в навигации
export function updateBadges(cartCount, favCount) {
    if (cartCount !== null && cartCount !== undefined) {
        document.querySelectorAll('[data-cart-count]').forEach(el => {
            el.textContent = cartCount;
            el.classList.toggle('hidden', cartCount === 0);
        });
    }
    if (favCount !== null && favCount !== undefined) {
        document.querySelectorAll('[data-fav-count]').forEach(el => {
            el.textContent = favCount;
            el.classList.toggle('hidden', favCount === 0);
        });
    }
}
