/**
 * Login page (migration Part 3 - Cloud's own, not a proxy to Local's).
 *
 * The Google/GitHub buttons are plain links to Cloud's own /auth/{provider}/start?target=cloud
 * (src/cloud/oauth_handlers.py:oauth_start) - Cloud is the sole OAuth authority and, as of this
 * page, also the browser origin completing the login itself (oauth_callback sets the session
 * cookie directly for target=cloud and redirects to /terminals - no handoff code, no separate
 * origin to hand off to). This script only shows a notification for the auth_result query param
 * oauth_callback redirects back here with on failure.
 */
class LoginUtilities {
    static parseURLParameters() {
        const urlParams = new URLSearchParams(window.location.search);
        return {
            authResult: urlParams.get('auth_result'),
            errorMessage: urlParams.get('error_message'),
        };
    }

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

class LoginHandler {
    handleAuthResults() {
        const { authResult, errorMessage } = LoginUtilities.parseURLParameters();

        if (!authResult) {
            LoginUtilities.showNotification('info', 'Welcome!', 'Choose your preferred login method below', 3000);
            return;
        }

        switch (authResult) {
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

    init() {
        this.handleAuthResults();
    }
}

document.addEventListener('DOMContentLoaded', function () {
    new LoginHandler().init();
});

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { LoginUtilities, LoginHandler };
}
