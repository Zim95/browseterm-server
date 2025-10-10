// Login page JavaScript
console.log('Login page loaded successfully!');
console.log('Welcome to BrowseTerm login page');

// OAuth2 helper functions
function generateCSRFToken() {
    return crypto.randomUUID().replace(/-/g, '');
}

function initiateOAuth(provider) {
    const providerInfo = window.OAUTH_CONFIG[provider];
    if (!providerInfo) {
        window.notifications.error(`Login with ${provider} is not supported.`);
        return;
    }
    const clientId = providerInfo.client_id;
    const authMetaUrl = providerInfo.auth_meta_url;
    const authScope = providerInfo.auth_scope;
    const authRedirectUri = providerInfo.auth_redirect_uri;

    // Create a CSRF token and store it locally
    const state = generateCSRFToken();
    localStorage.setItem("latestCSRFToken", state);

    // Redirect the user to the OAuth provider
    const link = `${authMetaUrl}?scope=${authScope}&response_type=code&access_type=offline&state=${state}&redirect_uri=${authRedirectUri}&client_id=${clientId}`;
    window.location.assign(link);
}

// Add any login page specific functionality here
document.addEventListener('DOMContentLoaded', function() {
    console.log('Login page DOM is ready');
    console.log('OAuth Config:', window.OAUTH_CONFIG);

    // Check for URL parameters that might indicate authentication results
    const urlParams = new URLSearchParams(window.location.search);
    const authResult = urlParams.get('auth_result');
    const errorMessage = urlParams.get('error_message');

    // Show notifications based on URL parameters
    if (authResult === 'success') {
        notifications.success("Login Successful!", "Welcome to BrowseTerm!", 4000);
    } else if (authResult === 'error') {
        const message = errorMessage || "Authentication failed. Please try again.";
        notifications.error("Login Failed", message, 6000);
    } else if (authResult === 'cancelled') {
        notifications.warning("Login Cancelled", "You cancelled the authentication process", 4000);
    }

    // Add click events to login buttons
    const googleBtn = document.querySelector('.btn-google');
    const githubBtn = document.querySelector('.btn-github');

    if (googleBtn) {
        googleBtn.addEventListener('click', function(e) {
            e.preventDefault();
            console.log('Google login button clicked!');
            initiateOAuth('google');
        });
    }

    if (githubBtn) {
        githubBtn.addEventListener('click', function(e) {
            e.preventDefault();
            console.log('GitHub login button clicked!');
            initiateOAuth('github');
        });
    }

    // Show welcome notification on page load (only if no auth result)
    if (!authResult) {
        setTimeout(() => {
            notifications.info("Welcome!", "Choose your preferred login method below", 3000);
        }, 1000);
    }
});
