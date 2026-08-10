// Инициализация после построения DOM — не ждём загрузки картинок и шрифтов
// (window 'load' оставлен только там, где меряются размеры картинок)
export function onReady(fn) {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', fn);
    } else {
        fn();
    }
}
