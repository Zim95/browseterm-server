// Home page JavaScript
console.log('Home page loaded successfully!');
console.log('Welcome to BrowseTerm home page');

// Add any home page specific functionality here
document.addEventListener('DOMContentLoaded', function() {
    console.log('Home page DOM is ready');

    // Example: Add a click event to the container
    const container = document.querySelector('.container');
    if (container) {
        container.addEventListener('click', function() {
            console.log('Home container clicked!');
        });
    }
});
