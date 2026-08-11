import { apiPost } from '../lib/api.js';
import { openModal, closeModal } from '../lib/modal-core.js';
import { updateBadges } from '../lib/badges.js';

// --------------------------------------------
// 16.5. OPEN DELIVERY WITH PROFILE PRE-FILL
// --------------------------------------------
export async function openDeliveryWithProfile(deliveryOverlay) {
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
export function initDeliveryModal() {
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

    // Закрытие по клику на фон — на делегированном слушателе lib/modal-core.js,
    // своего обработчика здесь нет (дубль такого рода был причиной бага JR-12)
}
