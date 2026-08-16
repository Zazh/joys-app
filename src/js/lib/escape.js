// Экранирование значений API перед подстановкой в innerHTML: имя товара,
// адрес и т.п. правятся людьми — разметка в них должна печататься текстом,
// а не исполняться (сохранённый XSS). Экранировать и атрибуты, и текст.
export function escapeHtml(value) {
    if (value == null) return '';
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
