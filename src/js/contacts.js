// ============================================
// CONTACTS.JS — карта офиса на странице контактов
// Отдельная точка входа: Leaflet не попадает в main.js и не грузится на других страницах
// ============================================
import L from 'leaflet';

// CARTO Positron — монохромные серые тайлы, {r} — ретина-версия из коробки.
// Атрибуция OSM + CARTO обязательна (условие бесплатного использования).
const TILE_URL = 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png';
const TILE_ATTRIBUTION =
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> ' +
    '&copy; <a href="https://carto.com/attributions">CARTO</a>';

// Брендовый пин: капля #E42521 с белым кружком, остриё ровно в точке [20, 48]
const PIN_HTML = `
<span class="map-pin">
    <svg width="40" height="48" viewBox="0 0 40 48" fill="none" aria-hidden="true">
        <path d="M20 48C20 48 35 30.5 35 17.5C35 9.2 28.3 2.5 20 2.5C11.7 2.5 5 9.2 5 17.5C5 30.5 20 48 20 48Z" fill="#E42521"/>
        <circle cx="20" cy="17.5" r="5.5" fill="#fff"/>
    </svg>
</span>`;

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
    if (template) return template.content.cloneNode(true);

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
    });

    L.tileLayer(TILE_URL, {
        attribution: TILE_ATTRIBUTION,
        maxZoom: 19,
        subdomains: 'abcd',
    }).addTo(map);

    const marker = L.marker([lat, lng], {
        icon: L.divIcon({
            className: 'map-pin-icon', // не 'leaflet-div-icon' — без белой подложки и рамки
            html: PIN_HTML,
            iconSize: [40, 48],
            iconAnchor: [20, 48],
            popupAnchor: [0, -44],
        }),
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

onReady(initOfficeMap);
