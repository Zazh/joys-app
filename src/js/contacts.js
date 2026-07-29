// ============================================
// CONTACTS.JS — скрипты страницы контактов
// Подключается только в pages/contacts.html (defer)
// ============================================

// --------------------------------------------
// 1. КОПИРОВАНИЕ РЕКВИЗИТОВ
// --------------------------------------------

const TOAST_TIMEOUT = 2000;

// Clipboard API доступен не везде (http, старые браузеры, отказ в разрешении) —
// на этот случай остаётся textarea + execCommand, а если и он не сработал,
// значение выделяется в самой странице, чтобы скопировать вручную.
async function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (e) {
            // падаем в легаси-путь ниже
        }
    }
    return legacyCopy(text);
}

function legacyCopy(text) {
    const area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');       // не поднимает клавиатуру на мобильном
    area.style.cssText = 'position:fixed;top:0;left:0;opacity:0;';
    document.body.appendChild(area);

    const selection = document.getSelection();
    const prevRange = selection && selection.rangeCount ? selection.getRangeAt(0) : null;

    area.select();
    area.setSelectionRange(0, text.length);  // iOS игнорирует select() у readonly

    let copied = false;
    try {
        copied = document.execCommand('copy');
    } catch (e) {
        copied = false;
    }

    area.remove();
    if (prevRange && selection) {
        selection.removeAllRanges();
        selection.addRange(prevRange);
    }
    return copied;
}

// Выделяем значение на странице — последний шанс скопировать вручную
function selectNode(node) {
    const selection = document.getSelection();
    if (!node || !selection) return;
    const range = document.createRange();
    range.selectNodeContents(node);
    selection.removeAllRanges();
    selection.addRange(range);
}

function initRequisites() {
    const list = document.querySelector('[data-requisites]');
    if (!list) return;

    const toast = document.querySelector('[data-copy-toast]');
    let toastTimer = null;

    function showToast(ok) {
        if (!toast) return;
        clearTimeout(toastTimer);
        // Текст ставим каждый раз заново: смена содержимого live-региона —
        // то, что реально озвучивает скринридер (одна смена класса — нет)
        toast.textContent = ok
            ? toast.dataset.messageSuccess
            : toast.dataset.messageError;
        toast.classList.add('is-visible');
        toastTimer = setTimeout(() => {
            toast.classList.remove('is-visible');
            toast.textContent = '';
        }, TOAST_TIMEOUT);
    }

    async function copyAndReport(text, fallbackNode) {
        const ok = await copyText(text);
        if (!ok) selectNode(fallbackNode);
        showToast(ok);
    }

    // Одна кнопка — одно значение из своего <dd>
    list.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-copy]');
        if (!btn) return;
        const valueNode = btn.closest('dd')?.querySelector('[data-copy-value]');
        const text = valueNode?.textContent.trim();
        if (!text) return;
        copyAndReport(text, valueNode);
    });

    // «Скопировать все реквизиты» — собираем из самой разметки, чтобы
    // текст не разъезжался с таблицей и переводился вместе с ней
    const copyAllBtn = list.parentElement.querySelector('[data-copy-all]');
    copyAllBtn?.addEventListener('click', () => {
        const lines = [];
        list.querySelectorAll('dd').forEach((dd) => {
            const label = dd.previousElementSibling?.textContent.trim();   // <dt>
            const value = dd.querySelector('[data-copy-value]')?.textContent.trim();
            if (label && value) lines.push(`${label}: ${value}`);
        });
        if (lines.length) copyAndReport(lines.join('\n'), list);
    });
}

// Скрипт подключён с defer — разметка уже разобрана, ждать DOMContentLoaded незачем
initRequisites();
