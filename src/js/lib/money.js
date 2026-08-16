// Единственное место форматирования «число → строка с валютой» (SB-06).
// Дефолты символов читаются в момент вызова, не на импорте — привычка
// модулей: window.DRJOYS объявляется в base.html до бандла, но полагаться
// на порядок не надо. Не для product-buy.js: там цены — строки,
// отформатированные сервером (parseFloat('8 990') = 8).
export function formatMoney(value, symbol = window.DRJOYS?.currencySymbol || '₸') {
    return parseFloat(value).toLocaleString('ru-RU') + ' ' + symbol;
}

export function formatPayment(value) {
    return formatMoney(value, window.DRJOYS?.paymentCurrencySymbol || '');
}
