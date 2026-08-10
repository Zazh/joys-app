// ============================================
// STORES.JS — оффлайн-точки на странице /partners/:
// карта с кластерами городов, чипы-фильтры, сплит список+карта,
// геолокация «Рядом со мной». Отдельная точка входа: Leaflet
// не попадает в main.js и не грузится на других страницах.
// ============================================
import L from 'leaflet';
import { addBrandTiles, brandPinIcon } from './lib/brand-map.js';
import { onReady } from './lib/on-ready.js';

// На этом зуме и мельче вместо пинов — кластеры городов: полсотни пинов
// на карте всей страны слипаются в кашу над Алматы
const CLUSTER_MAX_ZOOM = 9;
// Крупнее города при подгонке под его точки не приближаемся
const CITY_FOCUS_MAX_ZOOM = 14;
// Ближайшая точка не дальше этого — считаем, что юзер в её городе,
// и включаем чип города вместо «Все»
const NEAR_CITY_KM = 30;

const isDesktop = () => window.matchMedia('(min-width: 1024px)').matches;

// Расстояние по сфере в километрах — для «рядом со мной» точности хватает
function haversineKm(aLat, aLng, bLat, bLng) {
    const rad = Math.PI / 180;
    const dLat = (bLat - aLat) * rad;
    const dLng = (bLng - aLng) * rad;
    const h = Math.sin(dLat / 2) ** 2
        + Math.cos(aLat * rad) * Math.cos(bLat * rad) * Math.sin(dLng / 2) ** 2;
    return 12742 * Math.asin(Math.sqrt(h)); // 2R = 12742 км
}

