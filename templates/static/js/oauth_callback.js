/**
 * OAuthCallbackHandlerUtilities
 * Utility methods for OAuth callback handling
 */
class OAuthCallbackHandlerUtilities {
    /**
     * Clean up stored state (CSRF token)
     */
    static cleanupState() {
        localStorage.removeItem('latestCSRFToken');
    }

    /**
     * Get authentication endpoint for provider
     * @param {string} provider - Provider name (google, github)
     * @returns {string|null} Endpoint URL or null
     */
    static getEndpoint(provider) {
        const endpoints = {
            'google': '/google-token-exchange',
            'github': '/github-token-exchange'
        };
        return endpoints[provider] || null;
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
 * OAuthCallbackHandler
 * Handles OAuth callback processing, validation, and authentication flow
 */
class OAuthCallbackHandler {
    /**
     * Initialize the OAuth callback handler
     */
    constructor() {
        this.provider = null;
        this.code = null;
        this.state = null;
        console.log('OAuthCallbackHandler initialized');
    }

    /**
     * Parse URL parameters and set the class properties
     */
    parseUrlParameters() {
        const urlParams = new URLSearchParams(window.location.search);
        this.code = urlParams.get('code');
        this.state = urlParams.get('state');
        this.error = urlParams.get('error');
        this.errorDescription = urlParams.get('error_description');
    }

    /**
     * Handle OAuth and validation errors
     * @param {string} error - Error code
     * @param {string} description - Error description
     */
    handleError(errorMessage) {
        OAuthCallbackHandlerUtilities.cleanupState();
        OAuthCallbackHandlerUtilities.showNotification('error', 'Authentication Error', errorMessage, 6000);
        setTimeout(() => {
            window.location.href = '/login?auth_result=error&error_message=' + encodeURIComponent(errorMessage);
        }, 2000);
    }

    /**
     * Handle successful authentication
     * @param {Object} result - Authentication result data
     */
    handleSuccess(result) {
        console.log('✅ Authentication successful:', result);
        OAuthCallbackHandlerUtilities.cleanupState();
        OAuthCallbackHandlerUtilities.showNotification('success', 'Login Successful!', `Welcome to BrowseTerm via ${this.provider}!`, 3000);
        setTimeout(() => {
            window.location.href = '/';
        }, 2000);
    }

    /**
     * Validate CSRF state token
     */
    validateCSRFState() {
        const storedState = localStorage.getItem('latestCSRFToken');
        if (!storedState) this.handleError('Missing stored authentication state');
        if (this.state !== storedState) this.handleError('Authentication state is expired or incorrect');
    }

    /**
     * Send authentication request to backend
     * @param {string} endpoint - API endpoint
     * @returns {Object} Authentication result
     */
    async sendAuthenticationRequest(endpoint) {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                code: this.code,
                state: this.state,
                provider: this.provider
            })
        });
        if (!response.ok) {
            const result = await response.json();
            throw new Error('Failed to send authentication request: ' + result.error || result.detail || `HTTP error! status: ${response.status}`);
        }
        return await response.json();
    }

    /**
     * Proceed with authentication flow
     */
    async proceedWithAuthentication() {
        try {
            // Show processing notification
            OAuthCallbackHandlerUtilities.showNotification('info', 'Processing...', `Completing ${this.provider} authentication`, 3000);
            // Get endpoint for provider
            const endpoint = OAuthCallbackHandlerUtilities.getEndpoint(this.provider);
            if (!endpoint) throw new Error(`Unsupported provider: ${this.provider}`);
            // Send authentication request
            const result = await this.sendAuthenticationRequest(endpoint);
            // Authentication successful
            this.handleSuccess(result);
        } catch (error) {
            this.handleError(error.message);
        }
    }

    /**
     * Initialize and set up event listeners
     * Call this when DOM is ready
     */
    async init() {
        console.log('OAuth callback page loaded');
        // Get provider from window object
        this.provider = window.provider;
        if (!this.provider) this.handleError('No authentication provider specified');

        // Parse and validate URL parameters
        this.parseUrlParameters();

        // Check for OAuth errors: return means, we wont proceed with authentication. In this case, 
        if (this.error) this.handleError(`${this.error}: ${this.errorDescription}`);
        // If authorization code is missing
        if (!this.code) this.handleError('Missing authorization code parameter');
        // If state is missing
        if (!this.state) this.handleError('Missing authentication state parameter');

        // Validate CSRF state
        this.validateCSRFState();
        await this.proceedWithAuthentication();
    }
}


// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    const handler = new OAuthCallbackHandler();
    handler.init();
});

