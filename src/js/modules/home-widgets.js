// --------------------------------------------
// 4. АНИМАЦИЯ БИЕНИЯ СЕРДЦА С КУЛЬМИНАЦИЕЙ
// --------------------------------------------
export function initHeartbeat() {
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

// --------------------------------------------
// 5. FAQ АККОРДЕОН
// --------------------------------------------
export function initFAQ() {
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

// --------------------------------------------
// 20. HERO TITLE — подгонка под 85% ширины экрана (мобайл)
// --------------------------------------------
// Заголовок приходит на трёх языках и длина строк везде разная, поэтому
// фиксированный размер либо не дотягивает до края, либо вылезает.
// Считаем размер от самой длинной строки: она занимает ровно 85% ширины,
// короткие строки наследуют тот же font-size и остаются пропорционально уже.
export function initHeroTitleFit() {
    const title = document.querySelector('.hero-title');
    if (!title) return;
    const lines = title.querySelectorAll('.hero-title-line');
    if (!lines.length) return;

    const mobile = window.matchMedia('(max-width: 767px)');
    const RATIO = 0.85;
    const BASE = 100;       // опорный размер для замера, px
    const MIN = 10;
    const MAX = 80;
    const range = document.createRange();

    function fit() {
        if (!mobile.matches) {
            title.style.removeProperty('--hero-title-size');
            return;
        }
        // Меряем всегда от одного и того же опорного размера, иначе результат
        // зависел бы от предыдущего прогона и полз при каждом ресайзе.
        // Промежуточный размер не успевает отрисоваться: запись стиля, замер
        // и финальная запись происходят внутри одной задачи, до отрисовки.
        title.style.setProperty('--hero-title-size', BASE + 'px');

        let widest = 0;
        lines.forEach((line) => {
            range.selectNodeContents(line);
            widest = Math.max(widest, range.getBoundingClientRect().width);
        });

        if (!widest) {
            title.style.removeProperty('--hero-title-size');
            return;
        }

        const target = document.documentElement.clientWidth * RATIO;
        const size = Math.min(Math.max((BASE * target) / widest, MIN), MAX);
        title.style.setProperty('--hero-title-size', size.toFixed(2) + 'px');
    }

    fit();
    // Benzin — подключаемый шрифт: до его загрузки ширина считается по фолбэку
    if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(fit);
    }

    let raf = null;
    function schedule() {
        if (raf) cancelAnimationFrame(raf);
        raf = requestAnimationFrame(() => { raf = null; fit(); });
    }
    window.addEventListener('resize', schedule);
    window.addEventListener('orientationchange', schedule);
    mobile.addEventListener('change', schedule);
}
