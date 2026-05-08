// ============================================
// MAIN.JS - Общие скрипты для всего сайта
// ============================================

// --------------------------------------------
// 0. УНИВЕРСАЛЬНЫЕ УТИЛИТЫ МОДАЛОК
// --------------------------------------------
function openModal(overlay) {
    if (!overlay) return;
    overlay.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    // Close burger menu if open
    if (window._closeMenu) window._closeMenu();
    // Dispatch custom event for modals that need to load data
    overlay.dispatchEvent(new CustomEvent('modal:open'));
}

function closeModal(overlay) {
    if (!overlay) return;
    overlay.classList.add('hidden');
    document.body.style.overflow = '';
    // Reset to step 1
    const steps = overlay.querySelectorAll('.modal-step');
    steps.forEach((step, i) => {
        step.classList.toggle('hidden', i !== 0);
    });
}

function goToStep(overlay, stepNum) {
    if (!overlay) return;
    overlay.querySelectorAll('.modal-step').forEach(step => {
        step.classList.toggle('hidden', step.dataset.step !== String(stepNum));
    });
}

// Глобальный доступ для inline-скриптов в шаблонах
window.openModal = openModal;
window.closeModal = closeModal;
window.goToStep = goToStep;

// --------------------------------------------
// 0.1 API HELPER
// --------------------------------------------
function getCSRFToken() {
    // Prefer cookie (always fresh after session change) over template-rendered token
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : (window.DRJOYS?.csrfToken || '');
}

async function apiPost(url, data) {
    const resp = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken(),
        },
        body: JSON.stringify(data),
    });
    return resp.json();
}

// Обновить бейджи корзины и избранного в навигации
function updateBadges(cartCount, favCount) {
    if (cartCount !== null && cartCount !== undefined) {
        document.querySelectorAll('[data-cart-count]').forEach(el => {
            el.textContent = cartCount;
            el.classList.toggle('hidden', cartCount === 0);
        });
    }
    if (favCount !== null && favCount !== undefined) {
        document.querySelectorAll('[data-fav-count]').forEach(el => {
            el.textContent = favCount;
            el.classList.toggle('hidden', favCount === 0);
        });
    }
}

// Phone mask — автоопределение длины кода страны
function initPhoneMasks() {
    document.querySelectorAll('input[type="tel"]').forEach(phoneInput => {
        if (phoneInput.dataset.maskInit) return;
        phoneInput.dataset.maskInit = '1';

        function formatPhone(digits) {
            if (!digits.length) return '';

            let codeLen = 1;
            if (digits.startsWith('7') || digits.startsWith('1')) codeLen = 1;
            else if (digits.startsWith('99')) codeLen = 3;
            else codeLen = 2;

            const code = digits.slice(0, codeLen);
            const rest = digits.slice(codeLen);

            let formatted = '+' + code;
            if (rest.length > 0) formatted += ' (' + rest.slice(0, 3);
            if (rest.length >= 3) formatted += ')';
            if (rest.length > 3) formatted += ' ' + rest.slice(3, 6);
            if (rest.length > 6) formatted += '-' + rest.slice(6, 8);
            if (rest.length > 8) formatted += '-' + rest.slice(8, 10);

            return formatted;
        }

        phoneInput.addEventListener('input', (e) => {
            let digits = e.target.value.replace(/\D/g, '');
            if (digits.length > 15) digits = digits.slice(0, 15);
            e.target.value = formatPhone(digits);
        });

        phoneInput.addEventListener('focus', () => {
            if (!phoneInput.value) phoneInput.value = '+';
        });

        phoneInput.addEventListener('blur', () => {
            if (phoneInput.value === '+') phoneInput.value = '';
        });

        phoneInput.addEventListener('keydown', (e) => {
            if (e.key === 'Backspace' && phoneInput.value.length <= 1) {
                phoneInput.value = '';
                e.preventDefault();
            }
        });
    });
}

// Escape key — закрывает все видимые модалки
document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    document.querySelectorAll('.modal-overlay:not(.hidden)').forEach(overlay => {
        closeModal(overlay);
    });
});

// Click on overlay background — закрывает модалку
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
        closeModal(e.target);
    }
});

// Click on .modal-close — закрывает ближайшую модалку
document.addEventListener('click', (e) => {
    const closeBtn = e.target.closest('.modal-close');
    if (!closeBtn) return;
    const overlay = closeBtn.closest('.modal-overlay');
    if (overlay) closeModal(overlay);
});

// Инициализация масок телефона при загрузке
window.addEventListener('load', initPhoneMasks);

// --------------------------------------------
// 1. БУРГЕР-МЕНЮ
// --------------------------------------------
function initMobileMenu() {
    const menuBtn = document.getElementById('menuBtn');
    const mainNav = document.getElementById('mainNav');
    const navWrapper = document.querySelector('.nav_wrapper');
    if (!menuBtn || !mainNav || !navWrapper) return;

    let isMenuActive = false;

    function openMenu() {
        isMenuActive = true;
        const lines = menuBtn.querySelectorAll('span');
        lines[0].style.opacity = '0';
        lines[1].style.transform = 'rotate(45deg)';
        lines[2].style.transform = 'rotate(-45deg)';
        lines[3].style.opacity = '0';

        mainNav.classList.remove('hidden');
        mainNav.classList.add('flex');
        navWrapper.classList.add('bottom-0');
        navWrapper.classList.add('bg-white/75', 'backdrop-blur-xl');
    }

    function closeMenu() {
        isMenuActive = false;
        const lines = menuBtn.querySelectorAll('span');
        lines[0].style.opacity = '1';
        lines[1].style.transform = 'rotate(0deg)';
        lines[2].style.transform = 'rotate(0deg)';
        lines[3].style.opacity = '1';

        mainNav.classList.add('hidden');
        mainNav.classList.remove('flex');
        navWrapper.classList.remove('bottom-0');
        navWrapper.classList.remove('bg-white/75', 'backdrop-blur-xl');
    }

    menuBtn.addEventListener('click', () => {
        if (isMenuActive) closeMenu();
        else openMenu();
    });

    // Click on dark area (nav_wrapper, outside mainNav) closes menu
    navWrapper.addEventListener('click', (e) => {
        if (isMenuActive && e.target === navWrapper) closeMenu();
    });

    // Expose closeMenu for use by modals
    window._closeMenu = closeMenu;
}

window.addEventListener('load', initMobileMenu);

// --------------------------------------------
// 2. ДИНАМИЧЕСКИЙ GAP ДЛЯ СЕТКИ КАРТОЧЕК
// --------------------------------------------
function updateProductGridGap() {
    const referenceCol = document.getElementById('referenceCol');
    const productGrid = document.getElementById('productGrid');

    // Проверяем что элементы существуют
    if (!referenceCol || !productGrid) return;

    // Медиа-запрос для xl брейкпоинта (1280px в Tailwind)
    const isXlOrLarger = window.matchMedia('(min-width: 1280px)');

    // Если экран меньше xl - используем классовые gap
    if (!isXlOrLarger.matches) {
        productGrid.style.gap = '';
        return;
    }

    // Проверяем что эталонная колонка не скрыта
    if (referenceCol.classList.contains('hidden')) {
        // Убираем inline style, чтобы работали классовые gap
        productGrid.style.gap = '';
        return;
    }

    // Получаем ширину эталонной колонки
    const colWidth = referenceCol.offsetWidth;

    // Применяем как gap ТОЛЬКО на xl+
    productGrid.style.gap = `${colWidth}px`;
}

// Вызываем при загрузке
window.addEventListener('load', updateProductGridGap);

// Вызываем при изменении размера окна с debounce
let resizeTimer;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(updateProductGridGap, 100);
});

