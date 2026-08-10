// --------------------------------------------
// 3. ПЕРЕКЛЮЧЕНИЕ КАРТИНОК ТОВАРОВ
// --------------------------------------------
export function initProductImageSlider() {
    const productCards = document.querySelectorAll('.product-card_picture');

    productCards.forEach(card => {
        const images = card.querySelectorAll('.product-image');
        const imagesCount = images.length;

        if (imagesCount === 0) return;
        if (imagesCount === 1) { images[0].classList.add('active'); return; }

        // Не-первые фото отрендерены с data-src — грузим при первом наведении/касании
        let hydrated = false;
        function hydrateImages() {
            if (hydrated) return;
            hydrated = true;
            images.forEach(img => {
                if (img.dataset.src && !img.getAttribute('src')) {
                    img.src = img.dataset.src;
                }
            });
        }
        card.addEventListener('mouseenter', hydrateImages, { once: true });

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
            hydrateImages();
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

// --------------------------------------------
// 8. СЛАЙДЕР ПРОДУКТА С АВТОПРОКРУТКОЙ
// --------------------------------------------
export function initProductSlider() {
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

        if (imagesCount <= 1) {
            // Одно фото: листать нечего, но кнопка play/pause с прогрессом
            // стоит в вёрстке статически — без этого висела бы мёртвой
            slider.querySelector('.slider-progress-wrapper')?.remove();
            return;
        }

        // Создаем индикаторы (кликабельные)
        indicatorsContainer.innerHTML = '';
        const indicators = [];
        for (let i = 0; i < imagesCount; i++) {
            const indicator = document.createElement('button');
            indicator.type = 'button';
            indicator.classList.add('indicator');
            indicator.setAttribute('aria-label', `Слайд ${i + 1}`);
            indicatorsContainer.appendChild(indicator);
            indicators.push(indicator);
        }

        // Кнопки prev/next (видны на десктопе, скрыты на мобайле)
        const prevBtn = document.createElement('button');
        prevBtn.type = 'button';
        prevBtn.className = 'slider-arrow slider-arrow-prev';
        prevBtn.setAttribute('aria-label', 'Предыдущий слайд');
        prevBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>';
        slider.appendChild(prevBtn);

        const nextBtn = document.createElement('button');
        nextBtn.type = 'button';
        nextBtn.className = 'slider-arrow slider-arrow-next';
        nextBtn.setAttribute('aria-label', 'Следующий слайд');
        nextBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>';
        slider.appendChild(nextBtn);

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
            if (!playPauseBtn) return;
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
                if (progressBar) progressBar.style.strokeDashoffset = 100;
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

        // МОБИЛЬНЫЙ: Клик на картинку - toggle play/pause (только если есть autoplay-контролы)
        if (playPauseBtn) {
            slider.addEventListener('click', (e) => {
                if (e.target.closest('.slider-play-pause')) return;

                if (window.innerWidth < 1024) {
                    togglePlayPause();
                }
            });
        }

        // Прыжок к конкретному слайду (сбрасываем прогресс-кружок)
        function goTo(index) {
            if (index === currentIndex) return;
            showImage(index);
            stopAutoplay();
            if (progressBar) progressBar.style.strokeDashoffset = 100;
            if (isPlaying) startAutoplay();
        }
        function goPrev() {
            goTo((currentIndex - 1 + imagesCount) % imagesCount);
        }
        function goNext() {
            goTo((currentIndex + 1) % imagesCount);
        }

        // Клики на стрелки
        prevBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            goPrev();
        });
        nextBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            goNext();
        });

        // Клики на индикаторы
        indicators.forEach((indicator, i) => {
            indicator.addEventListener('click', (e) => {
                e.stopPropagation();
                goTo(i);
            });
        });

        // Универсальный свайп: touch (мобайл) + mouse drag (десктоп)
        const swipeThreshold = 50;
        let dragStartX = null;
        let dragMoved = false;

        function applySwipe(diff) {
            if (diff < -swipeThreshold) {
                goNext();
            } else if (diff > swipeThreshold) {
                goPrev();
            }
        }

        // Touch
        slider.addEventListener('touchstart', (e) => {
            dragStartX = e.changedTouches[0].screenX;
        }, { passive: true });
        slider.addEventListener('touchend', (e) => {
            if (dragStartX === null) return;
            applySwipe(e.changedTouches[0].screenX - dragStartX);
            dragStartX = null;
        });

        // Mouse drag — слушаем mouseup/mousemove на document, чтобы свайп
        // срабатывал, даже если курсор вышел за пределы слайдера до отпускания
        const onDocMouseMove = (e) => {
            if (dragStartX === null) return;
            if (Math.abs(e.clientX - dragStartX) > 5) {
                dragMoved = true;
            }
        };
        const onDocMouseUp = (e) => {
            if (dragStartX === null) return;
            const startX = dragStartX;
            dragStartX = null;
            document.removeEventListener('mousemove', onDocMouseMove);
            document.removeEventListener('mouseup', onDocMouseUp);
            if (dragMoved) {
                applySwipe(e.clientX - startX);
            }
            dragMoved = false;
        };

        slider.addEventListener('mousedown', (e) => {
            if (e.button !== 0) return;
            if (e.target.closest('.slider-play-pause')) return;
            if (e.target.closest('.slider-arrow')) return;
            if (e.target.closest('.indicator')) return;
            dragStartX = e.clientX;
            dragMoved = false;
            document.addEventListener('mousemove', onDocMouseMove);
            document.addEventListener('mouseup', onDocMouseUp);
            e.preventDefault();
        });
        slider.addEventListener('dragstart', (e) => e.preventDefault());
    });
}

// --------------------------------------------
// 9. DRAG КАРУСЕЛЬ С КАСТОМНЫМ КУРСОРОМ
// --------------------------------------------
export function initDragCarousel() {
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
