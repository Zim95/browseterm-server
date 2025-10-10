// OAuth Callback Handler
console.log('OAuth callback page loaded');

document.addEventListener('DOMContentLoaded', function() {
    console.log('OAuth callback DOM is ready');
    // Get provider from window object
    const provider = window.provider;
    if (!provider) {
        console.error('No provider specified');
        handleOAuthError('missing_provider', 'No authentication provider specified');
        return;
    }
    console.log('Processing OAuth callback for provider:', provider);
    // Parse URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');
    const state = urlParams.get('state');
    const error = urlParams.get('error');
    const errorDescription = urlParams.get('error_description');
    console.log('OAuth parameters:', { provider, code, state, error, errorDescription });
    // Handle OAuth error (user cancelled, etc.)
    if (error) {
        console.log('OAuth error received:', error);
        handleOAuthError(error, errorDescription);
        return;
    }
    // Validate required parameters
    if (!code || !state) {
        console.error('Missing required OAuth parameters');
        handleOAuthError('missing_parameters', 'Missing authorization code or state parameter');
        return;
    }
    // Validate CSRF state parameter
    const storedState = localStorage.getItem('latestCSRFToken');
    if (!storedState) {
        console.error('No stored CSRF token found');
        handleOAuthError('missing_state', 'No stored authentication state found');
        return;
    }
    if (state !== storedState) {
        console.error('CSRF state mismatch:', { received: state, stored: storedState });
        handleOAuthError('state_mismatch', 'Authentication state is expired or incorrect');
        return;
    }
    // State is valid, proceed with authentication
    console.log('CSRF state validated successfully');
    proceedWithAuthentication(code, state, provider);
});

/**
 * Handle OAuth errors
 */
function handleOAuthError(error, description) {
    console.error('OAuth error:', error, description);
    // Clean up stored state
    localStorage.removeItem('latestCSRFToken');
    // Show error notification
    if (window.notifications) {
        let errorMessage = 'Authentication failed. Please try again.';
        switch (error) {
            case 'access_denied':
                errorMessage = 'Authentication was cancelled. Please try again.';
                break;
            case 'state_mismatch':
                errorMessage = 'Authentication state is expired or incorrect. Please re-initiate login.';
                break;
            case 'missing_state':
                errorMessage = 'Authentication session expired. Please re-initiate login.';
                break;
            case 'missing_parameters':
                errorMessage = 'Invalid authentication response. Please try again.';
                break;
            default:
                errorMessage = description || 'Authentication failed. Please try again.';
        }
        window.notifications.error('Authentication Error', errorMessage, 6000);
    }
    // Redirect to login page after a short delay
    setTimeout(() => {
        window.location.href = '/login?auth_result=error&error_message=' + encodeURIComponent(errorMessage);
    }, 2000);
}

/**
 * Proceed with successful authentication
 */
async function proceedWithAuthentication(code, state, provider) {
    try {
        console.log(`Sending authorization code to backend for ${provider}...`);
        // Show processing notification
        if (window.notifications) {
            window.notifications.info('Processing...', `Completing ${provider} authentication`, 3000);
        }
        // Determine the correct endpoint based on provider
        const endpoint = getProviderEndpoint(provider);
        if (!endpoint) {
            throw new Error(`Unsupported provider: ${provider}`);
        }
        // Send code to backend
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                code: code,
                state: state,
                provider: provider
            })
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const result = await response.json();
        console.log('Authentication successful:', result);
        // Clean up stored state
        localStorage.removeItem('latestCSRFToken');
        // Cookie is now set by the backend as HTTP-only
        // No need to set it from JavaScript anymore
        // Show success notification
        if (window.notifications) {
            window.notifications.success('Login Successful!', `Welcome to BrowseTerm via ${provider}!`, 3000);
        }
        // Redirect to home page after success
        setTimeout(() => {
            window.location.href = '/';
        }, 2000);
    } catch (error) {
        console.error('Authentication failed:', error);
        // Clean up stored state
        localStorage.removeItem('latestCSRFToken');
        // Show error notification
        if (window.notifications) {
            window.notifications.error('Authentication Failed', `Failed to complete ${provider} authentication. Please try again.`, 5000);
        }
        // Redirect to login page
        setTimeout(() => {
            window.location.href = '/login?auth_result=error&error_message=Failed to complete authentication';
        }, 3000);
    }
}

/**
 * Get the correct endpoint for the provider
 */
function getProviderEndpoint(provider) {
    const endpoints = {
        'google': '/google-token-exchange',
        'github': '/github-token-exchange'
    };    
    return endpoints[provider] || null;
}
