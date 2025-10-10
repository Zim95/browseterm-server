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
    async function handleLogout() {
        // Show confirmation dialog
        if (confirm('Are you sure you want to logout?')) {
            console.log('User confirmed logout');

            try {
                // Call logout endpoint to clear HTTP-only cookie
                const response = await fetch('/logout', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    }
                });

                if (response.ok) {
                    console.log('Logout successful');
                    // Redirect to login page
                    window.location.href = '/login';
                } else {
                    console.error('Logout failed');
                    // Still redirect to login page even if logout fails
                    window.location.href = '/login';
                }
            } catch (error) {
                console.error('Logout error:', error);
                // Still redirect to login page even if logout fails
                window.location.href = '/login';
            }
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

// Notification System
class NotificationManager {
    constructor() {
        this.container = document.getElementById('notificationContainer');
        this.notifications = new Map();
        this.defaultDuration = 5000; // 5 seconds
    }

    /**
     * Show a notification
     * @param {Object} options - Notification options
     * @param {string} options.type - Type of notification ('success', 'error', 'info', 'warning')
     * @param {string} options.title - Notification title
     * @param {string} options.message - Notification message
     * @param {number} options.duration - Duration in milliseconds (optional)
     * @param {boolean} options.closable - Whether notification can be closed (default: true)
     * @param {string} options.icon - Custom icon (optional)
     */
    show(options) {
        const {
            type = 'info',
            title = '',
            message = '',
            duration = this.defaultDuration,
            closable = true,
            icon = null
        } = options;

        // Generate unique ID for the notification
        const id = this.generateId();

        // Create notification element
        const notification = this.createNotificationElement({
            id,
            type,
            title,
            message,
            closable,
            icon
        });

        // Add to container
        this.container.appendChild(notification);
        this.notifications.set(id, notification);

        // Trigger show animation
        requestAnimationFrame(() => {
            notification.classList.add('show');
        });

        // Set up auto-remove
        if (duration > 0) {
            this.setupAutoRemove(id, duration);
        }

        return id;
    }

    /**
     * Create notification element
     */
    createNotificationElement({ id, type, title, message, closable, icon }) {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.setAttribute('data-id', id);
        // Get icon based on type
        const defaultIcons = {
            success: '✓',
            error: '✕',
            info: 'ℹ',
            warning: '⚠'
        };
        const iconText = icon || defaultIcons[type] || defaultIcons.info;
        // Create notification HTML
        notification.innerHTML = `
            <div class="notification-icon">${iconText}</div>
            <div class="notification-content">
                ${title ? `<h4 class="notification-title">${title}</h4>` : ''}
                <p class="notification-message">${message}</p>
            </div>
            ${closable ? '<button class="notification-close" aria-label="Close notification">×</button>' : ''}
            <div class="notification-progress">
                <div class="notification-progress-bar"></div>
            </div>
        `;
        // Add close button event listener
        if (closable) {
            const closeBtn = notification.querySelector('.notification-close');
            closeBtn.addEventListener('click', () => this.remove(id));
        }
        return notification;
    }

    /**
     * Setup auto-remove with progress bar
     */
    setupAutoRemove(id, duration) {
        const notification = this.notifications.get(id);
        if (!notification) return;

        const progressBar = notification.querySelector('.notification-progress-bar');

        // Animate progress bar
        progressBar.style.width = '100%';
        progressBar.style.transitionDuration = `${duration}ms`;

        // Remove notification after duration
        setTimeout(() => {
            this.remove(id);
        }, duration);
    }

    /**
     * Remove notification
     */
    remove(id) {
        const notification = this.notifications.get(id);
        if (!notification) return;

        // Ensure notification is visible before hiding
        if (!notification.classList.contains('show')) {
            // If not shown yet, just remove immediately
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
            this.notifications.delete(id);
            return;
        }

        // Add hide class to trigger slide-out animation
        notification.classList.remove('show');
        notification.classList.add('hide');

        // Remove from DOM after animation completes
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
            this.notifications.delete(id);
        }, 300); // Match CSS transition duration
    }

    /**
     * Remove all notifications
     */
    removeAll() {
        this.notifications.forEach((notification, id) => {
            this.remove(id);
        });
    }

    /**
     * Generate unique ID
     */
    generateId() {
        return 'notification_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
    /**
     * Convenience methods
     */
    success(title, message, duration) {
        return this.show({ type: 'success', title, message, duration });
    }
    error(title, message, duration) {
        return this.show({ type: 'error', title, message, duration });
    }
    info(title, message, duration) {
        return this.show({ type: 'info', title, message, duration });
    }
    warning(title, message, duration) {
        return this.show({ type: 'warning', title, message, duration });
    }
}

// Create global notification manager instance
window.notifications = new NotificationManager();

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NotificationManager;
}
