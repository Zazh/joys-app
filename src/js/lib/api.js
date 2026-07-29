import { getCSRFToken } from './csrf.js';

// POST JSON на наши эндпоинты. Общий для main.js, contacts.js и inline-скриптов
// шаблонов (window.apiPost) — иначе блок заголовков размножается по копиям
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
    return resp.json();
}