// --------------------------------------------
// 3. ПЕРЕКЛЮЧЕНИЕ КАРТИНОК ТОВАРОВ
// --------------------------------------------
function initProductImageSlider() {
    const productCards = document.querySelectorAll('.product-card_picture');

    productCards.forEach(card => {
        const images = card.querySelectorAll('.product-image');
        const imagesCount = images.length;

        if (imagesCount === 0) return;
        if (imagesCount === 1) { images[0].classList.add('active'); return; }

        // Создаем индикаторы автоматически
        const indicatorsContainer = card.querySelector('.product-indicators');
        indicatorsContainer.innerHTML = ''; // Очищаем на всякий случай

        const indicators = [];
        for (let i = 0; i < imagesCount; i++) {
            const indicator = document.createElement('span');
            indicator.classList.add('indicator');
            indicatorsContainer.appendChild(indicator);
            indicators.push(indicator);
        }

        // Инициализация - показываем первую картинку и индикатор
        images[0].classList.add('active');
        indicators[0].classList.add('active');

        let currentIndex = 0;
        let touchStartX = 0;
        let touchEndX = 0;

        // Функция переключения картинки
        function showImage(index) {
            if (index === currentIndex) return;

            images.forEach(img => img.classList.remove('active'));
            indicators.forEach(ind => ind.classList.remove('active'));

            images[index].classList.add('active');
            indicators[index].classList.add('active');

            currentIndex = index;
        }

        // ==========================================
        // ДЕСКТОП: Движение курсора по зонам
        // ==========================================
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const sectionWidth = rect.width / imagesCount;
            const newIndex = Math.floor(x / sectionWidth);

            if (newIndex >= 0 && newIndex < imagesCount) {
                showImage(newIndex);
            }
        });

        card.addEventListener('mouseleave', () => {
            showImage(0);
        });

        // ==========================================
        // МОБИЛЬНЫЕ: Свайпы влево/вправо
        // ==========================================
        card.addEventListener('touchstart', (e) => {
            touchStartX = e.changedTouches[0].screenX;
        }, { passive: true });

        card.addEventListener('touchend', (e) => {
            touchEndX = e.changedTouches[0].screenX;
            handleSwipe();
        });

        function handleSwipe() {
            const swipeThreshold = 50;

            if (touchEndX < touchStartX - swipeThreshold) {
                const nextIndex = (currentIndex + 1) % imagesCount;
                showImage(nextIndex);
            }

            if (touchEndX > touchStartX + swipeThreshold) {
                const prevIndex = (currentIndex - 1 + imagesCount) % imagesCount;
                showImage(prevIndex);
            }
        }
    });
}

window.addEventListener('load', initProductImageSlider);

// --------------------------------------------
// 4. АНИМАЦИЯ БИЕНИЯ СЕРДЦА С КУЛЬМИНАЦИЕЙ
// --------------------------------------------
function initHeartbeat() {
    const heartElement = document.querySelector('.heart-beat');
    const dotElement = document.querySelector('.dot-shake');
    const triggers = document.querySelectorAll('.heart-trigger');

    if (!heartElement || triggers.length === 0) return;

    let hoverTimer = null;
    let scaleValue = 1;
    let shakeIntensity = 1;
    let isHovering = false;
    let animationFrame = null;

    // Функция обновления scale и shake intensity
    function updateScale() {
        if (!isHovering) return;

        const elapsed = Date.now() - hoverTimer;
        const totalDuration = 20000; // 20 секунд
        const progress = Math.min(elapsed / totalDuration, 1); // 0 → 1

        // Кривая нарастания:
        if (progress < 0.2) {
            // Прелюдия - БЫСТРЫЙ старт
            const localProgress = progress / 0.2;
            scaleValue = 1 + (localProgress * 0.05);
            shakeIntensity = 1 + (localProgress * 0.5); // 1.0 → 1.5 (быстрее!)
        } else if (progress < 0.5) {
            // Нарастание
            const localProgress = (progress - 0.2) / 0.3;
            scaleValue = 1.05 + (localProgress * 0.05);
            shakeIntensity = 1.5 + (localProgress * 0.5); // 1.5 → 2.0
        } else if (progress < 0.8) {
            // Интенсив
            const localProgress = (progress - 0.5) / 0.3;
            scaleValue = 1.1 + (localProgress * 0.05);
            shakeIntensity = 2.0 + (localProgress * 0.5); // 2.0 → 2.5
        } else {
            // Кульминация - точка растет КАК СЕРДЦЕ
            const localProgress = (progress - 0.8) / 0.2;
            scaleValue = 1.15 + (localProgress * 0.2);
            shakeIntensity = 2.5 + (localProgress * 0.5); // 2.5 → 3.0
        }

        // Если цикл завершен - начинаем заново
        if (elapsed >= totalDuration) {
            hoverTimer = Date.now();
        }

        // Применяем scale для сердца
        heartElement.style.setProperty('--heart-scale', scaleValue);

        // Применяем shake intensity для точки
        if (dotElement) {
            dotElement.style.setProperty('--shake-intensity', shakeIntensity);
        }

        // Продолжаем анимацию
        animationFrame = requestAnimationFrame(updateScale);
    }

    // Обработчики для триггеров
    triggers.forEach(trigger => {
        trigger.addEventListener('mouseenter', () => {
            isHovering = true;
            hoverTimer = Date.now();
            scaleValue = 1;
            shakeIntensity = 1;

            heartElement.classList.add('is-beating');
            if (dotElement) {
                dotElement.classList.add('is-shaking');
            }

            animationFrame = requestAnimationFrame(updateScale);
        });

        trigger.addEventListener('mouseleave', () => {
            isHovering = false;
            heartElement.classList.remove('is-beating');
            heartElement.style.setProperty('--heart-scale', 1);

            if (dotElement) {
                dotElement.classList.remove('is-shaking');
                dotElement.style.setProperty('--shake-intensity', 1);
            }

            if (animationFrame) {
                cancelAnimationFrame(animationFrame);
                animationFrame = null;
            }
        });
    });
}

window.addEventListener('load', initHeartbeat);

// --------------------------------------------
// 5. FAQ АККОРДЕОН
// --------------------------------------------
function initFAQ() {
    const faqItems = document.querySelectorAll('.faq-item');

    if (faqItems.length === 0) return;

    faqItems.forEach((item, index) => {
        const button = item.querySelector('.faq-button');
        const panel = item.querySelector('.faq-panel');

        if (!button || !panel) return;

        // Генерируем уникальные ID автоматически
        const buttonId = `faq-button-${index + 1}`;
        const panelId = `faq-panel-${index + 1}`;

        // Устанавливаем ID и aria-атрибуты
        button.id = buttonId;
        button.setAttribute('aria-expanded', 'false');
        button.setAttribute('aria-controls', panelId);

        panel.id = panelId;
        panel.setAttribute('role', 'region');
        panel.setAttribute('aria-labelledby', buttonId);

        // Обработчик клика
        button.addEventListener('click', () => {
            const isExpanded = button.getAttribute('aria-expanded') === 'true';

            // Закрываем все остальные (опционально - убери если хочешь чтобы несколько было открыто)
            faqItems.forEach((otherItem) => {
                const otherButton = otherItem.querySelector('.faq-button');
                const otherPanel = otherItem.querySelector('.faq-panel');

                if (otherButton !== button) {
                    otherButton.setAttribute('aria-expanded', 'false');
                    otherPanel.classList.remove('is-open');
                }
            });

            // Переключаем текущий элемент
            if (isExpanded) {
                button.setAttribute('aria-expanded', 'false');
                panel.classList.remove('is-open');
            } else {
                button.setAttribute('aria-expanded', 'true');
                panel.classList.add('is-open');
            }
        });
    });
}

window.addEventListener('load', initFAQ);

