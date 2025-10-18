/**
 * BaseUtilities
 * Utility methods for base functionality
 */
class BaseUtilities {
    /**
     * Get value from localStorage with default fallback
     * @param {string} key - Storage key
     * @param {string} defaultValue - Default value if key not found
     * @returns {string} Stored value or default
     */
    static getFromLocalStorage(key, defaultValue = null) {
        return localStorage.getItem(key) || defaultValue;
    }

    /**
     * Set value in localStorage
     * @param {string} key - Storage key
     * @param {string} value - Value to store
     */
    static setInLocalStorage(key, value) {
        localStorage.setItem(key, value);
    }

    /**
     * Remove value from localStorage
     * @param {string} key - Storage key
     */
    static removeFromLocalStorage(key) {
        localStorage.removeItem(key);
    }

    /**
     * Check if viewport is mobile
     * @returns {boolean} True if mobile viewport
     */
    static isMobile() {
        return window.innerWidth <= 768;
    }
}

/**
 * SidebarManager
 * Handles sidebar collapse/expand, mobile menu, and responsive behavior
 */
class SidebarManager {
    /**
     * Initialize the sidebar manager
     * @param {HTMLElement} sidebar - Sidebar element
     * @param {HTMLElement} mainContent - Main content element
     * @param {HTMLElement} hamburger - Hamburger button element
     * @param {HTMLElement} mobileMenuBtn - Mobile menu button element
     */
    constructor(sidebar, mainContent, hamburger, mobileMenuBtn) {
        this.sidebar = sidebar;
        this.mainContent = mainContent;
        this.hamburger = hamburger;
        this.mobileMenuBtn = mobileMenuBtn;
        this.mobileOverlay = null;
        console.log('SidebarManager initialized');
    }

    /**
     * Initialize sidebar state and event listeners
     */
    initialize() {
        // Set initial state from localStorage
        const isCollapsed = BaseUtilities.getFromLocalStorage('sidebarCollapsed') === 'true';
        if (isCollapsed) {
            this.sidebar.classList.add('collapsed');
            this.mainContent.classList.add('expanded');
        }

        // Setup event listeners
        this.setupEventListeners();

        // Initialize responsive behavior
        this.handleResponsiveSidebar();
    }

    /**
     * Setup event listeners for sidebar controls
     */
    setupEventListeners() {
        // Hamburger menu toggle (desktop)
        if (this.hamburger) {
            this.hamburger.addEventListener('click', () => this.toggleSidebar());
        }

        // Mobile menu button toggle
        if (this.mobileMenuBtn) {
            this.mobileMenuBtn.addEventListener('click', () => this.toggleMobileMenu());
        }

        // Handle window resize for mobile responsiveness
        window.addEventListener('resize', () => this.handleResponsiveSidebar());
    }

    /**
     * Toggle sidebar collapse/expand (desktop)
     */
    toggleSidebar() {
        const isCurrentlyCollapsed = this.sidebar.classList.contains('collapsed');
        if (isCurrentlyCollapsed) {
            // Expand sidebar
            this.sidebar.classList.remove('collapsed');
            this.mainContent.classList.remove('expanded');
            BaseUtilities.setInLocalStorage('sidebarCollapsed', 'false');
        } else {
            // Collapse sidebar
            this.sidebar.classList.add('collapsed');
            this.mainContent.classList.add('expanded');
            BaseUtilities.setInLocalStorage('sidebarCollapsed', 'true');
        }
        console.log('Sidebar toggled:', !isCurrentlyCollapsed ? 'collapsed' : 'expanded');
    }

    /**
     * Handle responsive sidebar behavior based on viewport
     */
    handleResponsiveSidebar() {
        const isMobile = BaseUtilities.isMobile();
        if (isMobile) {
            // On mobile, sidebar should be hidden by default
            this.sidebar.classList.remove('collapsed');
            this.sidebar.classList.remove('open');
            this.mainContent.classList.remove('expanded');
            this.closeMobileMenu();
        } else {
            // On desktop, restore saved state
            const isCollapsed = BaseUtilities.getFromLocalStorage('sidebarCollapsed') === 'true';
            if (isCollapsed) {
                this.sidebar.classList.add('collapsed');
                this.mainContent.classList.add('expanded');
            } else {
                this.sidebar.classList.remove('collapsed');
                this.mainContent.classList.remove('expanded');
            }
        }
    }

    /**
     * Create mobile overlay for sidebar
     * @returns {HTMLElement} Overlay element
     */
    createMobileOverlay() {
        if (!this.mobileOverlay) {
            this.mobileOverlay = document.createElement('div');
            this.mobileOverlay.className = 'mobile-overlay';
            document.body.appendChild(this.mobileOverlay);
            this.mobileOverlay.addEventListener('click', () => this.closeMobileMenu());
        }
        return this.mobileOverlay;
    }

