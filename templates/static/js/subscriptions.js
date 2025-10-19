/**
 * SubscriptionUtilities
 * Utility methods for subscription page functionality
 */
class SubscriptionUtilities {
    /**
     * Get subscription plans from window object (passed from backend)
     * @returns {Array} Array of subscription plans
     */
    static getPlansFromTemplate() {
        return window.subscriptionPlans || [];
    }

    /**
     * Get current subscription plan from window object
     * @returns {Object} Current subscription plan
     */
    static getCurrentPlanFromTemplate() {
        return window.currentSubscriptionPlan || {};
    }

    /**
     * Format CPU display
     * @param {string|number} cpuLimit - CPU limit value
     * @returns {string} Formatted CPU display
     */
    static formatCPUDisplay(cpuLimit) {
        return cpuLimit ? `${cpuLimit}` : 'Configurable';
    }

    /**
     * Format memory display
     * @param {string|number} memoryLimit - Memory limit value
     * @returns {string} Formatted memory display
     */
    static formatMemoryDisplay(memoryLimit) {
        return memoryLimit ? `${memoryLimit}` : 'Configurable';
    }

    /**
     * Format period display
     * @param {number} durationDays - Duration in days
     * @returns {string} Formatted period display
     */
    static formatPeriodDisplay(durationDays) {
        return durationDays > 0 ? `per ${durationDays} days` : '';
    }