// --------------------------------------------
// 6. ДОБАВИТЬ В КОРЗИНУ - ВЫПАДАЮЩИЙ СПИСОК
// --------------------------------------------
function initAddToCart() {
    const addToCartBlocks = document.querySelectorAll('.add-to-cart');

    if (addToCartBlocks.length === 0) return;

    addToCartBlocks.forEach(block => {
        const button = block.querySelector('.btn-cat');
        const buttonWrapper = block.querySelector('.cart-button-wrapper');
        const linksWrapper = block.querySelector('.cart-links-wrapper');

        if (!button || !buttonWrapper || !linksWrapper) return;

        // Клик на кнопку - открываем список
        button.addEventListener('click', (e) => {
            e.stopPropagation();

            // Закрываем все другие открытые блоки
            addToCartBlocks.forEach(otherBlock => {
                if (otherBlock !== block) {
                    const otherButtonWrapper = otherBlock.querySelector('.cart-button-wrapper');
                    const otherLinksWrapper = otherBlock.querySelector('.cart-links-wrapper');

                    otherBlock.classList.remove('active');
                    otherButtonWrapper.classList.remove('hidden');
                    otherLinksWrapper.classList.add('hidden');
                }
            });

            // Открываем текущий блок
            block.classList.add('active');
            buttonWrapper.classList.add('hidden');
            linksWrapper.classList.remove('hidden');
        });

        // Клик вне блока - закрываем
        document.addEventListener('click', (e) => {
            if (!block.contains(e.target)) {
                block.classList.remove('active');
                buttonWrapper.classList.remove('hidden');
                linksWrapper.classList.add('hidden');
            }
        });

        // Останавливаем всплытие при клике внутри блока
        block.addEventListener('click', (e) => {
            e.stopPropagation();
        });
    });
}

window.addEventListener('load', initAddToCart);

// --------------------------------------------
// 8. СЛАЙДЕР ПРОДУКТА С АВТОПРОКРУТКОЙ
// --------------------------------------------
function initProductSlider() {
    const sliders = document.querySelectorAll('.product-slider');

    if (sliders.length === 0) return;

    sliders.forEach(slider => {
        const images = slider.querySelectorAll('.slider-image');
        const indicatorsContainer = slider.querySelector('.slider-indicators');
        const playPauseBtn = slider.querySelector('.slider-play-pause');
        const pauseIcon = playPauseBtn?.querySelector('.pause-icon');
        const playIcon = playPauseBtn?.querySelector('.play-icon');
        const progressBar = slider.querySelector('.progress-bar');

        const imagesCount = images.length;

        if (imagesCount <= 1) return;

        // Создаем индикаторы
        indicatorsContainer.innerHTML = '';
        const indicators = [];
        for (let i = 0; i < imagesCount; i++) {
            const indicator = document.createElement('span');
            indicator.classList.add('indicator');
            indicatorsContainer.appendChild(indicator);
            indicators.push(indicator);
        }

        // Параметры
        const autoplay = slider.getAttribute('data-autoplay') === 'true';
        const interval = parseInt(slider.getAttribute('data-interval')) || 5000;

        let currentIndex = 0;
        let autoplayTimer = null;
        let progressTimer = null;
        let isPlaying = autoplay;
        let isHovered = false; // НОВЫЙ ФЛАГ

        // Показать картинку
        function showImage(index) {
            images.forEach(img => img.classList.remove('active'));
            indicators.forEach(ind => ind.classList.remove('active'));

            images[index].classList.add('active');
            indicators[index].classList.add('active');

            currentIndex = index;
        }

        // Следующая картинка
        function nextImage() {
            const nextIndex = (currentIndex + 1) % imagesCount;
            showImage(nextIndex);
        }

        // Обновление прогресс-бара
        function updateProgress() {
            if (!isPlaying || isHovered) return; // ПРОВЕРЯЕМ isHovered

            let progress = 0;
            const step = 100 / (interval / 100);

            progressTimer = setInterval(() => {
                if (isHovered) return; // ПРОВЕРЯЕМ isHovered

                progress += step;
                const offset = 100 - progress;
                progressBar.style.strokeDashoffset = offset;

                if (progress >= 100) {
                    clearInterval(progressTimer);
                }
            }, 100);
        }

        // Старт автопрокрутки
        function startAutoplay() {
            if (!isPlaying || isHovered) return; // ПРОВЕРЯЕМ isHovered

            stopAutoplay();

            // Сброс прогресса
            progressBar.style.strokeDashoffset = 100;

            // Запуск прогресс-бара
            updateProgress();

            // Запуск автопрокрутки
            autoplayTimer = setTimeout(() => {
                if (isHovered) return; // ПРОВЕРЯЕМ перед переключением
                nextImage();
                startAutoplay();
            }, interval);
        }

        // Остановка автопрокрутки
        function stopAutoplay() {
            if (autoplayTimer) {
                clearTimeout(autoplayTimer);
                autoplayTimer = null;
            }
            if (progressTimer) {
                clearInterval(progressTimer);
                progressTimer = null;
            }
        }

        // Toggle play/pause
        function togglePlayPause() {
            isPlaying = !isPlaying;

            if (isPlaying) {
                pauseIcon.classList.remove('hidden');
                playIcon.classList.add('hidden');
                playPauseBtn.setAttribute('aria-label', 'Pause slideshow');
                if (!isHovered) { // Запускаем только если не наведен курсор
                    startAutoplay();
                }
            } else {
                pauseIcon.classList.add('hidden');
                playIcon.classList.remove('hidden');
                playPauseBtn.setAttribute('aria-label', 'Play slideshow');
                stopAutoplay();
                progressBar.style.strokeDashoffset = 100;
            }
        }

        // Инициализация
        showImage(0);
        if (autoplay) {
            startAutoplay();
        }

        // События

        // Клик на кнопку play/pause
        if (playPauseBtn) {
            playPauseBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                togglePlayPause();
            });
        }

        // ДЕСКТОП: Наведение мыши - полная остановка
        slider.addEventListener('mouseenter', () => {
            isHovered = true;
            stopAutoplay(); // ПОЛНОСТЬЮ ОСТАНАВЛИВАЕМ
        });

        slider.addEventListener('mouseleave', () => {
            isHovered = false;
            if (isPlaying) {
                startAutoplay(); // ПЕРЕЗАПУСКАЕМ
            }
        });

        // МОБИЛЬНЫЙ: Клик на картинку - toggle play/pause
        slider.addEventListener('click', (e) => {
            if (e.target.closest('.slider-play-pause')) return;

            if (window.innerWidth < 1024) {
                togglePlayPause();
            }
        });

        // Свайпы для мобильных
        let touchStartX = 0;
        let touchEndX = 0;

        slider.addEventListener('touchstart', (e) => {
            touchStartX = e.changedTouches[0].screenX;
        }, { passive: true });

        slider.addEventListener('touchend', (e) => {
            touchEndX = e.changedTouches[0].screenX;
            handleSwipe();
        });

        function handleSwipe() {
            const swipeThreshold = 50;

            if (touchEndX < touchStartX - swipeThreshold) {
                const nextIndex = (currentIndex + 1) % imagesCount;
                showImage(nextIndex);
                if (isPlaying) {
                    startAutoplay();
                }
            }

            if (touchEndX > touchStartX + swipeThreshold) {
                const prevIndex = (currentIndex - 1 + imagesCount) % imagesCount;
                showImage(prevIndex);
                if (isPlaying) {
                    startAutoplay();
                }
            }
        }
    });
}

window.addEventListener('load', initProductSlider);


// --------------------------------------------
// 9. DRAG КАРУСЕЛЬ С КАСТОМНЫМ КУРСОРОМ
// --------------------------------------------
function initDragCarousel() {
    const carouselWrappers = document.querySelectorAll('.carousel-wrapper');

    if (carouselWrappers.length === 0) return;

    carouselWrappers.forEach(wrapper => {
        const cursor = wrapper.querySelector('.carousel-cursor');

        if (!cursor) return;

        let isDragging = false;
        let startX = 0;
        let scrollLeft = 0;
        let hasMoved = false; // Флаг для отслеживания движения

        // Обновление позиции кастомного курсора
        function updateCursorPosition(e) {
            cursor.style.left = e.clientX + 'px';
            cursor.style.top = e.clientY + 'px';
        }

        // Начало драга
        function startDrag(e) {
            // Запускаем драг на любом элементе внутри wrapper
            isDragging = true;
            hasMoved = false;
            wrapper.classList.add('is-dragging');

            startX = e.pageX - wrapper.offsetLeft;
            scrollLeft = wrapper.scrollLeft;

            wrapper.style.scrollBehavior = 'auto';

            // Запрещаем выделение текста
            e.preventDefault();
        }

        // Процесс драга
        function drag(e) {
            if (!isDragging) return;

            e.preventDefault();
            hasMoved = true; // Зафиксировали что было движение

            const x = e.pageX - wrapper.offsetLeft;
            const walk = (x - startX) * 1.5;
            wrapper.scrollLeft = scrollLeft - walk;
        }

        // Конец драга
        function endDrag(e) {
            if (!isDragging) return;

            isDragging = false;

            // Блокируем клики если было движение
            if (hasMoved) {
                setTimeout(() => {
                    wrapper.classList.remove('is-dragging');
                }, 10);
            } else {
                wrapper.classList.remove('is-dragging');
            }

            wrapper.style.scrollBehavior = 'smooth';
        }

        // Движение мыши
        wrapper.addEventListener('mousemove', (e) => {
            updateCursorPosition(e);

            if (isDragging) {
                drag(e);
            }
        });

        // События драга - на самом wrapper
        wrapper.addEventListener('mousedown', startDrag);
        wrapper.addEventListener('mouseup', endDrag);
        wrapper.addEventListener('mouseleave', endDrag);

        // Дополнительная защита - блокируем клики при драге
        wrapper.addEventListener('click', (e) => {
            if (hasMoved) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                hasMoved = false;
            }
        }, true);
    });
}

