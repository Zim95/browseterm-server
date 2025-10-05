// Login page JavaScript
console.log('Login page loaded successfully!');
console.log('Welcome to BrowseTerm login page');

// Add any login page specific functionality here
document.addEventListener('DOMContentLoaded', function() {
    console.log('Login page DOM is ready');

    // Example: Add click events to login buttons
    const googleBtn = document.querySelector('.btn-google');
    const githubBtn = document.querySelector('.btn-github');

    if (googleBtn) {
        googleBtn.addEventListener('click', function(e) {
            e.preventDefault();
            console.log('Google login button clicked!');
            // Add Google OAuth logic here
        });
    }

    if (githubBtn) {
        githubBtn.addEventListener('click', function(e) {
            e.preventDefault();
            console.log('GitHub login button clicked!');
            // Add GitHub OAuth logic here
        });
    }
});
