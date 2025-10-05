// Base JavaScript for sidebar functionality
console.log('Base template loaded successfully!');

document.addEventListener('DOMContentLoaded', function() {
    console.log('Base template DOM is ready');

    // Get elements
    const sidebar = document.getElementById('sidebar');
    const hamburger = document.getElementById('hamburger');
    const mainContent = document.getElementById('mainContent');
    const logoutBtn = document.getElementById('logoutBtn');
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');

    // Check if sidebar should be collapsed by default (stored in localStorage)
    const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';

    // Initialize sidebar state
    if (isCollapsed) {
        sidebar.classList.add('collapsed');
        mainContent.classList.add('expanded');
    }

    // Hamburger menu toggle (desktop)
    if (hamburger) {
        hamburger.addEventListener('click', function() {
            toggleSidebar();
        });
    }

    // Mobile menu button toggle
    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', function() {
            toggleMobileMenu();
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
            closeMobileMenu(); // Close mobile menu if open
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

    // Mobile menu functionality
    let mobileOverlay = null;

    function createMobileOverlay() {
        if (!mobileOverlay) {
            mobileOverlay = document.createElement('div');
            mobileOverlay.className = 'mobile-overlay';
            document.body.appendChild(mobileOverlay);
            
            mobileOverlay.addEventListener('click', closeMobileMenu);
        }
        return mobileOverlay;
    }

    function openMobileMenu() {
        sidebar.classList.add('open');
        mobileMenuBtn.classList.add('active');
        const overlay = createMobileOverlay();
        overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    function closeMobileMenu() {
        sidebar.classList.remove('open');
        mobileMenuBtn.classList.remove('active');
        if (mobileOverlay) {
            mobileOverlay.classList.remove('active');
        }
        document.body.style.overflow = '';
    }

    function toggleMobileMenu() {
        if (sidebar.classList.contains('open')) {
            closeMobileMenu();
        } else {
            openMobileMenu();
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
