/**
 * ProfileUtilities
 * Utility methods for profile page functionality
 */
class ProfileUtilities {
    /**
     * Get user data from window object (passed from backend template)
     * @returns {Object} User data object
     */
    static getUserDataFromTemplate() {
        const userInfo = window.userInfo || {};
        return {
            name: userInfo.name || 'Unknown User',
            email: userInfo.email || 'No email',
            profile_picture_url: userInfo.profile_picture_url || null
        };
    }

    /**
     * Get current subscription plan from window object
     * @returns {Object} Subscription plan object
     */
    static getCurrentPlanFromTemplate() {
        return window.currentSubscriptionPlan || {};
    }

    /**
     * Validate image file
     * @param {File} file - File to validate
     * @returns {Object} { valid: boolean, error: string|null }
     */
    static validateImageFile(file) {
        // Check if file is an image
        if (!file.type.startsWith('image/')) {
            return { valid: false, error: 'Please select a valid image file.' };
        }

        // Check file size (max 5MB)
        const maxSize = 5 * 1024 * 1024; // 5MB
        if (file.size > maxSize) {
            return { valid: false, error: 'File size must be less than 5MB.' };
        }

        return { valid: true, error: null };
    }

    /**
     * Convert file to data URL for preview
     * @param {File} file - File to convert
     * @returns {Promise<string>} Data URL
     */
    static fileToDataURL(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = (e) => reject(e);
            reader.readAsDataURL(file);
        });
    }

    /**
     * Show notification
     * @param {string} type - Notification type
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
 * ProfileHandler
 * Handles user profile page functionality
 */
class ProfileHandler {
    /**
     * Initialize the profile handler
     */
    constructor() {
        console.log('ProfileHandler initialized');
        this.elements = {};
        this.userData = null;
        this.currentPlan = null;
    }

    /**
     * Initialize profile page
     */
    async init() {
        console.log('User profile page loaded successfully!');

        // Cache DOM elements
        this.cacheElements();

        // Load user profile data
        await this.loadUserProfile();

        // Setup event listeners
        this.setupEventListeners();
    }

    /**
     * Cache DOM elements
     */
    cacheElements() {
        this.elements = {
            userName: document.getElementById('userName'),
            userEmail: document.getElementById('userEmail'),
            currentPlan: document.getElementById('currentPlan'),
            profilePhoto: document.getElementById('profilePhoto'),
            uploadBtn: document.getElementById('uploadBtn'),
            photoUpload: document.getElementById('photoUpload')
        };
    }

    /**
     * Load user profile data
     */
    async loadUserProfile() {
        try {
            console.log('Loading user profile...');

            // Get user data from template
            this.userData = ProfileUtilities.getUserDataFromTemplate();
            console.log('User data loaded:', this.userData);

            // Get current subscription plan
            this.currentPlan = await this.getCurrentSubscription();
            console.log('Current plan:', this.currentPlan);

            // Update UI
            this.updateUI();

        } catch (error) {
            console.error('Error loading user profile:', error);
            this.showError('Error loading user profile. Please try again.');
            ProfileUtilities.showNotification(
                'error',
                'Profile Error',
                'Failed to load profile data',
                5000
            );
        }
    }

    /**
     * Get current subscription (simulated API call)
     * @returns {Promise<Object>} Subscription plan object
     */
    async getCurrentSubscription() {
        console.log('Fetching current subscription...');
        // For now, just return the plan from template
        // In the future, this could be an actual API call
        return ProfileUtilities.getCurrentPlanFromTemplate();
    }

    /**
     * Update UI with user data
     */
    updateUI() {
        // Update text content
        this.elements.userName.textContent = this.userData.name;
        this.elements.userEmail.textContent = this.userData.email;
        this.elements.currentPlan.textContent = this.currentPlan.name || 'No Plan';

        // Update profile picture
        this.updateProfilePicture(this.userData.profile_picture_url);

        // Remove loading states
        this.removeLoadingStates();
    }