    /**
     * Open mobile menu
     */
    openMobileMenu() {
        this.sidebar.classList.add('open');
        this.mobileMenuBtn.classList.add('active');
        const overlay = this.createMobileOverlay();
        overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    /**
     * Close mobile menu
     */
    closeMobileMenu() {
        this.sidebar.classList.remove('open');
        if (this.mobileMenuBtn) {
            this.mobileMenuBtn.classList.remove('active');
        }
        if (this.mobileOverlay) {
            this.mobileOverlay.classList.remove('active');
        }
        document.body.style.overflow = '';
    }

    /**
     * Toggle mobile menu open/close
     */
    toggleMobileMenu() {
        if (this.sidebar.classList.contains('open')) {
            this.closeMobileMenu();
        } else {
            this.openMobileMenu();
        }
    }
}

/**
 * DarkModeManager
 * Handles dark mode initialization and toggling
 * 
 * Note: The dark mode toggle button uses an inline onclick handler that calls
 * window.toggleDarkModeGlobal (defined in base.html head). This manager is
 * only responsible for initializing the dark mode state on page load.
 * The toggle() method exists for programmatic use if needed, but is not
 * directly called by the UI button.
 */
class DarkModeManager {
    /**
     * Initialize the dark mode manager
     */
    constructor() {
        console.log('DarkModeManager initialized');
    }

    /**
     * Initialize dark mode from localStorage
     */
    initialize() {
        // Check if user has a saved preference
        const savedTheme = BaseUtilities.getFromLocalStorage('theme');

        // Set default to 'light' if no preference is saved
        if (!savedTheme) {
            BaseUtilities.setInLocalStorage('theme', 'light');
        }

        // Only apply dark mode if explicitly saved as 'dark' (default is light mode)
        if (savedTheme === 'dark') {
            document.body.classList.add('dark-mode');
        }

        // Remove the loading class from html if it exists (from head script)
        document.documentElement.classList.remove('dark-mode-loading');

        console.log('Dark mode initialized:', document.body.classList.contains('dark-mode') ? 'enabled' : 'disabled');
    }
}

/**
 * LogoutManager
 * Handles user logout functionality
 */
class LogoutManager {
    /**
     * Initialize the logout manager
     */
    constructor() {
        console.log('LogoutManager initialized');
    }

    /**
     * Handle logout with confirmation
     */
    async handleLogout() {
        // Show confirmation dialog
        if (!confirm('Are you sure you want to logout?')) {
            return;
        }

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

/**
 * NotificationManager
 * Manages toast notifications throughout the application
 */
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

/**
 * UIAnimationManager
 * Handles UI animations for buttons and links
 */
class UIAnimationManager {
    /**
     * Initialize UI animations
     */
    constructor() {
        console.log('UIAnimationManager initialized');
    }

    /**
     * Add animations to all interactive elements
     */
    initialize() {
        this.addMenuLinkAnimations();
        this.addButtonAnimations();
    }

    /**
     * Add smooth transitions for menu items
     */
    addMenuLinkAnimations() {
        const menuLinks = document.querySelectorAll('.menu-link');
        menuLinks.forEach(link => {
            link.addEventListener('mouseenter', function() {
                this.style.transform = 'translateX(4px)';
            });

            link.addEventListener('mouseleave', function() {
                this.style.transform = 'translateX(0)';
            });
        });
    }

    /**
     * Add click animation to buttons
     */
    addButtonAnimations() {
        const buttons = document.querySelectorAll('button');
        buttons.forEach(button => {
            button.addEventListener('click', function() {
                this.style.transform = 'scale(0.95)';
                setTimeout(() => {
                    this.style.transform = '';
                }, 150);
            });
        });
    }
}

/**
 * BaseApp
 * Main application controller that orchestrates all managers
 */
class BaseApp {
    /**
     * Initialize the base app
     */
    constructor() {
        console.log('BaseApp initialized');
        this.sidebarManager = null;
        this.darkModeManager = null;
        this.logoutManager = null;
        this.uiAnimationManager = null;
    }

    /**
     * Initialize all managers and functionality
     */
    initialize() {
        console.log('Base template DOM is ready');

        // Get elements
        const sidebar = document.getElementById('sidebar');
        const hamburger = document.getElementById('hamburger');
        const mainContent = document.getElementById('mainContent');
        const logoutBtn = document.getElementById('logoutBtn');
        const mobileMenuBtn = document.getElementById('mobileMenuBtn');

        // Initialize managers
        this.sidebarManager = new SidebarManager(sidebar, mainContent, hamburger, mobileMenuBtn);
        this.sidebarManager.initialize();

        this.darkModeManager = new DarkModeManager();
        this.darkModeManager.initialize();

        this.logoutManager = new LogoutManager();

        this.uiAnimationManager = new UIAnimationManager();
        this.uiAnimationManager.initialize();

        // Setup event listeners
        this.setupEventListeners(logoutBtn);

        console.log('Sidebar functionality initialized');
        // Note: Dark mode toggle is handled via inline onclick in HTML
        // The global function window.toggleDarkModeGlobal is defined in base.html head
        // No event listener needed here to avoid double-firing
        console.log('Dark mode toggle handled via inline onclick handler');
    }

    /**
     * Setup event listeners for global actions
     */
    setupEventListeners(logoutBtn) {
        // Logout button functionality
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => {
                this.logoutManager.handleLogout();
            });
        }
    }
}


document.addEventListener('DOMContentLoaded', function() {
    const app = new BaseApp();
    app.initialize();
    // Make dark mode manager available globally for inline onclick handler
    window.baseApp = app;
});

// Create global notification manager instance
window.notifications = new NotificationManager();