window.addEventListener('load', initDragCarousel);

// ============================================
// SHOP — МОДАЛКИ МАГАЗИНА
// ============================================

// --------------------------------------------
// 10. FLOATING NAV — открытие модалок
// --------------------------------------------
function initFloatingNav() {
    document.querySelectorAll('[data-open-modal]').forEach(btn => {
        btn.addEventListener('click', () => {
            const modalId = btn.dataset.openModal;
            const modal = document.getElementById(modalId);
            if (modal) openModal(modal);
        });
    });
}

window.addEventListener('load', initFloatingNav);

// --------------------------------------------
// 11. PRODUCT BUY — размеры + добавление в корзину (API)
// --------------------------------------------
function initProductBuy() {
    const sym = window.DRJOYS?.currencySymbol || '₸';
    let sizeSelected = false;
    let selectedSizeId = null;

    // --- Size dropdown (Lamoda-style) ---
    const dropdown = document.getElementById('sizeDropdown');
    const triggerBtn = document.getElementById('sizeDropdownBtn');
    const menu = document.getElementById('sizeMenu');
    const selectedName = document.getElementById('selectedSizeName');

    function openDropdown() {
        if (!menu || !dropdown) return;
        menu.classList.remove('hidden');
        dropdown.classList.add('open');
    }

    function closeDropdown() {
        if (!menu || !dropdown) return;
        menu.classList.add('hidden');
        dropdown.classList.remove('open');
    }

    function selectSize(item) {
        sizeSelected = true;
        selectedSizeId = parseInt(item.dataset.sizeId);

        // Update active state
        menu.querySelectorAll('.size-dropdown__item--active').forEach(el => el.classList.remove('size-dropdown__item--active'));
        item.classList.add('size-dropdown__item--active');

        // Update trigger: remove placeholder style, show size name
        triggerBtn.classList.remove('size-dropdown__trigger--placeholder');
        if (selectedName) selectedName.textContent = item.dataset.size;

        // Show & update SKU
        const skuBlock = document.getElementById('skuBlock');
        const skuEl = document.getElementById('productSku');
        if (skuBlock) skuBlock.classList.remove('hidden');
        if (skuEl) skuEl.textContent = item.dataset.sku;

        // Show & update price
        const priceRow = document.getElementById('priceRow');
        const priceCurrentEl = document.getElementById('priceCurrent');
        const priceOldEl = document.getElementById('priceOld');
        const priceDiscountEl = document.getElementById('priceDiscount');

        if (priceRow) priceRow.classList.remove('hidden');
        if (priceCurrentEl) priceCurrentEl.textContent = item.dataset.price + ' ' + sym;

        if (priceOldEl && priceDiscountEl) {
            if (item.dataset.oldPrice) {
                priceOldEl.textContent = item.dataset.oldPrice + ' ' + sym;
                priceDiscountEl.textContent = '-' + item.dataset.discount + '%';
                priceOldEl.classList.remove('hidden');
                priceDiscountEl.classList.remove('hidden');
            } else {
                priceOldEl.classList.add('hidden');
                priceDiscountEl.classList.add('hidden');
            }
        }

        // Двойная валюта (payment price)
        const pricePaymentEl = document.getElementById('pricePayment');
        if (pricePaymentEl) {
            const paymentPrice = item.dataset.paymentPrice;
            if (paymentPrice) {
                pricePaymentEl.textContent = '(' + paymentPrice + ' ' + (window.DRJOYS?.paymentCurrencySymbol || '') + ')';
                pricePaymentEl.classList.remove('hidden');
            } else {
                pricePaymentEl.classList.add('hidden');
            }
        }

        closeDropdown();
    }

    if (dropdown && triggerBtn && menu) {
        triggerBtn.addEventListener('click', () => {
            const isOpen = !menu.classList.contains('hidden');
            if (isOpen) closeDropdown();
            else openDropdown();
        });

        document.addEventListener('click', (e) => {
            const buyBtn = document.getElementById('buyAnonymousBtn');
            if (!dropdown.contains(e.target) && e.target !== buyBtn) closeDropdown();
        });

        menu.querySelectorAll('.size-dropdown__item:not(.size-dropdown__item--disabled)').forEach(item => {
            item.addEventListener('click', () => selectSize(item));
        });
    }

    // --- Buy button → open Order Quantity modal ---
    const buyBtn = document.getElementById('buyAnonymousBtn');

    if (buyBtn) {
        buyBtn.addEventListener('click', () => {
            if (!sizeSelected || !selectedSizeId) {
                openDropdown();
                return;
            }

            // Найти выбранный элемент размера
            const activeItem = menu ? menu.querySelector('.size-dropdown__item--active') : null;
            if (!activeItem) return;

            const productBuyEl = document.getElementById('productBuy');
            const productName = productBuyEl ? productBuyEl.dataset.productName : '';
            const sizeName = activeItem.dataset.size || '';
            const price = activeItem.dataset.price || '0';

            // Заполнить модалку Order Quantity
            const nameEl = document.getElementById('orderProductName');
            const sizeEl = document.getElementById('orderProductSize');
            const unitEl = document.getElementById('orderUnitPrice');
            const totalEl = document.getElementById('orderTotalPrice');
            const qtyEl = document.getElementById('qtyValue');
            const addBtn = document.getElementById('addToCartBtn');

            if (nameEl) nameEl.textContent = productName;
            if (sizeEl) sizeEl.textContent = sizeName;
            if (unitEl) {
                unitEl.dataset.price = price.replace(/\s/g, '').replace(',', '.');
                unitEl.textContent = price + ' ' + sym;
            }
            if (qtyEl) qtyEl.textContent = '1';
            if (totalEl) totalEl.textContent = price + ' ' + sym;
            if (addBtn) addBtn.dataset.sizeId = selectedSizeId;

            // Открыть модалку
            const modal = document.getElementById('modalOrderQuantity');
            if (modal) openModal(modal);
        });
    }

    // --- Favorite button toggle → API ---
    const favBtn = document.getElementById('productFavoriteBtn');
    const productBuy = document.getElementById('productBuy');
    const productId = productBuy ? productBuy.dataset.productId : null;

    if (favBtn && productId) {
        const favPath = favBtn.querySelector('svg path');
        favBtn.addEventListener('click', async () => {
            favBtn.disabled = true;
            const result = await apiPost('/orders/favorites/toggle/', { product_id: parseInt(productId) });
            favBtn.disabled = false;

            if (result.ok) {
                const isActive = result.added;
                favBtn.classList.toggle('active', isActive);
                if (favPath) favPath.setAttribute('fill', isActive ? 'currentColor' : 'none');
                updateBadges(null, result.fav_count);
            }
        });
    }
}

window.addEventListener('load', initProductBuy);