    /**
     * Update profile picture
     * @param {string|null} pictureUrl - URL of profile picture
     */
    updateProfilePicture(pictureUrl) {
        console.log('Updating profile picture...', pictureUrl);

        if (!pictureUrl) {
            console.log('No profile picture URL provided');
            return;
        }

        // Remove icon if exists
        const icon = this.elements.profilePhoto.querySelector('.photo-icon');
        if (icon) {
            icon.remove();
        }

        // Get or create img element
        let img = this.elements.profilePhoto.querySelector('img');
        if (!img) {
            img = document.createElement('img');
            this.elements.profilePhoto.appendChild(img);
        }

        // Setup error handler
        img.onerror = () => {
            console.error('Failed to load profile picture from:', pictureUrl);
            ProfileUtilities.showNotification(
                'warning',
                'Profile Picture',
                'Failed to load profile picture',
                3000
            );
        };

        // Set attributes for external images (Google, GitHub, etc.)
        img.referrerPolicy = 'no-referrer';  // this is to prevent tracking - So that our profile picture gets loaded properly.
        img.crossOrigin = 'anonymous';  // this is to prevent tracking - So that our profile picture gets loaded properly.
        img.src = pictureUrl;
        img.alt = this.userData.name;

        console.log('Profile picture updated:', img.src);
    }

    /**
     * Remove loading states from elements
     */
    removeLoadingStates() {
        this.elements.userName.classList.remove('loading');
        this.elements.userEmail.classList.remove('loading');
        this.elements.currentPlan.classList.remove('loading');
    }

    /**
     * Show error message in UI
     * @param {string} message - Error message to display
     */
    showError(message) {
        this.elements.userName.textContent = message;
        this.elements.userEmail.textContent = message;
        this.elements.currentPlan.textContent = message;

        this.elements.userName.classList.add('error');
        this.elements.userEmail.classList.add('error');
        this.elements.currentPlan.classList.add('error');
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Upload button - currently disabled (coming soon)
        if (this.elements.uploadBtn) {
            this.elements.uploadBtn.addEventListener('click', () => {
                this.handleUploadClick();
            });
        }

        // Profile photo click - currently disabled (coming soon)
        if (this.elements.profilePhoto) {
            this.elements.profilePhoto.addEventListener('click', () => {
                this.handleProfilePhotoClick();
            });
        }

        // File input change handler (for when upload is enabled)
        if (this.elements.photoUpload) {
            this.elements.photoUpload.addEventListener('change', (e) => {
                this.handlePhotoUpload(e);
            });
        }
    }

    /**
     * Handle upload button click
     * Currently shows "Coming soon" alert
     */
    handleUploadClick() {
        ProfileUtilities.showNotification(
            'info',
            'Coming Soon',
            'Photo upload feature will be available soon!',
            3000
        );
    }

    /**
     * Handle profile photo click
     * Currently shows "Coming soon" alert
     */
    handleProfilePhotoClick() {
        ProfileUtilities.showNotification(
            'info',
            'Coming Soon',
            'Photo upload feature will be available soon!',
            3000
        );
    }

    /**
     * Handle photo upload
     * @param {Event} event - File input change event
     */
    async handlePhotoUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        console.log('Photo upload triggered:', file.name);

        // Validate file
        const validation = ProfileUtilities.validateImageFile(file);
        if (!validation.valid) {
            ProfileUtilities.showNotification(
                'error',
                'Invalid File',
                validation.error,
                5000
            );
            return;
        }

        try {
            // Convert to data URL for preview
            const dataURL = await ProfileUtilities.fileToDataURL(file);

            // Update preview
            this.updateProfilePicturePreview(dataURL);

            console.log('Profile photo preview updated:', file.name);

            ProfileUtilities.showNotification(
                'success',
                'Preview Updated',
                'Photo preview updated. Click Save to upload.',
                3000
            );

        } catch (error) {
            console.error('Error processing photo:', error);
            ProfileUtilities.showNotification(
                'error',
                'Upload Error',
                'Failed to process photo. Please try again.',
                5000
            );
        }
    }

    /**
     * Update profile picture preview
     * @param {string} dataURL - Data URL of image
     */
    updateProfilePicturePreview(dataURL) {
        // Remove icon if exists
        const icon = this.elements.profilePhoto.querySelector('.photo-icon');
        if (icon) {
            icon.remove();
        }

        // Get or create img element
        let img = this.elements.profilePhoto.querySelector('img');
        if (!img) {
            img = document.createElement('img');
            this.elements.profilePhoto.appendChild(img);
        }

        // Set attributes for external images (Google, GitHub, etc.)
        img.referrerPolicy = 'no-referrer';  // this is to prevent tracking - So that our profile picture gets loaded properly.
        img.crossOrigin = 'anonymous';  // this is to prevent tracking - So that our profile picture gets loaded properly.
        img.src = dataURL;
        img.alt = 'Profile Preview';
    }
}

// Initialize profile handler when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('User profile class DOM is ready');
    const profileHandler = new ProfileHandler();
    profileHandler.init();
});
