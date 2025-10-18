/**
 * LoginUtilities
 * Utility methods for login functionality
 */
class LoginUtilities {
    /**
     * Generate a CSRF token for OAuth state parameter
     * @returns {string} Random CSRF token
     */
    static generateCSRFToken() {
        return crypto.randomUUID().replace(/-/g, '');
    }

    /**
     * Store CSRF token in localStorage
     * @param {string} token - CSRF token to store
     */
    static storeCSRFToken(token) {
        localStorage.setItem('latestCSRFToken', token);
    }

    /**
     * Build OAuth authorization URL
     * @param {Object} providerInfo - Provider configuration
     * @param {string} state - CSRF token
     * @returns {string} Complete OAuth URL
     */
    static buildOAuthURL(providerInfo, state) {
        const { client_id, auth_meta_url, auth_scope, auth_redirect_uri } = providerInfo;
        return `${auth_meta_url}?scope=${auth_scope}&response_type=code&access_type=offline&state=${state}&redirect_uri=${auth_redirect_uri}&client_id=${client_id}`;
    }

    /**
     * Parse URL parameters
     * @returns {Object} Object with auth_result and error_message
     */
    static parseURLParameters() {
        const urlParams = new URLSearchParams(window.location.search);
        return {
            authResult: urlParams.get('auth_result'),
            errorMessage: urlParams.get('error_message')
        };
    }

    /**
     * Get provider info from global config
     * @param {string} provider - Provider name (google, github)
     * @returns {Object|null} Provider configuration or null
     */
    static getProviderInfo(provider) {
        if (!window.OAUTH_CONFIG || !window.OAUTH_CONFIG[provider]) {
            console.error(`Provider ${provider} not found in OAUTH_CONFIG`);
            return null;
        }
        return window.OAUTH_CONFIG[provider];
    }

    /**
     * Show notification using the global notification system
     * @param {string} type - Notification type (success, error, info, warning)
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
 * LoginHandler
 * Handles login page functionality including OAuth flow and notifications
 */
class LoginHandler {
    /**
     * Initialize the login handler
     */
    constructor() {
        console.log('LoginHandler initialized');
        this.googleBtn = null;
        this.githubBtn = null;
    }

    /**
     * Handle OAuth and validation errors
     * Shows error notification without redirecting (already on login page)
     * @param {string} errorMessage - Error message to display
     */
    handleError(errorMessage) {
        LoginUtilities.showNotification('error', 'Login Error', errorMessage, 5000);
        // No redirect needed - already on login page
    }

    /**
     * Initiate OAuth flow for a provider
     * @param {string} provider - Provider name (google, github)
     */
    initiateOAuth(provider) {
        // Get provider info
        const providerInfo = LoginUtilities.getProviderInfo(provider);
        if (!providerInfo) {
            this.handleError(`Login with ${provider} is not supported.`);
            return; // Stop execution if provider not found
        }
        // Generate and store CSRF token
        const state = LoginUtilities.generateCSRFToken();
        LoginUtilities.storeCSRFToken(state);
        // Build OAuth URL
        const authURL = LoginUtilities.buildOAuthURL(providerInfo, state);
        // Redirect to OAuth provider
        console.log(`Redirecting to ${provider} OAuth...`);
        window.location.assign(authURL);
    }

    /**
     * Setup event listeners for login buttons
     */
    setupEventListeners() {
        if (this.googleBtn) {
            this.googleBtn.addEventListener('click', (e) => {
                e.preventDefault();
                console.log('Google login button clicked!');
                this.initiateOAuth('google');
            });
        }

        if (this.githubBtn) {
            this.githubBtn.addEventListener('click', (e) => {
                e.preventDefault();
                console.log('GitHub login button clicked!');
                this.initiateOAuth('github');
            });
        }
    }

    /**
     * Handle authentication results from URL parameters
     */
    handleAuthResults() {
        const { authResult, errorMessage } = LoginUtilities.parseURLParameters();

        if (!authResult) {
            LoginUtilities.showNotification('info', 'Welcome!', 'Choose your preferred login method below', 3000);
            return;
        }

        switch (authResult) {
            case 'success':
                LoginUtilities.showNotification('success', 'Login Successful!', 'Welcome to BrowseTerm!', 4000);
                break;
            case 'error':
                LoginUtilities.showNotification('error', 'Login Failed', errorMessage || 'Authentication failed. Please try again.', 10000);
                break;
            case 'cancelled':
                LoginUtilities.showNotification('warning', 'Login Cancelled', 'You cancelled the authentication process', 4000);
                break;
            default:
                LoginUtilities.showNotification('error', 'Login Error', 'Unknown authentication result', 5000);
        }
    }

    /**
     * Initialize login page
     */
    init() {
        // Get button elements
        this.googleBtn = document.querySelector('.btn-google');
        this.githubBtn = document.querySelector('.btn-github');
        // Setup event listeners
        this.setupEventListeners();
        // Handle URL parameters (auth results)
        this.handleAuthResults();
    }
}


document.addEventListener('DOMContentLoaded', function() {
    console.log('Login page class DOM is ready');
    const loginHandler = new LoginHandler();
    loginHandler.init();
});
