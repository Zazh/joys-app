// Экранирование значений API перед подстановкой в innerHTML: имя товара,
// адрес и т.п. правятся людьми — разметка в них должна печататься текстом,
// а не исполняться (сохранённый XSS). Экранировать и атрибуты, и текст.
// Экранировать только СЫРЫЕ строки (из JSON API): значения window.DRJOYS и
// i18n уже HTML-экранированы Django-шаблоном при рендере base.html —
// повторный escapeHtml напечатал бы &amp; текстом.
export function escapeHtml(value) {
    if (value == null) return '';
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
