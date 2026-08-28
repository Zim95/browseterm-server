/**
 * PaymentUtilities
 * Utility methods for the payment page
 */
class PaymentUtilities {
    /**
     * Get the server-resolved plan from window object (passed from backend template)
     * @returns {Object|null} Selected plan, or null if plan_id didn't resolve to anything
     */
    static getSelectedPlanFromTemplate() {
        const plan = window.selectedPlan;
        if (!plan || Object.keys(plan).length === 0) {
            return null;
        }
        return plan;
    }

    /**
     * GST rate applied to the displayed breakdown.
     * Placeholder rate (India standard SaaS/cloud-service rate) until real tax/pricing rules
     * exist server-side. Display-only: /create-payment still hardcodes the actual charge for v0.
     */
    static GST_RATE = 0.18;

    /**
     * Compute the base/GST/total breakdown for a plan.
     * @param {Object} plan - Subscription plan (amount is a "499.00"-style string)
     * @returns {{base: number, gst: number, total: number, currency: string}}
     */
    static computeBreakdown(plan) {
        const base = parseFloat(plan.amount) || 0;
        const gst = base * PaymentUtilities.GST_RATE;
        const total = base + gst;
        return { base, gst, total, currency: plan.currency || '' };
    }

    /**
     * Format a numeric amount to 2 decimal places for display.
     * @param {number} value
     * @returns {string}
     */
    static formatAmount(value) {
        return value.toFixed(2);
    }

    /**
     * Generate a fresh idempotency key.
     * One per page load/checkout attempt - reused across every Pay click/retry on this page,
     * never regenerated mid-attempt (see PAYMENTS.md follow-up: this page should "create the
     * idempotency key and use that all the time").
     * @returns {string}
     */
    static generateIdempotencyKey() {
        if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
            return crypto.randomUUID();
        }
        // Fallback for environments without crypto.randomUUID (older browsers/non-HTTPS contexts)
        return 'idem-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);
    }

    /**
     * Show notification
     * @param {string} type - Notification type
     * @param {string} title - Notification title
     * @param {string} message - Notification message
     * @param {number} duration - Duration in milliseconds
     */
    static showNotification(type, title, message, duration) {
        if (typeof window.notifications === 'undefined' || window.notifications === null) {
            console.warn('Notification system not available');
            return;
        }
        if (typeof window.notifications[type] !== 'function') {
            console.warn('Notification type not available');
            return;
        }
        window.notifications[type](title, message, duration);
    }
}

/**
 * PaymentHandler
 * Handles payment page functionality
 */
class PaymentHandler {
    constructor() {
        this.plan = null;
        this.idempotencyKey = null;
        this.elements = {};
    }

    /**
     * Initialize payment page
     */
    init() {
        this.elements = {
            paymentBody: document.getElementById('paymentBody')
        };

        this.plan = PaymentUtilities.getSelectedPlanFromTemplate();

        if (!this.plan) {
            this.renderPlanNotFound();
            return;
        }

        // Minted once for this checkout attempt, reused for every Pay click/retry below.
        this.idempotencyKey = PaymentUtilities.generateIdempotencyKey();

        this.render();
    }

    /**
     * Render the "plan not found" state (e.g. missing/invalid plan_id)
     */
    renderPlanNotFound() {
        this.elements.paymentBody.innerHTML = `
            <div class="loading-message error">
                Could not find that plan. <a href="/subscriptions">Go back and pick a plan</a>.
            </div>
        `;
    }

    /**
     * Render the checkout card
     */
    render() {
        const breakdown = PaymentUtilities.computeBreakdown(this.plan);

        this.elements.paymentBody.innerHTML = `
            <div class="details-card payment-card">
                <div class="detail-item">
                    <label class="detail-label">Plan</label>
                    <span class="detail-value">${this.plan.name}</span>
                </div>
                <div class="detail-item">
                    <label class="detail-label">Amount</label>
                    <span class="detail-value">${breakdown.currency}${PaymentUtilities.formatAmount(breakdown.base)}</span>
                </div>
                <div class="detail-item">
                    <label class="detail-label">GST (18%)</label>
                    <span class="detail-value">${breakdown.currency}${PaymentUtilities.formatAmount(breakdown.gst)}</span>
                </div>
                <div class="detail-item total-row">
                    <label class="detail-label">Total</label>
                    <span class="detail-value">${breakdown.currency}${PaymentUtilities.formatAmount(breakdown.total)}</span>
                </div>
            </div>
            <button class="buy-btn pay-btn" id="payBtn">Pay</button>
            <p class="idempotency-hint">Idempotency key: <code>${this.idempotencyKey}</code></p>
        `;

        document.getElementById('payBtn').addEventListener('click', () => this.handlePayClick());
    }

    /**
     * Handle Pay button click - calls /create-payment with the plan and this attempt's
     * idempotency key.
     */
    async handlePayClick() {
        const payBtn = document.getElementById('payBtn');
        payBtn.disabled = true;
        payBtn.textContent = 'Processing...';

        try {
            const response = await fetch('/create-payment', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    plan_id: this.plan.id,
                    idempotency_key: this.idempotencyKey,
                }),
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'Payment failed');
            }

            PaymentUtilities.showNotification(
                'success',
                'Payment successful',
                `Payment ID: ${result.payment_id}`,
                6000
            );
        } catch (error) {
            console.error('Error processing payment:', error);
            PaymentUtilities.showNotification(
                'error',
                'Payment Failed',
                error.message || 'Could not process payment. Please try again.',
                6000
            );
        } finally {
            payBtn.disabled = false;
            payBtn.textContent = 'Pay';
        }
    }
}

// Initialize payment handler when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    const paymentHandler = new PaymentHandler();
    paymentHandler.init();
});