// --------------------------------------------
// 12. ORDER QUANTITY — счётчик + цена (API-aware)
// --------------------------------------------
function initOrderQuantity() {
    const qtyMinus = document.getElementById('qtyMinus');
    const qtyPlus = document.getElementById('qtyPlus');
    const qtyValue = document.getElementById('qtyValue');

    if (!qtyMinus || !qtyPlus || !qtyValue) return;

    qtyMinus.addEventListener('click', () => {
        let val = parseInt(qtyValue.textContent) || 1;
        if (val > 1) {
            qtyValue.textContent = val - 1;
            updateOrderTotal();
        }
    });

    qtyPlus.addEventListener('click', () => {
        let val = parseInt(qtyValue.textContent) || 1;
        if (val < 99) {
            qtyValue.textContent = val + 1;
            updateOrderTotal();
        }
    });

    // Add to cart button → API
    const addToCartBtn = document.getElementById('addToCartBtn');
    if (addToCartBtn) {
        addToCartBtn.addEventListener('click', async () => {
            const sizeId = addToCartBtn.dataset.sizeId;
            const qty = parseInt(qtyValue.textContent) || 1;
            if (!sizeId) return;
            addToCartBtn.disabled = true;
            const result = await apiPost('/orders/cart/add/', { size_id: parseInt(sizeId), qty });
            addToCartBtn.disabled = false;
            if (result.ok) {
                updateBadges(result.cart_count, null);
                closeModal(document.getElementById('modalOrderQuantity'));
                // Открыть корзину
                const cartModal = document.getElementById('modalCart');
                if (cartModal) openModal(cartModal);
            }
        });
    }

    // Go to checkout page
    const goToDeliveryBtn = document.getElementById('goToDeliveryBtn');
    if (goToDeliveryBtn) {
        goToDeliveryBtn.addEventListener('click', () => {
            closeModal(document.getElementById('modalOrderQuantity'));
            window.location.href = '/orders/checkout/';
        });
    }
}

function updateOrderTotal() {
    const qtyValue = document.getElementById('qtyValue');
    const totalEl = document.getElementById('orderTotalPrice');
    const unitEl = document.getElementById('orderUnitPrice');
    if (!qtyValue || !totalEl || !unitEl) return;

    // data-price хранит чистое число (без пробелов/валюты)
    const priceStr = (unitEl.dataset.price || '0').replace(/\s/g, '').replace(',', '.');
    const unitPrice = parseFloat(priceStr) || 0;
    const qty = parseInt(qtyValue.textContent) || 1;
    const total = unitPrice * qty;
    const sym = window.DRJOYS?.currencySymbol || '₸';
    totalEl.textContent = total.toLocaleString('ru-RU') + ' ' + sym;
}

window.addEventListener('load', initOrderQuantity);

// --------------------------------------------
// 13. CART MODAL — загрузка из API, update, remove
// --------------------------------------------
function initCartModal() {
    const cartOverlay = document.getElementById('modalCart');
    if (!cartOverlay) return;

    const sym = window.DRJOYS?.currencySymbol || '₸';
    const paySym = window.DRJOYS?.paymentCurrencySymbol || '';
    const needsConv = window.DRJOYS?.needsConversion || false;
    let cartData = { items: [], cart_total: '0', cart_old_total: '0', cart_count: 0 };

    function fmtPrice(val) {
        return parseFloat(val).toLocaleString('ru-RU') + ' ' + sym;
    }

    function fmtPayment(val) {
        return parseFloat(val).toLocaleString('ru-RU') + ' ' + paySym;
    }

    function renderCart() {
        const listEl = document.getElementById('cartItemsList');
        const emptyEl = document.getElementById('cartEmpty');
        const footerEl = document.getElementById('cartFooter');
        const items = cartData.items;

        if (!items.length) {
            if (listEl) listEl.innerHTML = '';
            if (emptyEl) { emptyEl.classList.remove('hidden'); emptyEl.classList.add('flex'); }
            if (footerEl) footerEl.classList.add('hidden');
            return;
        }

        if (emptyEl) { emptyEl.classList.add('hidden'); emptyEl.classList.remove('flex'); }
        if (footerEl) footerEl.classList.remove('hidden');

        if (listEl) {
            listEl.innerHTML = items.map(item => {
                const hasOld = item.old_price && parseFloat(item.old_price) > parseFloat(item.price);
                const minusSvg = item.qty <= 1
                    ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>'
                    : '<svg width="12" height="12" viewBox="0 0 16 16" fill="none"><path d="M3 8H13" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
                const minusAction = item.qty <= 1 ? 'remove' : 'minus';

                return `<div class="cart-item flex gap-3 py-3" data-size-id="${item.size_id}" data-price="${item.price}" data-old-price="${item.old_price || ''}">
                    <div class="w-15 h-15 shrink-0 rounded-lg overflow-hidden bg-stone-50">
                        <img src="${item.image_url || window.DRJOYS?.placeholderUrl || ''}" class="w-full h-full object-cover" alt="${item.name}" loading="lazy">
                    </div>
                    <div class="flex-1 min-w-0">
                        <p class="text-xs font-bold truncate">${item.name}</p>
                        <p class="text-[10px] text-gray-500">${item.size_name}</p>
                        <div class="flex items-center justify-between mt-1">
                            <div class="flex items-center gap-2">
                                <button class="cart-qty-btn" type="button" data-action="${minusAction}" aria-label="${window.DRJOYS.i18n.decrease}">${minusSvg}</button>
                                <span class="text-xs font-benzin min-w-5 text-center cart-item-qty">${item.qty}</span>
                                <button class="cart-qty-btn" type="button" data-action="plus" aria-label="${window.DRJOYS.i18n.increase}">
                                    <svg width="12" height="12" viewBox="0 0 16 16" fill="none"><path d="M8 3V13M3 8H13" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
                                </button>
                            </div>
                            <div class="flex items-center gap-1.5 flex-wrap justify-end">
                                <span class="text-[10px] text-stone-400 line-through cart-item-old-price ${hasOld ? '' : 'hidden'}">${hasOld ? fmtPrice(parseFloat(item.old_price) * item.qty) : ''}</span>
                                <span class="text-xs font-bold cart-item-price">${fmtPrice(item.subtotal)}</span>
                                ${item.payment_subtotal ? `<span class="text-[10px] text-stone-400">(${fmtPayment(item.payment_subtotal)})</span>` : ''}
                            </div>
                        </div>
                    </div>
                </div>`;
            }).join('');
        }

        // Totals
        const total = parseFloat(cartData.cart_total);
        const oldTotal = parseFloat(cartData.cart_old_total);
        const cartTotalEl = document.getElementById('cartTotal');
        const cartOldTotalEl = document.getElementById('cartOldTotal');
        const cartSavingsEl = document.getElementById('cartSavings');

        if (cartTotalEl) {
            let totalText = fmtPrice(total);
            if (needsConv && cartData.payment_total) {
                totalText += ' (' + fmtPayment(parseFloat(cartData.payment_total)) + ')';
            }
            cartTotalEl.textContent = totalText;
        }

        const savings = oldTotal - total;
        if (savings > 0 && cartOldTotalEl && cartSavingsEl) {
            cartOldTotalEl.textContent = fmtPrice(oldTotal);
            cartOldTotalEl.classList.remove('hidden');
            const percent = Math.round((savings / oldTotal) * 100);
            cartSavingsEl.textContent = '-' + percent + '%';
            cartSavingsEl.classList.remove('hidden');
        } else {
            if (cartOldTotalEl) cartOldTotalEl.classList.add('hidden');
            if (cartSavingsEl) cartSavingsEl.classList.add('hidden');
        }
    }

    async function loadCart() {
        try {
            const resp = await fetch('/orders/cart/');
            cartData = await resp.json();
            if (cartData.ok) {
                renderCart();
                updateBadges(cartData.cart_count, null);
            }
        } catch (e) {
            console.error('loadCart error:', e);
        }
    }

    // Load cart when modal opens
    cartOverlay.addEventListener('modal:open', () => loadCart());

    // Qty/remove via delegation
    cartOverlay.addEventListener('click', async (e) => {
        const btn = e.target.closest('.cart-qty-btn');
        if (!btn) return;

        const item = btn.closest('.cart-item');
        const sizeId = parseInt(item.dataset.sizeId);
        const qtyEl = item.querySelector('.cart-item-qty');
        let qty = parseInt(qtyEl.textContent) || 1;

        if (btn.dataset.action === 'remove') {
            await apiPost('/orders/cart/remove/', { size_id: sizeId });
            loadCart();
            return;
        }
        if (btn.dataset.action === 'minus' && qty > 1) {
            qty -= 1;
        } else if (btn.dataset.action === 'plus' && qty < 99) {
            qty += 1;
        }
        const result = await apiPost('/orders/cart/update/', { size_id: sizeId, qty });
        if (result.ok) {
            updateBadges(result.cart_count, null);
            loadCart();
        }
    });

    // Checkout → auth check → delivery
    // Checkout → страница оформления заказа
    const checkoutBtn = document.getElementById('cartCheckoutBtn');
    if (checkoutBtn) {
        checkoutBtn.addEventListener('click', () => {
            closeModal(cartOverlay);
            window.location.href = '/orders/checkout/';
        });
    }

    // Continue shopping
    const continueBtn = document.getElementById('cartContinueBtn');
    if (continueBtn) {
        continueBtn.addEventListener('click', () => closeModal(cartOverlay));
    }
}

