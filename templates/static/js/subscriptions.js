// Subscriptions page JavaScript
console.log('Subscriptions page loaded successfully!');

const subscriptionPlans = window.subscriptionPlans || [];
const currentSubscriptionPlan = window.currentSubscriptionPlan || {};

// Function to simulate API call for subscription plans
async function getSubscriptionPlans() {
    console.log('Fetching subscription plans...');
    console.log('Subscription plans:', subscriptionPlans);
    // Return subscription plans
    return subscriptionPlans;
}

// Function to simulate API call for current plan
async function getCurrentPlan() {
    console.log('Fetching current plan...');
    console.log('Current plan:', currentSubscriptionPlan);
    // Return current plan
    return currentSubscriptionPlan;
}

// Function to render subscription card
function renderSubscriptionCard(plan, currentPlanId) {
    // Determine if this is the "Basic" plan (most popular)
    const popularClass = plan.name === 'Basic' ? 'popular' : '';
    const popularBadge = plan.name === 'Basic' ? '<div class="popular-badge">Most Popular</div>' : '';
    const isCurrentPlan = plan.id === currentPlanId;
    // Format CPU and memory display
    const cpuDisplay = plan.cpu_limit_per_container ? `${plan.cpu_limit_per_container}` : 'Configurable';
    const memoryDisplay = plan.memory_limit_per_container ? `${plan.memory_limit_per_container}` : 'Configurable';

    // Build features based on plan fields
    const featuresHTML = `
        <div class="feature">
            <span class="feature-icon">⌨</span>
            <span class="feature-text">${plan.max_containers} container${plan.max_containers > 1 ? 's' : ''} per user</span>
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

    // Determine button text and visibility
    let buttonHTML = '';
    if (!isCurrentPlan) {
        const buttonText = plan.amount === 0 ? 'Get Started' : 'Select Plan';
        // Check if plan is active
        if (plan.is_active === false) {
            buttonHTML = `
                <button class="buy-btn disabled" data-plan-id="${plan.id}" data-disabled="true" title="Not active right now..coming soon">
                    ${buttonText}
                </button>
            `;
        } else {
            buttonHTML = `<button class="buy-btn" data-plan-id="${plan.id}">${buttonText}</button>`;
        }
    } else {
        buttonHTML = '<div class="current-plan-badge">Current Plan</div>';
    }
    // Format period display
    const periodDisplay = plan.duration_days > 0 ? `per ${plan.duration_days} days` : '';

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

// Function to render subscription cards
function renderSubscriptionCards(plans, currentPlanId) {
    const subscriptionCards = document.getElementById('subscriptionCards');

    if (plans.length === 0) {
        subscriptionCards.innerHTML = '<div class="loading-message">No subscription plans found.</div>';
        return;
    }

    const cardsHTML = plans.map(plan => renderSubscriptionCard(plan, currentPlanId)).join('');
    subscriptionCards.innerHTML = cardsHTML;

    // Re-attach event listeners to new buttons
    attachEventListeners();
}

// Function to attach event listeners
function attachEventListeners() {
    // Buy buttons
    const buyBtns = document.querySelectorAll('.buy-btn');
    buyBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const planId = this.getAttribute('data-plan-id');
            const isDisabled = this.getAttribute('data-disabled') === 'true';
            
            // If button is disabled, show alert
            if (isDisabled) {
                alert('Not active right now..coming soon');
                return;
            }
            
            console.log(`Buy button clicked for plan: ${planId}`);
            handlePlanPurchase(planId);
        });
    });

    // Card hover effects
    const cards = document.querySelectorAll('.subscription-card');
    cards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-5px)';
        });

        card.addEventListener('mouseleave', function() {
            if (!this.classList.contains('popular')) {
                this.style.transform = 'translateY(0)';
            } else {
                this.style.transform = 'scale(1.05)';
            }
        });
    });
}

// Function to load subscription plans
async function loadSubscriptionPlans() {
    try {
        // Fetch both plans and current plan in parallel
        const [plans, currentPlan] = await Promise.all([
            getSubscriptionPlans(),
            getCurrentPlan()
        ]);

        console.log('Subscription plans loaded:', plans);
        console.log('Current plan:', currentPlan);

        renderSubscriptionCards(plans, currentPlan.id);
    } catch (error) {
        console.error('Error loading subscription plans:', error);
        const subscriptionCards = document.getElementById('subscriptionCards');
        subscriptionCards.innerHTML = '<div class="loading-message">Error loading subscription plans. Please try again.</div>';
    }
}

function handlePlanPurchase(planId) {
    // Show confirmation dialog
    const message = `Are you sure you want to purchase the ${planId} plan?`;

    if (confirm(message)) {
        console.log(`User confirmed purchase of ${planId} plan`);

        // Add actual purchase logic here
        // This could involve:
        // - Redirecting to payment gateway
        // - Calling API to process subscription
        // - Updating user's subscription status

        // For now, just show a success message
        alert(`Thank you for choosing the ${planId} plan! Payment processing will be implemented soon.`);
    } else {
        console.log(`User cancelled purchase of ${planId} plan`);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('Subscriptions page DOM is ready');

    // Load subscription plans from API
    loadSubscriptionPlans();
});