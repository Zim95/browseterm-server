// Base JavaScript for sidebar functionality
console.log('Base template loaded successfully!');

document.addEventListener('DOMContentLoaded', function() {
    console.log('Base template DOM is ready');

    // Get elements
    const sidebar = document.getElementById('sidebar');
    const hamburger = document.getElementById('hamburger');
    const mainContent = document.getElementById('mainContent');
    const logoutBtn = document.getElementById('logoutBtn');

    // Check if sidebar should be collapsed by default (stored in localStorage)
    const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';

    // Initialize sidebar state
    if (isCollapsed) {
        sidebar.classList.add('collapsed');
        mainContent.classList.add('expanded');
    }

    // Hamburger menu toggle
    if (hamburger) {
        hamburger.addEventListener('click', function() {
            toggleSidebar();
        });
    }

    // Logout button functionality
    if (logoutBtn) {
        logoutBtn.addEventListener('click', function() {
            console.log('Logout button clicked!');
            // Add logout logic here
            handleLogout();
        });
    }

    // Handle window resize for mobile responsiveness
    window.addEventListener('resize', function() {
        handleResponsiveSidebar();
    });

    // Initialize responsive behavior
    handleResponsiveSidebar();

    // Function to toggle sidebar
    function toggleSidebar() {
        const isCurrentlyCollapsed = sidebar.classList.contains('collapsed');
        
        if (isCurrentlyCollapsed) {
            // Expand sidebar
            sidebar.classList.remove('collapsed');
            mainContent.classList.remove('expanded');
            localStorage.setItem('sidebarCollapsed', 'false');
        } else {
            // Collapse sidebar
            sidebar.classList.add('collapsed');
            mainContent.classList.add('expanded');
            localStorage.setItem('sidebarCollapsed', 'true');
        }
        
        console.log('Sidebar toggled:', !isCurrentlyCollapsed ? 'expanded' : 'collapsed');
    }

    // Function to handle responsive sidebar behavior
    function handleResponsiveSidebar() {
        const isMobile = window.innerWidth <= 768;
        
        if (isMobile) {
            // On mobile, sidebar should be hidden by default
            sidebar.classList.remove('collapsed');
            sidebar.classList.remove('open');
            mainContent.classList.remove('expanded');
        } else {
            // On desktop, restore saved state
            const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
            if (isCollapsed) {
                sidebar.classList.add('collapsed');
                mainContent.classList.add('expanded');
            } else {
                sidebar.classList.remove('collapsed');
                mainContent.classList.remove('expanded');
            }
        }
    }

    // Function to handle logout
    function handleLogout() {
        // Show confirmation dialog
        if (confirm('Are you sure you want to logout?')) {
            console.log('User confirmed logout');
            // Add actual logout logic here
            // For now, just redirect to login page
            window.location.href = '/login';
        }
    }

    // Add smooth transitions for menu items
    const menuLinks = document.querySelectorAll('.menu-link');
    menuLinks.forEach(link => {
        link.addEventListener('mouseenter', function() {
            this.style.transform = 'translateX(4px)';
        });
        
        link.addEventListener('mouseleave', function() {
            this.style.transform = 'translateX(0)';
        });
    });

    // Add click animation to buttons
    const buttons = document.querySelectorAll('button');
    buttons.forEach(button => {
        button.addEventListener('click', function() {
            this.style.transform = 'scale(0.95)';
            setTimeout(() => {
                this.style.transform = '';
            }, 150);
        });
    });
    console.log('Sidebar functionality initialized');
});