    /**
     * Check if plan is popular
     * @param {Object} plan - Subscription plan
     * @returns {boolean} True if plan is popular
     */
    static isPlanPopular(plan) {
        return plan.name === 'Basic';
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
 * SubscriptionHandler
 * Handles subscription page functionality
 */
class SubscriptionHandler {
    /**
     * Initialize the subscription handler
     */
    constructor() {
        console.log('SubscriptionHandler initialized');
        this.elements = {};
        this.plans = [];
        this.currentPlan = null;
    }

    /**
     * Initialize subscription page
     */
    async init() {
        console.log('Subscriptions page loaded successfully!');

        // Cache DOM elements
        this.cacheElements();

        // Load subscription plans
        await this.loadSubscriptionPlans();
    }

    /**
     * Cache DOM elements
     */
    cacheElements() {
        this.elements = {
            subscriptionCards: document.getElementById('subscriptionCards')
        };
    }

    /**
     * Load subscription plans
     */
    async loadSubscriptionPlans() {
        try {
            console.log('Loading subscription plans...');

            // Get plans and current plan from template
            this.plans = SubscriptionUtilities.getPlansFromTemplate();
            this.currentPlan = SubscriptionUtilities.getCurrentPlanFromTemplate();

            console.log('Subscription plans loaded:', this.plans);
            console.log('Current plan:', this.currentPlan);

            // Render cards
            this.renderSubscriptionCards();

        } catch (error) {
            console.error('Error loading subscription plans:', error);
            this.showError('Error loading subscription plans. Please try again.');
            SubscriptionUtilities.showNotification(
                'error',
                'Loading Error',
                'Failed to load subscription plans',
                5000
            );
        }
    }

    /**
     * Render all subscription cards
     */
    renderSubscriptionCards() {
        if (this.plans.length === 0) {
            this.elements.subscriptionCards.innerHTML = 
                '<div class="loading-message">No subscription plans found.</div>';
            return;
        }

        const cardsHTML = this.plans
            .map(plan => this.renderSubscriptionCard(plan))
            .join('');

        this.elements.subscriptionCards.innerHTML = cardsHTML;

        // Setup event listeners
        this.attachEventListeners();
    }

    /**
     * Render a single subscription card
     * @param {Object} plan - Subscription plan
     * @returns {string} HTML string for card
     */
    renderSubscriptionCard(plan) {
        const isPopular = SubscriptionUtilities.isPlanPopular(plan);
        const popularClass = isPopular ? 'popular' : '';
        const popularBadge = isPopular ? '<div class="popular-badge">Most Popular</div>' : '';
        const isCurrentPlan = plan.id === this.currentPlan.id;

        // Format displays
        const cpuDisplay = SubscriptionUtilities.formatCPUDisplay(plan.cpu_limit_per_container);
        const memoryDisplay = SubscriptionUtilities.formatMemoryDisplay(plan.memory_limit_per_container);
        const periodDisplay = SubscriptionUtilities.formatPeriodDisplay(plan.duration_days);

        // Build features HTML
        const featuresHTML = this.buildFeaturesHTML(plan, cpuDisplay, memoryDisplay);

        // Build button HTML
        const buttonHTML = this.buildButtonHTML(plan, isCurrentPlan);

        return `
            <div class="subscription-card ${popularClass}" data-plan-id="${plan.id}">
                ${popularBadge}
                <div class="card-header">
                    <h3>${plan.name}</h3>
                    <div class="price">
                        <span class="currency">${plan.currency}</span>
                        <span class="amount">${plan.amount}</span>
                        ${periodDisplay ? `<span class="period">${periodDisplay}</span>` : ''}
                    </div>
                </div>
                <div class="card-features">
                    ${featuresHTML}
                </div>
                ${buttonHTML}
            </div>
        `;
    }

    /**
     * Build features HTML for a plan
     * @param {Object} plan - Subscription plan
     * @param {string} cpuDisplay - Formatted CPU display
     * @param {string} memoryDisplay - Formatted memory display
     * @returns {string} Features HTML
     */
    buildFeaturesHTML(plan, cpuDisplay, memoryDisplay) {
        const containerText = plan.max_containers > 1 ? 's' : '';
        
        return `
            <div class="feature">
                <span class="feature-icon">⌨</span>
                <span class="feature-text">${plan.max_containers} container${containerText} per user</span>
            </div>
            <div class="feature">
                <span class="feature-icon">💾</span>
                <span class="feature-text">${memoryDisplay} memory</span>
            </div>
            <div class="feature">
                <span class="feature-icon">⚡</span>
                <span class="feature-text">${cpuDisplay} CPU</span>
            </div>
            ${plan.extra_message ? `
                <div class="feature coming-soon">
                    <span class="feature-icon">✨</span>
                    <span class="feature-text"><strong>${plan.extra_message}</strong></span>
                </div>
            ` : ''}
        `;
    }

    /**
     * Build button HTML for a plan
     * @param {Object} plan - Subscription plan
     * @param {boolean} isCurrentPlan - Whether this is the user's current plan
     * @returns {string} Button HTML
     */
    buildButtonHTML(plan, isCurrentPlan) {
        if (isCurrentPlan) {
            return '<div class="current-plan-badge">Current Plan</div>';
        }

        const buttonText = plan.amount === 0 ? 'Get Started' : 'Select Plan';

        if (plan.is_active === false) {
            return `
                <button class="buy-btn disabled" 
                        data-plan-id="${plan.id}" 
                        data-disabled="true" 
                        title="Not active right now..coming soon">
                    ${buttonText}
                </button>
            `;
        }

        return `<button class="buy-btn" data-plan-id="${plan.id}">${buttonText}</button>`;
    }

    /**
     * Attach event listeners to cards and buttons
     */
    attachEventListeners() {
        // Buy buttons
        const buyBtns = document.querySelectorAll('.buy-btn');
        buyBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const planId = e.target.getAttribute('data-plan-id');
                const isDisabled = e.target.getAttribute('data-disabled') === 'true';
                this.handleBuyButtonClick(planId, isDisabled);
            });
        });

        // Card hover effects
        const cards = document.querySelectorAll('.subscription-card');
        cards.forEach(card => {
            card.addEventListener('mouseenter', () => this.handleCardHover(card, true));
            card.addEventListener('mouseleave', () => this.handleCardHover(card, false));
        });
    }

    /**
     * Handle buy button click
     * @param {string} planId - Plan ID
     * @param {boolean} isDisabled - Whether button is disabled
     */
    handleBuyButtonClick(planId, isDisabled) {
        if (isDisabled) {
            SubscriptionUtilities.showNotification(
                'info',
                'Coming Soon',
                'This plan will be available soon!',
                3000
            );
            return;
        }

        console.log(`Buy button clicked for plan: ${planId}`);
        this.handlePlanPurchase(planId);
    }

    /**
     * Handle card hover effect
     * @param {HTMLElement} card - Card element
     * @param {boolean} isHovering - Whether mouse is hovering
     */
    handleCardHover(card, isHovering) {
        if (isHovering) {
            card.style.transform = 'translateY(-5px)';
        } else {
            if (card.classList.contains('popular')) {
                card.style.transform = 'scale(1.05)';
            } else {
                card.style.transform = 'translateY(0)';
            }
        }
    }

    /**
     * Handle plan purchase
     * @param {string} planId - Plan ID
     */
    handlePlanPurchase(planId) {
        // Find plan details
        const plan = this.plans.find(p => p.id === planId);
        if (!plan) {
            SubscriptionUtilities.showNotification(
                'error',
                'Plan Not Found',
                'Could not find plan details',
                5000
            );
            return;
        }

        // Show confirmation
        const message = `Are you sure you want to purchase the ${plan.name} plan for ${plan.currency}${plan.amount}?`;

        if (confirm(message)) {
            console.log(`User confirmed purchase of ${plan.name} plan`);
            this.processPurchase(plan);
        } else {
            console.log(`User cancelled purchase of ${plan.name} plan`);
            SubscriptionUtilities.showNotification(
                'info',
                'Purchase Cancelled',
                'Plan purchase was cancelled',
                3000
            );
        }
    }

    /**
     * Process plan purchase
     * @param {Object} plan - Subscription plan
     */
    processPurchase(plan) {
        // TODO: Implement actual purchase logic
        // - Redirect to payment gateway
        // - Call API to process subscription
        // - Update user's subscription status

        console.log('Processing purchase for plan:', plan);

        SubscriptionUtilities.showNotification(
            'info',
            'Coming Soon',
            `Thank you for choosing the ${plan.name} plan! Payment processing will be implemented soon.`,
            6000
        );
    }

    /**
     * Show error message in UI
     * @param {string} message - Error message
     */
    showError(message) {
        this.elements.subscriptionCards.innerHTML = 
            `<div class="loading-message error">${message}</div>`;
    }
}

// Initialize subscription handler when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('Subscriptions page DOM is ready');
    const subscriptionHandler = new SubscriptionHandler();
    subscriptionHandler.init();
});
