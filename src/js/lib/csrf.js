// Общий для main.js и contacts.js: обе точки входа шлют POST на наши API.
// Лежит в подпапке — esbuild собирает только src/js/*.js, отдельным бандлом не станет
export function getCSRFToken() {
    // Кука свежее токена из шаблона: страница могла провисеть открытой,
    // пока сессия (а с ней и токен) сменилась
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : (window.DRJOYS?.csrfToken || '');
}
