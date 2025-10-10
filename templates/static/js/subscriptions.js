// Subscriptions page JavaScript
console.log('Subscriptions page loaded successfully!');

// Dummy JSON data for subscription plans
const dummyPlansData = {
    "plans": [
        {
            "id": "free",
            "name": "Free",
            "price": 0,
            "currency": "Rs.",
            "period": "",
            "cpu": "1 GB",
            "memory": "1 GB",
            "max_terminals": 1,
            "extra": null,
            "popular": false,
            "comingSoon": false
        },
        {
            "id": "basic",
            "name": "Basic",
            "price": 200,
            "currency": "Rs.",
            "period": "per month",
            "cpu": "1 GB",
            "memory": "1 GB",
            "max_terminals": 10,
            "extra": null,
            "popular": true,
            "comingSoon": false
        },
        {
            "id": "pro",
            "name": "Pro",
            "price": 700,
            "currency": "Rs.",
            "period": "per month",
            "cpu": "Configurable",
            "memory": "Configurable",
            "max_terminals": 30,
            "extra": "Coming Soon",
            "popular": false,
            "comingSoon": true
        }
    ]
};

// Dummy current plan data
const dummyCurrentPlanData = {
    "currentPlan": {
        "id": "free"
    }
};

// Function to simulate API call for subscription plans
async function fetchSubscriptionPlans() {
    console.log('Fetching subscription plans...');

    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 1000));

    // Return dummy data (in real app, this would be a fetch() call)
    return dummyPlansData;
}

// Function to simulate API call for current plan
async function fetchCurrentPlan() {
    console.log('Fetching current plan...');

    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 500));

    // Return dummy data (in real app, this would be a fetch() call)
    return dummyCurrentPlanData;
}

// Function to render subscription card
function renderSubscriptionCard(plan, currentPlanId) {
    const popularClass = plan.popular ? 'popular' : '';
    const popularBadge = plan.popular ? '<div class="popular-badge">Most Popular</div>' : '';
    const isCurrentPlan = plan.id === currentPlanId;

    // Build features based on plan fields
    const featuresHTML = `
        <div class="feature">
            <span class="feature-icon">⌨</span>
            <span class="feature-text">${plan.max_terminals} terminal${plan.max_terminals > 1 ? 's' : ''} per user</span>
        </div>
        <div class="feature">
            <span class="feature-icon">💾</span>
            <span class="feature-text">${plan.memory} memory</span>
        </div>
        <div class="feature">
            <span class="feature-icon">⚡</span>
            <span class="feature-text">${plan.cpu} CPU</span>
        </div>
        ${plan.extra ? `
            <div class="feature coming-soon">
                <span class="feature-text"><strong>${plan.extra}</strong></span>
            </div>
        ` : ''}
    `;

    // Determine button text and visibility
    let buttonHTML = '';
    if (!isCurrentPlan) {
        const buttonText = plan.price === 0 ? 'Get Started' : 'Select Plan';
        buttonHTML = `<button class="buy-btn" data-plan-id="${plan.id}">${buttonText}</button>`;
    } else {
        buttonHTML = '<div class="current-plan-badge">Current Plan</div>';
    }

    return `
        <div class="subscription-card ${popularClass}" data-plan-id="${plan.id}">
            ${popularBadge}
            <div class="card-header">
                <h3>${plan.name}</h3>
                <div class="price">
                    <span class="currency">${plan.currency}</span>
                    <span class="amount">${plan.price}</span>
                    ${plan.period ? `<span class="period">${plan.period}</span>` : ''}
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
        const [plansData, currentPlanData] = await Promise.all([
            fetchSubscriptionPlans(),
            fetchCurrentPlan()
        ]);

        console.log('Subscription plans loaded:', plansData.plans);
        console.log('Current plan:', currentPlanData.currentPlan);

        renderSubscriptionCards(plansData.plans, currentPlanData.currentPlan.id);
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