window.addEventListener('load', initCartModal);

// --------------------------------------------
// 14. FAVORITES MODAL — загрузка из API, удаление
// --------------------------------------------
function initFavoritesModal() {
    const favOverlay = document.getElementById('modalFavorites');
    if (!favOverlay) return;

    const sym = window.DRJOYS?.currencySymbol || '₸';

    function renderFavorites(data) {
        const listEl = document.getElementById('favoritesList');
        const emptyEl = document.getElementById('favoritesEmpty');
        const items = data.items || [];

        if (!items.length) {
            if (listEl) listEl.innerHTML = '';
            if (emptyEl) { emptyEl.classList.remove('hidden'); emptyEl.classList.add('flex'); }
            return;
        }

        if (emptyEl) { emptyEl.classList.add('hidden'); emptyEl.classList.remove('flex'); }

        if (listEl) {
            listEl.innerHTML = items.map(item => `
                <div class="fav-item flex gap-3 p-2 rounded-xl bg-stone-50" data-product-id="${item.product_id}" data-first-size-id="${item.first_size_id || ''}">
                    <div class="w-20 h-20 shrink-0 rounded-lg overflow-hidden bg-stone-50">
                        <img src="${item.image_url || window.DRJOYS?.placeholderUrl || ''}" class="w-full h-full object-cover" alt="${item.name}" loading="lazy">
                    </div>
                    <div class="flex-1 min-w-0 flex flex-col justify-between py-1">
                        <div>
                            <p class="text-xs font-bold leading-tight">${item.name}</p>
                            ${item.price ? `<p class="text-xs text-red-500 font-benzin mt-1">${parseFloat(item.price).toLocaleString('ru-RU')} ${sym}${item.payment_price ? ` <span class="text-stone-400 font-normal">(${parseFloat(item.payment_price).toLocaleString('ru-RU')} ${window.DRJOYS?.paymentCurrencySymbol || ''})</span>` : ''}</p>` : ''}
                        </div>
                        ${item.first_size_id ? `<button class="fav-to-cart-btn text-[10px] uppercase font-bold text-gray-500 hover:text-black text-left" type="button">${window.DRJOYS.i18n.addToCart}</button>` : ''}
                    </div>
                    <button class="fav-remove-btn shrink-0 self-start text-gray-500 hover:text-red-500 p-1" type="button" aria-label="${window.DRJOYS.i18n.removeFromFav}">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="3 6 5 6 21 6"/>
                            <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                            <line x1="10" y1="11" x2="10" y2="17"/>
                            <line x1="14" y1="11" x2="14" y2="17"/>
                        </svg>
                    </button>
                </div>
            `).join('');
        }
    }

    async function loadFavorites() {
        try {
            const resp = await fetch('/orders/favorites/');
            const data = await resp.json();
            if (data.ok) {
                renderFavorites(data);
                updateBadges(null, data.fav_count);
            }
        } catch (e) {
            console.error('loadFavorites error:', e);
        }
    }

    // Load when modal opens
    favOverlay.addEventListener('modal:open', () => loadFavorites());

    // Remove + Add to cart via delegation
    favOverlay.addEventListener('click', async (e) => {
        // Remove
        const removeBtn = e.target.closest('.fav-remove-btn');
        if (removeBtn) {
            const item = removeBtn.closest('.fav-item');
            const productId = parseInt(item.dataset.productId);
            const result = await apiPost('/orders/favorites/remove/', { product_id: productId });
            if (result.ok) updateBadges(null, result.fav_count);
            loadFavorites();
            return;
        }

        // Add to cart
        const cartBtn = e.target.closest('.fav-to-cart-btn');
        if (cartBtn) {
            const item = cartBtn.closest('.fav-item');
            const sizeId = item.dataset.firstSizeId;
            if (!sizeId) return;
            cartBtn.disabled = true;
            const result = await apiPost('/orders/cart/add/', { size_id: parseInt(sizeId), qty: 1 });
            cartBtn.disabled = false;
            if (result.ok) {
                updateBadges(result.cart_count, null);
                cartBtn.textContent = '✓';
                setTimeout(() => { cartBtn.textContent = window.DRJOYS.i18n.addToCart; }, 800);
            }
        }
    });
}

window.addEventListener('load', initFavoritesModal);

