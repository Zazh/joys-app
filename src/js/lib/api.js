import { getCSRFToken } from './csrf.js';

// POST JSON на наши эндпоинты. Общий для main.js, contacts.js и inline-скриптов
// шаблонов (window.apiPost) — иначе блок заголовков размножается по копиям.
// Не-2xx (HTML-страница ошибки nginx, CSRF-403) — исключение, как и сбой сети:
// вызывающий обязан ловить и разблокировать свои кнопки
export async function apiPost(url, data) {
    const resp = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken(),
            // /api/ и /orders/ живут вне i18n_patterns: без этого заголовка ответы
            // приходят по-русски на казахской и английской версиях страницы
            'Accept-Language': document.documentElement.lang,
        },
        body: JSON.stringify(data),
    });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    return resp.json();
}