function initStores() {
    const dataEl = document.getElementById('storesData');
    const container = document.getElementById('storesMap');
    if (!dataEl || !container) return;

    const stores = JSON.parse(dataEl.textContent);
    const located = stores.filter(s => s.lat != null && s.lng != null);
    if (!located.length) return;

    const layout = document.getElementById('storesLayout');
    const list = document.getElementById('storesList');
    const chips = [...document.querySelectorAll('.stores-chip')];
    const cards = new Map(
        [...list.querySelectorAll('.store-card')].map(card => [Number(card.dataset.storeId), card]),
    );
    const lang = document.documentElement.lang || 'ru';

    let map = null;
    const markers = new Map(); // store.id → L.Marker
    let clustersLayer = null;
    let pinsShown = false;
    let userMarker = null;
    let activeCity = 'all';
    let activeStoreId = null;

    const visibleLocated = () =>
        located.filter(s => activeCity === 'all' || s.city === activeCity);

    // --------------------------------------------
    // Попап пина: клонируем <template> из шаблона — тексты и иконки живут в Django
    // --------------------------------------------
    function buildPopup(store) {
        const template = document.getElementById('storePopupTemplate');
        const node = template.content.firstElementChild.cloneNode(true);
        node.querySelector('[data-popup-name]').textContent = store.name;
        node.querySelector('[data-popup-address]').textContent = store.address;
        if (store.pickupOnly) node.querySelector('[data-popup-pickup]').hidden = false;

        const gis = node.querySelector('[data-route-2gis]');
        if (store.url) gis.href = store.url; else gis.remove();
        node.querySelector('[data-route-yandex]').href =
            `https://yandex.ru/maps/?rtext=~${store.lat},${store.lng}&rtt=auto&z=16`;
        node.querySelector('[data-route-google]').href =
            `https://www.google.com/maps/dir/?api=1&destination=${store.lat},${store.lng}`;
        return node;
    }

    // --------------------------------------------
    // Активная точка: рамка на карточке + увеличенный пин, в обе стороны
    // (клик по карточке ↔ клик по пину, как список и карта в Airbnb)
    // --------------------------------------------
    function clearActiveStore() {
        if (activeStoreId === null) return;
        cards.get(activeStoreId)?.classList.remove('is-active');
        const marker = markers.get(activeStoreId);
        marker?.getElement()?.querySelector('.map-pin')?.classList.remove('is-active');
        marker?.setZIndexOffset(0);
        activeStoreId = null;
    }

    function setActiveStore(store, { scrollCard = false, pan = false } = {}) {
        clearActiveStore();
        activeStoreId = store.id;
        const card = cards.get(store.id);
        card?.classList.add('is-active');
        const marker = markers.get(store.id);
        if (!marker) return;

        // Пин мог быть скрыт кластерами: элемент появляется только после
        // приближения (syncLayers на zoomend), поэтому подсветка повторяется
        // перед открытием попапа
        const highlight = () => {
            marker.setZIndexOffset(1000);
            marker.getElement()?.querySelector('.map-pin')?.classList.add('is-active');
        };
        highlight();

        if (pan) {
            const target = L.latLng(store.lat, store.lng);
            const zoom = Math.max(map.getZoom(), 15);
            if (map.getCenter().distanceTo(target) < 1 && map.getZoom() === zoom) {
                marker.openPopup();
            } else {
                // Попап — после перелёта: его autoPan дёргал бы карту во время анимации
                map.once('moveend', () => {
                    highlight();
                    marker.openPopup();
                });
                map.flyTo(target, zoom, { duration: 0.6 });
            }
        } else {
            marker.openPopup();
        }
        if (scrollCard && card && isDesktop()) {
            card.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }
    }

    // --------------------------------------------
    // Карта: пины по точкам + кластеры городов на дальнем зуме
    // --------------------------------------------
    function buildClusters() {
        const byCity = new Map();
        for (const store of located) {
            if (!byCity.has(store.city)) byCity.set(store.city, []);
            byCity.get(store.city).push(store);
        }
        const clusterMarkers = [];
        for (const [city, cityStores] of byCity) {
            const lat = cityStores.reduce((sum, s) => sum + s.lat, 0) / cityStores.length;
            const lng = cityStores.reduce((sum, s) => sum + s.lng, 0) / cityStores.length;
            const marker = L.marker([lat, lng], {
                icon: L.divIcon({
                    className: 'map-cluster-icon',
                    html: `<span class="map-cluster">${cityStores.length}</span>`,
                    iconSize: [44, 44],
                    iconAnchor: [22, 22],
                }),
                title: city,
                alt: city,
            });
            marker.bindTooltip(city, { direction: 'top', offset: [0, -14] });
            // Клик по кластеру — приблизиться к городу; фильтр-чип не трогаем:
            // изучение карты не должно резать список
            marker.on('click', () => fitStores(cityStores));
            clusterMarkers.push(marker);
        }
        return L.layerGroup(clusterMarkers);
    }

    // Что показывать на текущем зуме: кластеры городов или пины.
    // При выбранном городе кластеры не нужны — точек мало, пины всегда
    function syncLayers() {
        const clustersMode = activeCity === 'all' && map.getZoom() <= CLUSTER_MAX_ZOOM;
        if (clustersMode) {
            if (pinsShown) {
                markers.forEach(marker => marker.remove());
                pinsShown = false;
            }
            if (!map.hasLayer(clustersLayer)) clustersLayer.addTo(map);
            return;
        }
        if (map.hasLayer(clustersLayer)) clustersLayer.remove();
        markers.forEach((marker, id) => {
            const store = located.find(s => s.id === id);
            const show = activeCity === 'all' || store.city === activeCity;
            if (show && !map.hasLayer(marker)) marker.addTo(map);
            if (!show && map.hasLayer(marker)) marker.remove();
        });
        pinsShown = true;
    }

    function fitStores(cityStores, extraPoint = null) {
        const points = cityStores.map(s => [s.lat, s.lng]);
        if (extraPoint) points.push(extraPoint);
        map.fitBounds(L.latLngBounds(points), {
            padding: [48, 48],
            maxZoom: cityStores.length > 1 ? CITY_FOCUS_MAX_ZOOM : 15,
        });
    }

    function createMap() {
        if (map) return;
        container.innerHTML = '';
        map = L.map(container, {
            // Страница скроллится над картой; колёсико включается кликом (см. ниже).
            // Перетаскивание включено и на мобильном: в отличие от контактов
            // с одним офисом, по карте точек нужно ходить
            scrollWheelZoom: false,
            attributionControl: false,
        });
        addBrandTiles(map);

        for (const store of located) {
            const marker = L.marker([store.lat, store.lng], {
                icon: brandPinIcon(),
                title: `${store.name} — ${store.address}`,
                alt: `${store.name} — ${store.address}`,
            });
            marker.bindPopup(() => buildPopup(store), { minWidth: 240, maxWidth: 300 });
            marker.on('click', () => setActiveStore(store, { scrollCard: true }));
            // Проверка нужна: openPopup новой точки сначала закрывает попап
            // старой, и без неё этот popupclose сбрасывал бы свежую подсветку
            marker.on('popupclose', () => {
                if (activeStoreId === store.id) clearActiveStore();
            });
            markers.set(store.id, marker);
        }
        clustersLayer = buildClusters();

        map.on('zoomend', syncLayers);
        // Зум колёсиком — только после клика по карте, до курсора вне карты
        map.on('click', () => map.scrollWheelZoom.enable());
        map.on('mouseout', () => map.scrollWheelZoom.disable());

        fitStores(visibleLocated());
        syncLayers();
    }

    // Ленивая инициализация: тайлы грузятся, когда карта подошла к вьюпорту.
    // На мобильном контейнер скрыт — observer сработает при первом переключении
    // на карту, отдельная ветка не нужна
    if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries) => {
            if (entries.some(entry => entry.isIntersecting)) {
                observer.disconnect();
                createMap();
            }
        }, { rootMargin: '300px' });
        observer.observe(container);
    } else {
        createMap();
    }

    // --------------------------------------------
    // Чипы городов: фильтруют и список, и карту
    // --------------------------------------------
    function setCity(city) {
        activeCity = city;
        for (const chip of chips) {
            const active = chip.dataset.city === city;
            chip.classList.toggle('is-active', active);
            chip.setAttribute('aria-pressed', String(active));
        }
        for (const section of list.querySelectorAll('[data-city-group]')) {
            section.hidden = city !== 'all' && section.dataset.cityGroup !== city;
        }
        if (map) {
            map.closePopup();
            clearActiveStore();
            const visible = visibleLocated();
            if (visible.length) fitStores(visible);
            syncLayers();
        }
    }

    for (const chip of chips) {
        chip.addEventListener('click', () => setCity(chip.dataset.city));
    }

    // --------------------------------------------
    // Карточки: кнопка «На карте» (на мобильном сперва переключает вид),
    // на десктопе точку фокусирует клик по любому месту карточки
    // --------------------------------------------
    list.addEventListener('click', (e) => {
        const card = e.target.closest('.store-card');
        if (!card || e.target.closest('a')) return;
        const focusBtn = e.target.closest('[data-map-focus]');
        if (!focusBtn && !isDesktop()) return;
        const store = located.find(s => s.id === Number(card.dataset.storeId));
        if (!store) return;
        if (!isDesktop()) switchView(true);
        createMap();
        setActiveStore(store, { pan: true });
    });

    // --------------------------------------------
    // Мобильный переключатель Карта/Список
    // --------------------------------------------
    const toggle = document.getElementById('storesViewToggle');

    function switchView(toMap) {
        layout.classList.toggle('stores-view--map', toMap);
        // Карта раскрывается фиксированным слоем на весь экран — страница под
        // ней не должна скроллиться (тот же приём, что у модалок)
        document.body.classList.toggle('overflow-hidden', toMap);
        toggle.setAttribute('aria-pressed', String(toMap));
        toggle.querySelector('[data-icon-map]').classList.toggle('hidden', toMap);
        toggle.querySelector('[data-toggle-label-map]').classList.toggle('hidden', toMap);
        toggle.querySelector('[data-icon-list]').classList.toggle('hidden', !toMap);
        toggle.querySelector('[data-toggle-label-list]').classList.toggle('hidden', !toMap);
        // Контейнер только что стал видимым — Leaflet о его размере не знает
        if (toMap && map) requestAnimationFrame(() => map.invalidateSize());
    }

    toggle.addEventListener('click', () => {
        switchView(!layout.classList.contains('stores-view--map'));
    });

    // Растянули окно до десктопа, не выйдя из карты, — возвращаем сплит,
    // иначе body остался бы заблокированным, а кнопка выхода спрятана (lg:hidden)
    window.matchMedia('(min-width: 1024px)').addEventListener('change', (e) => {
        if (e.matches) switchView(false);
    });

    // --------------------------------------------
    // «Рядом со мной»: только по клику (авто-запрос геолокации — антипаттерн).
    // Считаем расстояния, сортируем карточки, включаем чип ближайшего города
    // --------------------------------------------
    const nearBtn = document.getElementById('storesNearMe');
    const geoError = document.getElementById('storesGeoError');
    const labelKm = container.dataset.labelKm || 'км';
    const labelM = container.dataset.labelM || 'м';

    function formatDistance(km) {
        if (km < 0.95) return `${Math.max(10, Math.round(km * 100) * 10)} ${labelM}`;
        const digits = km < 10 ? 1 : 0;
        return `${km.toLocaleString(lang, { maximumFractionDigits: digits })} ${labelKm}`;
    }

    function applyDistances(userLat, userLng) {
        const distances = new Map();
        for (const store of located) {
            const km = haversineKm(userLat, userLng, store.lat, store.lng);
            distances.set(store.id, km);
            const span = cards.get(store.id)?.querySelector('[data-distance]');
            if (span) {
                span.textContent = ` · ${formatDistance(km)}`;
                span.hidden = false;
            }
        }

        // Ближние карточки — вверх внутри города, ближние города — вверх списка.
        // Точки без координат остаются в хвосте своих секций
        const sections = [...list.querySelectorAll('[data-city-group]')];
        const sectionMin = new Map();
        for (const section of sections) {
            const sectionCards = [...section.querySelectorAll('.store-card')];
            sectionCards.sort((a, b) =>
                (distances.get(Number(a.dataset.storeId)) ?? Infinity)
                - (distances.get(Number(b.dataset.storeId)) ?? Infinity));
            const grid = section.querySelector('.stores-cards');
            sectionCards.forEach(card => grid.appendChild(card));
            sectionMin.set(section, Math.min(
                ...sectionCards.map(card => distances.get(Number(card.dataset.storeId)) ?? Infinity),
            ));
        }
        sections
            .sort((a, b) => sectionMin.get(a) - sectionMin.get(b))
            .forEach(section => list.appendChild(section));

        return distances;
    }

    nearBtn.addEventListener('click', () => {
        if (!navigator.geolocation) {
            geoError.classList.remove('hidden');
            return;
        }
        navigator.geolocation.getCurrentPosition((pos) => {
            const { latitude: lat, longitude: lng } = pos.coords;
            geoError.classList.add('hidden');
            nearBtn.classList.add('is-active');
            createMap();

            if (userMarker) userMarker.remove();
            userMarker = L.marker([lat, lng], {
                icon: L.divIcon({
                    className: 'map-user-icon',
                    html: '<span class="map-user-dot"></span>',
                    iconSize: [16, 16],
                    iconAnchor: [8, 8],
                }),
                zIndexOffset: 500,
                interactive: false,
            }).addTo(map);

            const distances = applyDistances(lat, lng);
            const nearest = [...located].sort(
                (a, b) => distances.get(a.id) - distances.get(b.id),
            );
            // В городе — включаем его чип; в глуши между городами — «Все»
            setCity(distances.get(nearest[0].id) <= NEAR_CITY_KM ? nearest[0].city : 'all');
            fitStores(
                nearest.filter(s => activeCity === 'all' || s.city === activeCity).slice(0, 3),
                [lat, lng],
            );
        }, () => {
            geoError.classList.remove('hidden');
        }, { timeout: 10000, maximumAge: 300000 });
    });
}

onReady(initStores);
