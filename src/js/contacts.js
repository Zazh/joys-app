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

// Брендовый пин — знак из логотипа: щит #E42521 + белое сердце внутри.
// Пути взяты как есть из src/images/svgs/logo_small.svg (без ® рядом),
// viewBox обрезан по знаку — остриё щита приходится ровно в [20.6, 38]
const PIN_HTML = `
<span class="map-pin">
    <svg width="41" height="38" viewBox="160.718 0 40.43 38" fill="none" aria-hidden="true">
        <path d="M161.331 3.4931C163.089 3.17884 165.731 2.6985 168.94 2.08553C178.32 0.293213 178.817 -0.013871 181.126 0.000467538C183.534 0.016001 183.903 0.357736 192.837 2.08553C196.182 2.73316 198.931 3.22664 200.744 3.54448C200.837 4.31398 200.94 5.36667 200.981 6.6201C201.147 11.6625 200.169 15.4634 199.971 16.2114C198.312 22.451 194.844 26.8793 193.313 28.6692C188.978 33.7391 184.006 36.5793 181.067 38C178.086 36.547 173.361 33.7964 169.178 29.0348C167.765 27.4265 163.971 22.8071 162.104 15.8469C160.718 10.6791 160.946 6.28075 161.331 3.4931Z" fill="#E42521"/>
        <path d="M180.707 14.6557C181.339 11.825 183.187 9.63717 185.508 8.99074C188.921 8.04081 191.402 10.9647 191.62 11.2299C191.79 11.4378 194.13 14.3868 193.475 18.0802C192.885 21.4127 190.257 23.0903 189.437 23.6137C186.871 25.2518 180.656 28.4828 180.177 29.0456C179.632 28.1745 178.714 26.4491 177.65 25.1945C177.111 24.5588 175.903 23.1931 173.831 21.5059C170.024 18.4076 167.258 15.6378 168.89 10.4927C169.994 7.01441 174.453 5.82072 177.266 7.61901C180.235 9.51648 180.527 13.8348 180.706 14.6557H180.707Z" fill="#fff"/>
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
            iconSize: [41, 38],
            iconAnchor: [20.6, 38],
            popupAnchor: [0, -34],
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
