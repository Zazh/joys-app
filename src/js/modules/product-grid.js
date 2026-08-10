// --------------------------------------------
// 2. ДИНАМИЧЕСКИЙ GAP ДЛЯ СЕТКИ КАРТОЧЕК
// --------------------------------------------
function updateProductGridGap() {
    const referenceCol = document.getElementById('referenceCol');
    const productGrid = document.getElementById('productGrid');

    // Проверяем что элементы существуют
    if (!referenceCol || !productGrid) return;

    // Медиа-запрос для xl брейкпоинта (1280px в Tailwind)
    const isXlOrLarger = window.matchMedia('(min-width: 1280px)');

    // Если экран меньше xl - используем классовые gap
    if (!isXlOrLarger.matches) {
        productGrid.style.gap = '';
        return;
    }

    // Проверяем что эталонная колонка не скрыта
    if (referenceCol.classList.contains('hidden')) {
        // Убираем inline style, чтобы работали классовые gap
        productGrid.style.gap = '';
        return;
    }

    // Получаем ширину эталонной колонки
    const colWidth = referenceCol.offsetWidth;

    // Применяем как gap ТОЛЬКО на xl+
    productGrid.style.gap = `${colWidth}px`;
}

export function initProductGridGap() {
    // Вызываем при загрузке
    window.addEventListener('load', updateProductGridGap);

    // Вызываем при изменении размера окна с debounce
    let resizeTimer;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(updateProductGridGap, 100);
    });
}