// --------------------------------------------
// 15. PROFILE MODAL — навигация по шагам
// --------------------------------------------
function initProfileModal() {
    const profileOverlay = document.getElementById('modalProfile');
    if (!profileOverlay) return;

    const backBtn = document.getElementById('profileBackBtn');
    let stepHistory = ['1'];
    let ordersLoaded = false;
    let ordersData = [];

    const STATUS_CSS = {
        pending: 'order-status--processing',
        paid: 'order-status--processing',
        shipped: 'order-status--shipped',
        delivered: 'order-status--delivered',
        cancelled: 'order-status--processing',
    };

    function resetProfile() {
        stepHistory = ['1'];
        if (backBtn) backBtn.classList.add('hidden');
        closeModal(profileOverlay);
    }

    function goToProfileStep(stepNum) {
        if (stepHistory[stepHistory.length - 1] !== stepNum) {
            stepHistory.push(stepNum);
        }
        goToStep(profileOverlay, stepNum);

        if (backBtn) {
            backBtn.classList.toggle('hidden', stepHistory.length <= 1);
        }
    }

    function formatDate(isoStr) {
        const d = new Date(isoStr);
        return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
    }

    function formatAmount(amount, symbol) {
        const num = parseFloat(amount);
        return num.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) + ' ' + symbol;
    }

    async function loadOrders() {
        if (ordersLoaded) return;
        const loadingEl = document.getElementById('ordersLoading');
        const emptyEl = document.getElementById('ordersEmpty');
        const listEl = document.getElementById('ordersHistoryList');

        try {
            const resp = await fetch('/orders/history/', { credentials: 'same-origin' });
            const data = await resp.json();
            ordersLoaded = true;

            if (loadingEl) loadingEl.classList.add('hidden');

            if (!data.ok || !data.orders || data.orders.length === 0) {
                if (emptyEl) emptyEl.classList.remove('hidden');
                return;
            }

            ordersData = data.orders;

            ordersData.forEach(order => {
                const symbol = order.currency_symbol || '₸';
                const amount = order.display_amount || order.total_amount;
                const statusCls = STATUS_CSS[order.status] || 'order-status--processing';

                const btn = document.createElement('button');
                btn.className = 'order-card w-full text-left p-3 rounded-xl bg-stone-50 hover:bg-gray-200';
                btn.type = 'button';
                btn.dataset.orderId = order.id;
                btn.innerHTML = `
                    <div class="flex justify-between items-start">
                        <div>
                            <p class="text-sm font-bold">#${order.number}</p>
                            <p class="text-[10px] text-gray-500">${formatDate(order.created_at)}</p>
                        </div>
                        <span class="order-status ${statusCls} text-[10px] font-bold px-2 py-0.5 rounded-full">${order.status_display}</span>
                    </div>
                    <p class="text-xs font-benzin text-red-500 mt-2">${formatAmount(amount, symbol)}</p>
                `;

                btn.addEventListener('click', () => showOrderDetail(order));
                listEl.appendChild(btn);
            });
        } catch (err) {
            if (loadingEl) loadingEl.textContent = window.DRJOYS.i18n.loadError;
            console.error('Orders load error:', err);
        }
    }

    function showOrderDetail(order) {
        const titleEl = document.getElementById('orderDetailTitle');
        const contentEl = document.getElementById('orderDetailContent');
        const symbol = order.currency_symbol || '₸';
        const amount = order.display_amount || order.total_amount;
        const statusCls = STATUS_CSS[order.status] || 'order-status--processing';

        titleEl.textContent = `${window.DRJOYS.i18n.orderNum} #${order.number}`;

        let itemsHtml = '';
        (order.items || []).forEach(item => {
            itemsHtml += `
                <div class="flex gap-3 py-2">
                    <div class="w-12 h-12 shrink-0 rounded-lg overflow-hidden bg-stone-50">
                        <div class="w-full h-full bg-stone-50"></div>
                    </div>
                    <div class="flex-1">
                        <p class="text-xs font-bold">${item.product_name}</p>
                        <p class="text-[10px] text-gray-500">${window.DRJOYS.i18n.sizeLbl}: ${item.size_name} &middot; ${item.quantity} ${window.DRJOYS.i18n.pcsLbl}</p>
                        <p class="text-xs font-bold mt-1">${formatAmount(item.subtotal, symbol)}</p>
                    </div>
                </div>
            `;
        });

        contentEl.innerHTML = `
            <div class="flex justify-between items-center">
                <p class="text-xs text-gray-500">${formatDate(order.created_at)}</p>
                <span class="order-status ${statusCls} text-[10px] font-bold px-2 py-0.5 rounded-full">${order.status_display}</span>
            </div>
            <div class="flex flex-col divide-y divide-stone-50">
                ${itemsHtml}
            </div>
            <div>
                <p class="text-xs font-bold pb-1">${window.DRJOYS.i18n.deliveryAddr}</p>
                <p class="text-xs text-gray-500">${order.city}, ${order.address}</p>
            </div>
            <div class="flex justify-between items-center pt-2 border-t border-stone-50">
                <span class="font-benzin uppercase text-sm">${window.DRJOYS.i18n.totalLbl}</span>
                <span class="font-benzin text-red-500">${formatAmount(amount, symbol)}</span>
            </div>
        `;

        goToProfileStep('2-detail');
    }

    // Menu buttons
    profileOverlay.querySelectorAll('[data-profile-step]').forEach(btn => {
        btn.addEventListener('click', () => {
            const step = btn.dataset.profileStep;
            if (step === '2') loadOrders();
            goToProfileStep(step);
        });
    });

    // Back button
    if (backBtn) {
        backBtn.addEventListener('click', () => {
            stepHistory.pop();
            const prevStep = stepHistory[stepHistory.length - 1] || '1';
            goToStep(profileOverlay, prevStep);
            backBtn.classList.toggle('hidden', stepHistory.length <= 1);
        });
    }

    // Close button (remove inline onclick, use JS)
    const closeBtn = profileOverlay.querySelector('.modal-close');
    if (closeBtn) {
        closeBtn.removeAttribute('onclick');
        closeBtn.addEventListener('click', resetProfile);
    }

    // Logout
    const logoutBtn = document.getElementById('profileLogoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            await apiPost(`/${window.DRJOYS.lang}/accounts/logout/`, {});
            location.reload();
        });
    }

    // Close on overlay click
    profileOverlay.addEventListener('click', (e) => {
        if (e.target === profileOverlay) resetProfile();
    });
}

window.addEventListener('load', initProfileModal);

// --------------------------------------------
// 16. AUTH MODAL — Email Login / Register / SSO
// --------------------------------------------
function initPasswordToggles() {
    document.querySelectorAll('[data-toggle-password]').forEach(btn => {
        btn.addEventListener('click', () => {
            const inputId = btn.dataset.togglePassword;
            const input = document.getElementById(inputId);
            if (!input) return;
            const isPassword = input.type === 'password';
            input.type = isPassword ? 'text' : 'password';
            btn.querySelector('.eye-open').classList.toggle('hidden', !isPassword);
            btn.querySelector('.eye-closed').classList.toggle('hidden', isPassword);
        });
    });
}

function initAuthModal() {
    const authOverlay = document.getElementById('modalAuth');
    if (!authOverlay) return;

    initPasswordToggles();

    const backBtn = document.getElementById('authBackBtn');
    let ssoPopup = null;
    let ssoPopupTimer = null;

    function resetAuth() {
        if (backBtn) backBtn.classList.add('hidden');
        authOverlay.querySelectorAll('input').forEach(i => { i.value = ''; });
        authOverlay.querySelectorAll('.text-red-500').forEach(el => {
            el.textContent = '';
            el.classList.add('hidden');
        });
        closeModal(authOverlay);
    }

    function showError(el, errors) {
        if (!el) return;
        const msgs = [];
        for (const key in errors) {
            const val = errors[key];
            if (Array.isArray(val)) msgs.push(...val);
            else msgs.push(val);
        }
        el.textContent = msgs.join(' ');
        el.classList.remove('hidden');
    }

    function handleAuthSuccess() {
        window.DRJOYS.isAuthenticated = true;
        if (window._afterAuthAction === 'delivery') {
            window._afterAuthAction = null;
            closeModal(authOverlay);
            const deliveryModal = document.getElementById('modalDelivery');
            if (deliveryModal) setTimeout(() => openDeliveryWithProfile(deliveryModal), 200);
        } else {
            location.reload();
        }
    }

    // --- Step navigation ---
    authOverlay.querySelectorAll('[data-auth-method]').forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.dataset.authMethod;
            goToStep(authOverlay, target);
            if (backBtn) backBtn.classList.toggle('hidden', target === '1');
        });
    });

    if (backBtn) {
        backBtn.addEventListener('click', () => {
            goToStep(authOverlay, '1');
            backBtn.classList.add('hidden');
        });
    }

    // --- EMAIL LOGIN ---
    const loginForm = document.getElementById('authLoginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const loginBtn = document.getElementById('authLoginBtn');
            const email = document.getElementById('authLoginEmail').value.trim();
            const password = document.getElementById('authLoginPassword').value;
            const errorEl = document.getElementById('authLoginError');
            errorEl.classList.add('hidden');

            loginBtn.disabled = true;
            try {
                const result = await apiPost(`/${window.DRJOYS.lang}/accounts/login/`, { email, password });
                loginBtn.disabled = false;
                if (result.ok) {
                    handleAuthSuccess();
                } else {
                    showError(errorEl, result.errors || {__all__: [window.DRJOYS.i18n.loginError]});
                }
            } catch (err) {
                loginBtn.disabled = false;
                showError(errorEl, {__all__: [window.DRJOYS.i18n.networkError]});
                console.error('Login error:', err);
            }
        });
    }

    // --- REGISTER ---
    const registerForm = document.getElementById('authRegisterForm');
    if (registerForm) {
        let registerSubmitting = false;
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (registerSubmitting) return;
            registerSubmitting = true;

            const registerBtn = document.getElementById('authRegisterBtn');
            const email = document.getElementById('authRegEmail').value.trim();
            const password1 = document.getElementById('authRegPassword1').value;
            const password2 = document.getElementById('authRegPassword2').value;
            const errorEl = document.getElementById('authRegError');
            errorEl.classList.add('hidden');

            const originalText = registerBtn.textContent;
            registerBtn.disabled = true;
            registerBtn.textContent = '...';
            try {
                const result = await apiPost(`/${window.DRJOYS.lang}/accounts/register/`, { email, password1, password2 });
                if (result.ok) {
                    if (result.redirect_url) {
                        window.location.href = result.redirect_url;
                        return; // Не разблокируем — идёт редирект
                    }
                    handleAuthSuccess();
                    return;
                }
                showError(errorEl, result.errors || {__all__: [window.DRJOYS.i18n.registerError]});
            } catch (err) {
                showError(errorEl, {__all__: [window.DRJOYS.i18n.networkError]});
                console.error('Register error:', err);
            }
            registerBtn.disabled = false;
            registerBtn.textContent = originalText;
            registerSubmitting = false;
        });
    }

    // --- SSO POPUP ---
    authOverlay.querySelectorAll('[data-sso-provider]').forEach(btn => {
        btn.addEventListener('click', () => {
            const provider = btn.dataset.ssoProvider;
            const w = 500, h = 600;
            const left = (screen.width - w) / 2;
            const top = (screen.height - h) / 2;
            ssoPopup = window.open(
                `/accounts/${provider}/login/?process=login`,
                'drjoys_sso',
                'width=' + w + ',height=' + h + ',left=' + left + ',top=' + top + ',toolbar=no,menubar=no,scrollbars=yes'
            );
            // Fallback: poll for popup close
            clearInterval(ssoPopupTimer);
            ssoPopupTimer = setInterval(() => {
                if (!ssoPopup || ssoPopup.closed) {
                    clearInterval(ssoPopupTimer);
                    ssoPopup = null;
                    checkAuthAfterSSO();
                }
            }, 500);
        });
    });

    async function checkAuthAfterSSO() {
        try {
            const resp = await fetch(`/${window.DRJOYS.lang}/accounts/profile/`);
            const data = await resp.json();
            if (data.ok) handleAuthSuccess();
        } catch (e) { /* not authenticated */ }
    }

    // Listen for postMessage from SSO popup
    window.addEventListener('message', (event) => {
        if (event.origin !== window.location.origin) return;
        if (!event.data || event.data.type !== 'sso_complete') return;
        clearInterval(ssoPopupTimer);
        ssoPopup = null;
        if (event.data.success) handleAuthSuccess();
    });

    // --- Close handlers ---
    const closeBtn = authOverlay.querySelector('.modal-close');
    if (closeBtn) {
        closeBtn.removeAttribute('onclick');
        closeBtn.addEventListener('click', resetAuth);
    }

    authOverlay.addEventListener('click', (e) => {
        if (e.target === authOverlay) resetAuth();
    });
}

