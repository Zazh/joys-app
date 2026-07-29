import { apiPost } from './api.js';

// Отправка формы заявки на inquiries API. Одна на все формы: на странице контактов
// (#contactForm) и в модалках (.interactive-modal-form) — различаются только тем,
// что показывать после успеха и нужна ли своя проверка перед отправкой.
//
// Разметка договаривается с кодом через атрибуты:
//   data-form-slug      — slug InquiryForm, из него собирается URL
//   data-error-network  — текст на случай, когда ответа нет вовсе
//   [data-error-for=<ключ поля|__all__>] — куда положить текст ошибки
export function initInquiryForm(form, { validate, onSuccess }) {
    const submitBtn = form.querySelector('button[type="submit"]');

    function clearErrors() {
        form.querySelectorAll('[data-error-for]').forEach(el => {
            el.textContent = '';
            el.classList.add('hidden');
        });
        form.querySelectorAll('[aria-invalid]').forEach(el => el.removeAttribute('aria-invalid'));
    }

    // Показывает ошибку и возвращает поле, к которому она относится, — для фокуса
    function showError(key, message) {
        const errorEl = form.querySelector(`[data-error-for="${key}"]`);
        if (errorEl) {
            // Сначала показываем блок, потом пишем текст: скринридер объявляет
            // role="alert" по изменению содержимого, а в display:none его не видно
            errorEl.classList.remove('hidden');
            errorEl.textContent = message;
        }
        const input = form.querySelector(`[name="${key}"]`);
        if (input) input.setAttribute('aria-invalid', 'true');
        return input;
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        clearErrors();

        // Своя проверка формы (согласие на обработку данных) — до запроса
        const localError = validate?.();
        if (localError) {
            showError(localError.key, localError.message)?.focus();
            return;
        }

        const payload = {};
        new FormData(form).forEach((value, key) => { payload[key] = value; });

        // Двойной клик не должен слать вторую заявку
        if (submitBtn) submitBtn.disabled = true;
        try {
            const result = await apiPost(`/api/inquiries/${form.dataset.formSlug}/submit/`, { data: payload });
            if (result.ok) {
                onSuccess(result);
                return;
            }

            // Ошибки полей приходят как {data: {key: text}} или {key: text}
            const fieldErrors = result.errors?.data || result.errors || {};
            let firstInvalid = null;
            for (const [key, message] of Object.entries(fieldErrors)) {
                const input = showError(key, Array.isArray(message) ? message[0] : message);
                firstInvalid = firstInvalid || input;
            }
            if (firstInvalid) {
                firstInvalid.focus();
            } else {
                // Лимит заявок, антиспам, устаревший CSRF — ошибка формы целиком
                showError('__all__', result.error || form.dataset.errorNetwork);
            }
        } catch (err) {
            console.error('Inquiry submit error:', err);
            showError('__all__', form.dataset.errorNetwork);
        } finally {
            if (submitBtn) submitBtn.disabled = false;
        }
    });
}
