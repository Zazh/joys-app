import { getCSRFToken } from './csrf.js';

// POST JSON на наши эндпоинты. Общий для main.js, contacts.js и inline-скриптов
// шаблонов (window.apiPost) — иначе блок заголовков размножается по копиям.
// Не-2xx с НЕ-JSON телом (HTML-страница ошибки nginx, CSRF-403) — исключение,
// как и сбой сети: вызывающий обязан ловить и разблокировать свои кнопки.
// JSON-ошибки (400/401 с ok:false и errors полей) отдаются как раньше —
// auth и формы заявок показывают по ним точные сообщения, не «сбой сети»
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
    if (!resp.ok && !(resp.headers.get('Content-Type') || '').includes('json')) {
        throw new Error('HTTP ' + resp.status);
    }
    return resp.json();
}