window.addEventListener('load', initAuthModal);

// --------------------------------------------
// 16.5. OPEN DELIVERY WITH PROFILE PRE-FILL
// --------------------------------------------
async function openDeliveryWithProfile(deliveryOverlay) {
    openModal(deliveryOverlay);
    try {
        const resp = await fetch(`/${window.DRJOYS.lang}/accounts/profile/`);
        const data = await resp.json();
        if (data.ok && data.data) {
            const d = data.data;
            const set = (id, val) => { const el = document.getElementById(id); if (el && val) el.value = val; };
            set('deliveryFirstName', d.first_name);
            set('deliveryLastName', d.last_name);
            set('deliveryPhone', d.phone);
            set('deliveryEmail', d.email);
        }
    } catch (e) {
        // Profile fetch failed — form stays empty, user fills manually
    }
}

// --------------------------------------------
// 17. DELIVERY MODAL — форма → checkout API → успех
// --------------------------------------------
function initDeliveryModal() {
    const deliveryOverlay = document.getElementById('modalDelivery');
    if (!deliveryOverlay) return;

    const form = document.getElementById('deliveryForm');
    const submitBtn = form ? form.querySelector('button[type="submit"]') : null;

    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            // Clear previous errors
            form.querySelectorAll('.modal-error').forEach(el => el.remove());

            const data = {
                first_name: form.querySelector('#deliveryFirstName')?.value || '',
                last_name: form.querySelector('#deliveryLastName')?.value || '',
                phone: form.querySelector('#deliveryPhone')?.value || '',
                email: form.querySelector('#deliveryEmail')?.value || '',
                city: form.querySelector('#deliveryCity')?.value || '',
                address: [
                    form.querySelector('#deliveryStreet')?.value || '',
                    form.querySelector('#deliveryHouse')?.value || '',
                    form.querySelector('#deliveryApt')?.value || '',
                ].filter(Boolean).join(', '),
            };

            if (submitBtn) submitBtn.disabled = true;
            const result = await apiPost('/orders/checkout/', data);
            if (submitBtn) submitBtn.disabled = false;

            if (result.ok) {
                updateBadges(0, null);

                if (result.payment_url) {
                    // Редирект на платёжную страницу VTB
                    window.location.href = result.payment_url;
                } else {
                    // Fallback — показать модалку успеха
                    closeModal(deliveryOverlay);
                    form.reset();
                    const successModal = document.getElementById('modalSuccess');
                    if (successModal) {
                        const sym = window.DRJOYS?.currencySymbol || '₸';
                        const title = document.getElementById('successTitle');
                        const text = document.getElementById('successText');
                        if (title) title.innerHTML = window.DRJOYS.i18n.orderPlaced;
                        if (text) text.textContent = `${window.DRJOYS.i18n.orderSummary} #${result.order_number} ${window.DRJOYS.i18n.orderSumPrefix} ${parseFloat(result.total).toLocaleString('ru-RU')} ${sym}`;
                        setTimeout(() => openModal(successModal), 200);
                    }
                }
            } else {
                // Show errors
                if (result.errors) {
                    for (const [field, msg] of Object.entries(result.errors)) {
                        const input = form.querySelector(`[name="${field}"]`);
                        if (input) {
                            const errEl = document.createElement('p');
                            errEl.className = 'modal-error text-xs text-red-500 mt-1';
                            errEl.textContent = msg;
                            input.parentElement.appendChild(errEl);
                        }
                    }
                } else if (result.error) {
                    const errEl = document.createElement('p');
                    errEl.className = 'modal-error text-xs text-red-500 mt-1';
                    errEl.textContent = result.error;
                    form.prepend(errEl);
                }
            }
        });
    }

    // Close on overlay click
    deliveryOverlay.addEventListener('click', (e) => {
        if (e.target === deliveryOverlay) closeModal(deliveryOverlay);
    });
}

window.addEventListener('load', initDeliveryModal);

// --------------------------------------------
// 18. DROPDOWN ВЫБОРА РЕГИОНА
// --------------------------------------------
function initRegionDropdown() {
    const dropdown = document.getElementById('regionDropdown');
    const btn = document.getElementById('regionSwitcherBtn');
    const menu = document.getElementById('regionMenu');
    if (!dropdown || !btn || !menu) return;

    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = !menu.classList.contains('hidden');
        if (isOpen) {
            menu.classList.add('hidden');
            dropdown.classList.remove('open');
        } else {
            menu.classList.remove('hidden');
            dropdown.classList.add('open');
        }
    });

    // Закрытие по клику вне dropdown
    document.addEventListener('click', (e) => {
        if (!dropdown.contains(e.target)) {
            menu.classList.add('hidden');
            dropdown.classList.remove('open');
        }
    });

    // Автопоказ модалки при первом визите (нет cookie)
    const regionModal = document.getElementById('modalRegion');
    if (regionModal && !regionModal.classList.contains('hidden')) {
        openModal(regionModal);
    }
}

// --------------------------------------------
// 19. ВЫПАДАЮЩЕЕ МЕНЮ ЯЗЫКА
// --------------------------------------------
function initLangDropdown() {
    const dropdown = document.getElementById('langDropdown');
    const btn = document.getElementById('langSwitcherBtn');
    const menu = document.getElementById('langMenu');
    if (!dropdown || !btn || !menu) return;

    // Toggle dropdown
    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = !menu.classList.contains('hidden');
        if (isOpen) {
            menu.classList.add('hidden');
            dropdown.classList.remove('open');
        } else {
            menu.classList.remove('hidden');
            dropdown.classList.add('open');
        }
    });

    // Выбор языка — ссылки с href уже ведут на /kk/..., /en/..., /ru/...
    // Навигация происходит через обычный переход по <a href>.

    // Закрытие по клику вне dropdown
    document.addEventListener('click', (e) => {
        if (!dropdown.contains(e.target)) {
            menu.classList.add('hidden');
            dropdown.classList.remove('open');
        }
    });
}

window.addEventListener('load', initRegionDropdown);
window.addEventListener('load', initLangDropdown);

