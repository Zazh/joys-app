import { apiPost } from '../lib/api.js';
import { closeModal, goToStep } from '../lib/modal-core.js';
import { escapeHtml } from '../lib/escape.js';
import { formatMoney } from '../lib/money.js';

// --------------------------------------------
// 15. PROFILE MODAL — навигация по шагам
// --------------------------------------------
export function initProfileModal() {
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
                            <p class="text-sm font-bold">#${escapeHtml(order.number)}</p>
                            <p class="text-[10px] text-gray-500">${formatDate(order.created_at)}</p>
                        </div>
                        <span class="order-status ${statusCls} text-[10px] font-bold px-2 py-0.5 rounded-full">${escapeHtml(order.status_display)}</span>
                    </div>
                    <p class="text-xs font-benzin text-red-500 mt-2">${escapeHtml(formatMoney(amount, symbol))}</p>
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
                        <p class="text-xs font-bold">${escapeHtml(item.product_name)}</p>
                        <p class="text-[10px] text-gray-500">${window.DRJOYS.i18n.sizeLbl}: ${escapeHtml(item.size_name)} &middot; ${escapeHtml(item.quantity)} ${window.DRJOYS.i18n.pcsLbl}</p>
                        <p class="text-xs font-bold mt-1">${escapeHtml(formatMoney(item.subtotal, symbol))}</p>
                    </div>
                </div>
            `;
        });

        contentEl.innerHTML = `
            <div class="flex justify-between items-center">
                <p class="text-xs text-gray-500">${formatDate(order.created_at)}</p>
                <span class="order-status ${statusCls} text-[10px] font-bold px-2 py-0.5 rounded-full">${escapeHtml(order.status_display)}</span>
            </div>
            <div class="flex flex-col divide-y divide-stone-50">
                ${itemsHtml}
            </div>
            <div>
                <p class="text-xs font-bold pb-1">${window.DRJOYS.i18n.deliveryAddr}</p>
                <p class="text-xs text-gray-500">${escapeHtml(order.city)}, ${escapeHtml(order.address)}</p>
            </div>
            <div class="flex justify-between items-center pt-2 border-t border-stone-50">
                <span class="font-benzin uppercase text-sm">${window.DRJOYS.i18n.totalLbl}</span>
                <span class="font-benzin text-red-500">${escapeHtml(formatMoney(amount, symbol))}</span>
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
