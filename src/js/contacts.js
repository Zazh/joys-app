// ============================================
// CONTACTS.JS — карта офиса на странице контактов
// Отдельная точка входа: Leaflet не попадает в main.js и не грузится на других страницах
// ============================================
import L from 'leaflet';
import { addBrandTiles, brandPinIcon } from './lib/brand-map.js';
import { initInquiryForm } from './lib/inquiry-form.js';

function onReady(fn) {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', fn);
    } else {
        fn();
    }
}

// Содержимое попапа лежит в <template> шаблона: адрес, часы и иконки маршрутов
// остаются в Django (переводы, {% include %} иконок), JS их только клонирует
function buildPopup(container) {
    const template = document.getElementById('officeMapPopup');
    // Клонируем именно элемент, а не DocumentFragment: appendChild опустошает
    // фрагмент, и попап открылся бы пустым на второй раз
    if (template?.content.firstElementChild) {
        return template.content.firstElementChild.cloneNode(true);
    }

    // Шаблона нет — минимальный попап из data-атрибутов
    const wrap = document.createElement('div');
    wrap.className = 'map-popup';

    const name = document.createElement('strong');
    name.className = 'map-popup__name';
    name.textContent = container.dataset.title || '';
    wrap.appendChild(name);

    const address = document.createElement('span');
    address.className = 'map-popup__address';
    address.textContent = container.dataset.address || '';
    wrap.appendChild(address);

    return wrap;
}

function createMap(container) {
    const lat = parseFloat(container.dataset.lat);
    const lng = parseFloat(container.dataset.lng);
    if (Number.isNaN(lat) || Number.isNaN(lng)) return;

    // Фолбэк (адрес + ссылки на внешние карты) нужен только пока карты нет
    container.innerHTML = '';

    const map = L.map(container, {
        center: [lat, lng],
        zoom: 16,
        // Страница скроллится над картой; колёсико включается кликом (см. ниже)
        scrollWheelZoom: false,
        // На мобильном перетаскивание карты не должно красть скролл страницы —
        // маршрут там всё равно строят кнопками 2ГИС/Яндекс/Google
        dragging: !L.Browser.mobile,
        // Атрибуция — статичная строка под картой в шаблоне (.map-attribution),
        // не контрол Leaflet поверх тайлов (см. комментарий в lib/brand-map.js)
        attributionControl: false,
    });

    addBrandTiles(map);

    const marker = L.marker([lat, lng], {
        icon: brandPinIcon(),
        title: container.dataset.title || '',
        alt: container.dataset.title || '',
    }).addTo(map);

    marker.bindPopup(buildPopup(container), { minWidth: 240, maxWidth: 300 });

    // Часы и маршруты живут в попапе, поэтому на десктопе открываем его сразу —
    // иначе о них никто не узнает. На мобильном попап закрыл бы карту целиком
    if (window.matchMedia('(min-width: 1024px)').matches) marker.openPopup();

    // Зум колёсиком — только после клика по карте, до курсора вне карты
    map.on('click', () => map.scrollWheelZoom.enable());
    map.on('mouseout', () => map.scrollWheelZoom.disable());
}

// Ленивая инициализация: тайлы грузятся, когда карта подошла к вьюпорту
function initOfficeMap() {
    const container = document.getElementById('officeMap');
    if (!container) return;

    if (!('IntersectionObserver' in window)) {
        createMap(container);
        return;
    }

    const observer = new IntersectionObserver((entries) => {
        if (entries.some(entry => entry.isIntersecting)) {
            observer.disconnect();
            createMap(container);
        }
    }, { rootMargin: '300px' });

    observer.observe(container);
}

// ============================================
// ФОРМА ОБРАЩЕНИЯ — отправка на inquiries API без перезагрузки страницы
// ============================================

function initContactForm() {
    const form = document.getElementById('contactForm');
    if (!form) return;

    const consent = document.getElementById('contactConsent');
    const successBox = document.getElementById('contactFormSuccess');

    // Ссылка на политику лежит внутри <label>: без этого клик по ней
    // заодно переключал бы чекбокс согласия
    form.querySelectorAll('.form-consent a').forEach(link => {
        link.addEventListener('click', e => e.stopPropagation());
    });

    initInquiryForm(form, {
        // Согласие проверяем на клиенте: в заявке оно не сохраняется
        validate: () => (consent && !consent.checked
            ? { key: 'consent', message: form.dataset.errorConsent }
            : null),
        // Успех вместо формы: показываем блок, потом пишем текст и уводим фокус
        onSuccess: (result) => {
            form.classList.add('hidden');
            successBox.classList.remove('hidden');
            document.getElementById('contactSuccessTitle').textContent = result.success_title || '';
            document.getElementById('contactSuccessText').textContent = result.success_text || '';
            successBox.focus();
        },
    });
}

onReady(() => {
    initOfficeMap();
    initContactForm();
});
