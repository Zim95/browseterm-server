/**
 * TerminalsUtilities
 * Utility methods for terminals page functionality
 */
class TerminalsUtilities {
    /**
     * Get user info from window object (passed from backend)
     * @returns {Object} User info
     */
    static getUserInfo() {
        return window.userInfo || {};
    }

    static getOperatingSystems() {
        return window.images || [];
    }

    /**
     * Get current subscription plan from window object
     * @returns {Object} Current subscription plan
     */
    static getCurrentSubscriptionPlan() {
        return window.currentSubscriptionPlan || {};
    }

    /**
     * Get all subscription plans from window object
     * @returns {Array} All subscription plans
     */
    static getAllSubscriptionPlans() {
        return window.subscriptionPlans || [];
    }

    /**
     * Check if resource is configurable
     * @param {string} value - Resource value
     * @returns {boolean} True if configurable
     */
    static isConfigurable(value) {
        return value && value.toString().toLowerCase() === 'configurable';
    }

    /**
     * Normalize a display name into a safe username: lowercase, underscores, alphanumerics only
     * @param {string} name
     * @returns {string}
     */
    static normalizeName(name) {
        if (!name || typeof name !== 'string') return '';
        const lowered = name.trim().toLowerCase();
        const underscored = lowered.replace(/\s+/g, '_');
        return underscored.replace(/[^a-z0-9_]/g, '');
    }

    /**
     * Generate an alphanumeric password (no special chars)
     * @param {number} length
     * @returns {string}
     */
    static generatePassword(length = 8) {
        const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
        let pwd = '';
        for (let i = 0; i < length; i += 1) {
            const idx = Math.floor(Math.random() * chars.length);
            pwd += chars.charAt(idx);
        }
        return pwd;
    }

    /**
     * Find image record by name from window.images
     * @param {string} name
     * @returns {Object|null}
     */
    static findImageByName(name) {
        const images = TerminalsUtilities.getOperatingSystems();
        if (!Array.isArray(images)) return null;
        const target = (name || '').toString().trim();
        return images.find((img) => (img.name || '').toString().trim() === target) || null;
    }

    /**
     * Format status text (capitalize first letter)
     * @param {string} status - Terminal status
     * @returns {string} Formatted status
     */
    static formatStatus(status) {
        return status.charAt(0).toUpperCase() + status.slice(1);
    }

    /**
     * Adjust number input value
     * @param {HTMLInputElement} input - Input element
     * @param {number} change - Amount to change by
     * @param {number} min - Minimum value
     * @param {number} max - Maximum value
     */
    static adjustNumber(input, change, min = 1, max = 30) {
        const currentValue = parseInt(input.value) || min;
        const newValue = currentValue + change;

        if (newValue >= min && newValue <= max) {
            input.value = newValue;
        }
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
 * TerminalsHandler
 * Handles terminals page functionality
 */
class TerminalsHandler {
    /**
     * Initialize the terminals handler
     */
    constructor() {
        console.log('TerminalsHandler initialized');
        this.elements = {};
        this.terminals = [];
        this.operatingSystems = [];
        this.currentPlan = null;
        this.allPlans = [];
        this.cpuConfigurable = false;
        this.memoryConfigurable = false;
        this.storageConfigurable = false;
        // Track containers pending "Running" status - auto-cleanup on failure
        // Map of containerId -> { kubernetesId, networkName, userId }
        this.pendingContainers = new Map();
    }

    /**
     * Initialize terminals page
     */
    async init() {
        console.log('Terminals page loaded successfully!');

        // Cache DOM elements
        this.cacheElements();

        // Load subscription data and configure CPU/Memory/Storage controls
        this.loadSubscriptionData();
        this.configureResourceControls();

        // Load terminals
        await this.loadTerminals();

        // Load operating systems for modal
        await this.loadOperatingSystems();

        // Setup event listeners
        this.setupEventListeners();

        // Setup SSE connection for real-time status updates
        this.setupStatusStream();
    }

    /**
     * Cache DOM elements
     */
    cacheElements() {
        this.elements = {
            terminalsList: document.getElementById('terminalsList'),
            newTerminalBtn: document.querySelector('.new-terminal-btn'),
            modalOverlay: document.getElementById('modalOverlay'),
            modalClose: document.getElementById('modalClose'),
            cancelBtn: document.getElementById('cancelBtn'),
            terminalForm: document.getElementById('terminalForm'),
            operatingSystemSelect: document.getElementById('operatingSystem'),
            cpuInput: document.getElementById('cpu'),
            cpuDecrease: document.getElementById('cpuDecrease'),
            cpuIncrease: document.getElementById('cpuIncrease'),
            memoryInput: document.getElementById('memory'),
            memoryDecrease: document.getElementById('memoryDecrease'),
            memoryIncrease: document.getElementById('memoryIncrease'),
            storageInput: document.getElementById('storage'),
            storageDecrease: document.getElementById('storageDecrease'),
            storageIncrease: document.getElementById('storageIncrease')
        };
    }

    /**
     * Load subscription data from backend
     */
    loadSubscriptionData() {
        // Get current plan and all plans
        this.currentPlan = TerminalsUtilities.getCurrentSubscriptionPlan();
        this.allPlans = TerminalsUtilities.getAllSubscriptionPlans();
        // Check if CPU, Memory, and Storage are configurable
        this.cpuConfigurable = TerminalsUtilities.isConfigurable(
            this.currentPlan.cpu_limit_per_container
        );
        this.memoryConfigurable = TerminalsUtilities.isConfigurable(
            this.currentPlan.memory_limit_per_container
        );
        this.storageConfigurable = TerminalsUtilities.isConfigurable(
            this.currentPlan.storage_limit_per_container
        );
    }

    /**
     * Configure CPU/Memory/Storage controls based on subscription plan
     */
    configureResourceControls() {
        // Configure CPU controls
        this.configureResourceControl('cpu', this.cpuConfigurable);

        // Configure Memory controls
        this.configureResourceControl('memory', this.memoryConfigurable);

        // Configure Storage controls
        this.configureResourceControl('storage', this.storageConfigurable);
    }

    /**
     * Configure a resource control (CPU, Memory, or Storage)
     * @param {string} resource - 'cpu', 'memory', or 'storage'
     * @param {boolean} isConfigurable - Whether the resource is configurable
     */
    configureResourceControl(resource, isConfigurable) {
        const decreaseBtn = this.elements[`${resource}Decrease`];
        const increaseBtn = this.elements[`${resource}Increase`];
        const input = this.elements[`${resource}Input`];
        const info = document.getElementById(`${resource}Info`);

        if (isConfigurable) {
            // Enable controls
            decreaseBtn.disabled = false;
            increaseBtn.disabled = false;
            input.disabled = false;
            if (info) info.style.display = 'none';
        } else {
            // Disable controls
            decreaseBtn.disabled = true;
            increaseBtn.disabled = true;
            input.disabled = true;

            // Find plans with configurable resource
            const configurablePlans = this.allPlans.filter(plan => {
                let resourceValue;
                if (resource === 'cpu') {
                    resourceValue = plan.cpu_limit_per_container;
                } else if (resource === 'memory') {
                    resourceValue = plan.memory_limit_per_container;
                } else {
                    resourceValue = plan.storage_limit_per_container;
                }
                return TerminalsUtilities.isConfigurable(resourceValue);
            });

            // Build info message
            if (configurablePlans.length > 0) {
                const planNames = configurablePlans.map(p => p.name).join(', ');
                const infoMessage = `ℹ️ Only available to ${planNames} subscription${configurablePlans.length > 1 ? 's' : ''}`;
                if (info) {
                    info.textContent = infoMessage;
                    info.style.display = 'block';
                }
            } else {
                const infoMessage = 'ℹ️ Coming soon';
                if (info) {
                    info.textContent = infoMessage;
                    info.style.display = 'block';
                }
            }
        }
    }

    /**
     * Load terminals from API
     */
    async loadTerminals() {
        try {
            const userInfo = TerminalsUtilities.getUserInfo();
            if (!userInfo.id) {
                console.log('No user ID available, cannot load terminals');
                this.terminals = [];
                this.renderTerminalsList();
                return;
            }

            const response = await fetch(`/list-user-containers?user_id=${userInfo.id}`);
            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'Failed to load terminals');
            }

            // Transform API response to terminal format and sort by created_at descending
            this.terminals = (result.containers || [])
                .map(container => ({
                    id: container.id,
                    name: container.name,
                    ipAddress: container.ip_address || 'Pending...',
                    port: container.port_mappings?.[0]?.publish_port || '-',
                    status: container.status || 'Pending',
                    createdAt: container.created_at,
                    kubernetes_id: container.kubernetes_id || null
                }))
                .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));

            this.renderTerminalsList();
        } catch (error) {
            console.error('Error loading terminals:', error);
            this.showError('Error loading terminals. Please try again.');
            TerminalsUtilities.showNotification(
                'error',
                'Loading Error',
                'Failed to load terminals',
                5000
            );
        }
    }

    /**
     * Render terminals list
     */
    renderTerminalsList() {
        if (this.terminals.length === 0) {
            this.elements.terminalsList.innerHTML = 
                '<div class="loading-message">No terminals found.</div>';
            return;
        }

        const terminalsHTML = this.terminals
            .map(terminal => this.renderTerminalItem(terminal))
            .join('');

        this.elements.terminalsList.innerHTML = terminalsHTML;

        // Re-attach terminal control listeners
        this.attachTerminalControls();
    }

    /**
     * Get controls HTML based on terminal status
     * @param {string} terminalId - Terminal ID
     * @param {string} status - Terminal status (lowercase)
     * @param {string|null} kubernetesId - Kubernetes ID for K8s deletion
     * @returns {string} HTML string for controls
     */
    getControlsHTML(terminalId, status, kubernetesId = null) {
        // Define controls configuration for each status
        const controlsConfig = {
            running: {
                showPlay: true,
                showDelete: true,
                showLoading: false
            },
            failed: {
                showPlay: false,
                showDelete: true,
                showLoading: false
            },
            pending: {
                showPlay: false,
                showDelete: false,
                showLoading: true
            },
            succeeded: {
                showPlay: false,
                showDelete: false,
                showLoading: true
            },
            unknown: {
                showPlay: false,
                showDelete: false,
                showLoading: true
            }
        };

        const config = controlsConfig[status] || controlsConfig.pending;

        if (config.showLoading) {
            return `
                <div class="terminal-loading">
                    <span class="loading-spinner"></span>
                    <span class="loading-text">Creating...</span>
                </div>`;
        }

        let html = '';
        if (config.showPlay) {
            html += `
                <button class="control-btn play-btn" data-terminal-id="${terminalId}">
                    <i class="fas fa-play"></i>
                </button>`;
        }
        if (config.showDelete) {
            html += `
                <button class="control-btn delete-btn" data-terminal-id="${terminalId}" data-kubernetes-id="${kubernetesId || ''}">
                    <i class="fas fa-trash"></i>
                </button>`;
        }
        return html;
    }

    /**
     * Render a single terminal item
     * @param {Object} terminal - Terminal data
     * @returns {string} HTML string for terminal item
     */
    renderTerminalItem(terminal) {
        // Status values: Pending, Running, Succeeded, Failed, Unknown
        const statusLower = (terminal.status || 'Pending').toLowerCase();
        const statusText = terminal.status || 'Pending';
        const controlsHTML = this.getControlsHTML(terminal.id, statusLower, terminal.kubernetes_id);

        return `
            <div class="terminal-item" data-terminal-id="${terminal.id}">
                <div class="terminal-info">
                    <div class="terminal-name">${terminal.name}</div>
                    <div class="terminal-ip">
                        <div class="ip-address">${terminal.ipAddress || 'Pending...'}</div>
                        <div class="port">${terminal.port || '-'}</div>
                    </div>
                    <div class="terminal-status ${statusLower}">${statusText}</div>
                </div>
                <div class="terminal-controls">
                    ${controlsHTML}
                </div>
            </div>
        `;
    }

    /**
     * Setup all event listeners
     */
    setupEventListeners() {
        // New terminal button
        if (this.elements.newTerminalBtn) {
            this.elements.newTerminalBtn.addEventListener('click', () => this.openModal());
        }

        // Modal close buttons
        if (this.elements.modalClose) {
            this.elements.modalClose.addEventListener('click', () => this.closeModal());
        }

        if (this.elements.cancelBtn) {
            this.elements.cancelBtn.addEventListener('click', () => this.closeModal());
        }

        if (this.elements.modalOverlay) {
            this.elements.modalOverlay.addEventListener('click', (e) => {
                if (e.target === this.elements.modalOverlay) {
                    this.closeModal();
                }
            });
        }

        // Form submission
        if (this.elements.terminalForm) {
            this.elements.terminalForm.addEventListener('submit', (e) => this.handleFormSubmit(e));
        }

        // CPU/Memory increment/decrement buttons
        this.setupNumberInputs();
    }

    /**
     * Attach event listeners to terminal control buttons
     */
    attachTerminalControls() {
        const playBtns = document.querySelectorAll('.play-btn');
        const deleteBtns = document.querySelectorAll('.delete-btn');

        playBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const terminalId = e.target.closest('button').getAttribute('data-terminal-id');
                this.handlePlay(terminalId);
            });
        });

        deleteBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const button = e.target.closest('button');
                const terminalId = button.getAttribute('data-terminal-id');
                const kubernetesId = button.getAttribute('data-kubernetes-id');
                this.handleDelete(terminalId, kubernetesId);
            });
        });
    }

    /**
     * Setup number input controls (CPU/Memory)
     * Only adds listeners if the control is enabled based on subscription
     */
    setupNumberInputs() {
        // CPU controls - only if configurable
        if (this.cpuConfigurable && this.elements.cpuDecrease && this.elements.cpuIncrease && this.elements.cpuInput) {
            this.elements.cpuDecrease.addEventListener('click', () => 
                TerminalsUtilities.adjustNumber(this.elements.cpuInput, -1)
            );
            this.elements.cpuIncrease.addEventListener('click', () => 
                TerminalsUtilities.adjustNumber(this.elements.cpuInput, 1)
            );
            console.log('CPU controls enabled');
        } else {
            console.log('CPU controls disabled (not available in current plan)');
        }

        // Memory controls - only if configurable
        if (this.memoryConfigurable && this.elements.memoryDecrease && this.elements.memoryIncrease && this.elements.memoryInput) {
            this.elements.memoryDecrease.addEventListener('click', () =>
                TerminalsUtilities.adjustNumber(this.elements.memoryInput, -1)
            );
            this.elements.memoryIncrease.addEventListener('click', () =>
                TerminalsUtilities.adjustNumber(this.elements.memoryInput, 1)
            );
            console.log('Memory controls enabled');
        } else {
            console.log('Memory controls disabled (not available in current plan)');
        }

        // Storage controls - only if configurable
        if (this.storageConfigurable && this.elements.storageDecrease && this.elements.storageIncrease && this.elements.storageInput) {
            this.elements.storageDecrease.addEventListener('click', () =>
                TerminalsUtilities.adjustNumber(this.elements.storageInput, -1)
            );
            this.elements.storageIncrease.addEventListener('click', () =>
                TerminalsUtilities.adjustNumber(this.elements.storageInput, 1)
            );
            console.log('Storage controls enabled');
        } else {
            console.log('Storage controls disabled (not available in current plan)');
        }
    }

    /**
     * Setup SSE connection for real-time container status updates
     */
    setupStatusStream() {
        const userInfo = TerminalsUtilities.getUserInfo();
        if (!userInfo.id) {
            console.log('No user ID available, skipping SSE setup');
            return;
        }

        const eventSource = new EventSource(`/container-status-stream?user_id=${userInfo.id}`);

        eventSource.onopen = () => {
            console.log('SSE connection established for status updates');
        };

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log('SSE message received:', data);

                if (data.type === 'connected') {
                    console.log('SSE connected for user:', data.user_id);
                    return;
                }

                if (data.type === 'status_change') {
                    this.handleStatusChange(data);
                }
            } catch (error) {
                console.error('Error parsing SSE message:', error);
            }
        };

        eventSource.onerror = (error) => {
            console.error('SSE connection error:', error);
            // EventSource will auto-reconnect
        };

        // Store reference for cleanup if needed
        this.eventSource = eventSource;
    }

    /**
     * Handle container status change from SSE
     * @param {Object} data - Status change data
     */
    async handleStatusChange(data) {
        const { container_id, name, old_status, new_status } = data;
        console.log(`Container ${name} (${container_id}) status changed: ${old_status} -> ${new_status}`);

        // Find and update the terminal in our list
        const terminalIndex = this.terminals.findIndex(t => t.id === container_id);
        if (terminalIndex === -1) return;

        this.terminals[terminalIndex].status = new_status;
        this.renderTerminalsList();

        // Get pending info for this container
        const pendingInfo = this.pendingContainers.get(container_id);

        // Status handlers configuration
        const statusHandlers = {
            'Running': () => this.handleRunningStatus(container_id, name, pendingInfo),
            'Failed': () => this.handleFailedStatus(container_id, name, pendingInfo)
        };

        const handler = statusHandlers[new_status];
        if (handler) await handler();
    }

    /**
     * Handle container reaching Running status
     * @param {string} containerId - Container ID
     * @param {string} name - Container name
     * @param {Object|undefined} pendingInfo - Pending container info
     */
    handleRunningStatus(containerId, name, pendingInfo) {
        // Container is now running - remove from pending tracking
        if (pendingInfo) {
            this.pendingContainers.delete(containerId);
            console.log(`Container ${containerId} is now Running - removed from pending tracking`);
        }
        TerminalsUtilities.showNotification(
            'success',
            'Terminal Ready',
            `Terminal "${name}" is now running!`,
            4000
        );
    }

    /**
     * Handle container reaching Failed status
     * @param {string} containerId - Container ID
     * @param {string} name - Container name
     * @param {Object|undefined} pendingInfo - Pending container info
     */
    async handleFailedStatus(containerId, name, pendingInfo) {
        // Container failed - auto-cleanup only if it was pending
        if (!pendingInfo) {
            TerminalsUtilities.showNotification(
                'error',
                'Terminal Failed',
                `Terminal "${name}" failed.`,
                5000
            );
            return;
        }

        console.log(`Container ${containerId} failed before Running - auto-cleaning up...`);
        TerminalsUtilities.showNotification(
            'error',
            'Terminal Failed',
            `Terminal "${name}" failed to start. Cleaning up...`,
            5000
        );
        await this.cleanupFailedContainer(containerId, pendingInfo);
    }

    /**
     * Cleanup a failed container from K8s and DB
     * @param {string} containerId - Container DB ID
     * @param {Object} info - { kubernetesId, networkName, userId }
     */
    async cleanupFailedContainer(containerId, info) {
        try {
            console.log(`Cleaning up failed container ${containerId}...`);

            // Remove from pending tracking first
            this.pendingContainers.delete(containerId);

            // Step 1: Delete from K8s (if we have the kubernetes_id)
            if (info.kubernetesId) {
                await this.deleteContainerFromK8s(info.kubernetesId, info.networkName);
            }

            // Step 2: Delete from DB
            await this.deleteContainerFromDB(containerId, info.userId);

            // Step 3: Refresh the list
            await this.loadTerminals();

            console.log(`Cleanup complete for container ${containerId}`);
        } catch (error) {
            console.error(`Error during cleanup of container ${containerId}:`, error);
            // Still try to refresh the list
            await this.loadTerminals();
        }
    }

    /**
     * Handle play button click
     * @param {string} terminalId - Terminal ID
     */
    handlePlay(terminalId) {
        console.log('Play button clicked for terminal:', terminalId);
        window.open(`/terminalpage?id=${terminalId}`, '_blank');
    }

    /**
     * Handle delete button click
     * @param {string} terminalId - Terminal DB ID
     * @param {string} kubernetesId - Kubernetes pod ID (from data attribute)
     */
    async handleDelete(terminalId, kubernetesId) {
        console.log('Delete button clicked for terminal:', terminalId, 'kubernetes_id:', kubernetesId);

        // Find the terminal to get its name for confirmation
        const terminal = this.terminals.find(t => t.id === terminalId);
        const terminalName = terminal?.name || 'Unknown';

        // Confirm deletion
        const confirmed = confirm(`Are you sure you want to delete terminal "${terminalName}"?`);
        if (!confirmed) {
            return;
        }

        const userInfo = TerminalsUtilities.getUserInfo();
        const networkName = `${userInfo.id}-namespace`;

        try {
            // Step 1: Delete from DB first
            await this.deleteContainerFromDB(terminalId, userInfo.id);

            // Step 2: Refresh the list immediately (so user sees it removed)
            await this.loadTerminals();

            TerminalsUtilities.showNotification(
                'info',
                'Terminal Deleted',
                `Terminal "${terminalName}" has been deleted.`,
                4000
            );

            // Step 3: Delete from K8s in the background (user doesn't need to wait)
            if (kubernetesId) {
                this.deleteContainerFromK8s(kubernetesId, networkName).catch(err => {
                    console.error('Background K8s deletion failed:', err);
                });
            }

        } catch (error) {
            console.error('Error deleting terminal:', error);
            TerminalsUtilities.showNotification(
                'error',
                'Deletion Error',
                error.message,
                5000
            );
        }
    }

    /**
     * Open modal for creating new terminal
     */
    openModal() {
        this.elements.modalOverlay.classList.add('active');
        document.body.style.overflow = 'hidden';
        this.resetForm();
    }

    /**
     * Close modal
     */
    closeModal() {
        this.elements.modalOverlay.classList.remove('active');
        document.body.style.overflow = '';
    }

    /**
     * Reset terminal creation form
     */
    resetForm() {
        this.elements.terminalForm.reset();
        this.elements.cpuInput.value = 1;
        this.elements.memoryInput.value = 1;
        this.elements.storageInput.value = 2;
    }

    /**
     * Load operating systems for modal select
     */
    async loadOperatingSystems() {
        try {
            this.operatingSystems = TerminalsUtilities.getOperatingSystems();
            this.populateOperatingSystems();
        } catch (error) {
            console.error('Error loading operating systems:', error);
            this.elements.operatingSystemSelect.innerHTML = 
                '<option value="">Error loading OS</option>';
            TerminalsUtilities.showNotification(
                'error',
                'Loading Error',
                'Failed to load operating systems',
                5000
            );
        }
    }

    /**
     * Populate operating systems dropdown
     */
    populateOperatingSystems() {
        this.elements.operatingSystemSelect.innerHTML = '';

        if (this.operatingSystems.length === 0) {
            this.elements.operatingSystemSelect.innerHTML = 
                '<option value="">No operating systems available</option>';
            return;
        }

        this.operatingSystems.forEach(os => {
            const option = document.createElement('option');
            // Use the name as value so we can resolve by name later
            option.value = os.name;
            option.textContent = os.name;
            this.elements.operatingSystemSelect.appendChild(option);
        });
    }

    /**
     * Handle form submission
     * Two-step process:
     * 1. Create container in DB (fast) - closes modal and shows loading in terminal list
     * 2. Create container in K8s (slow) - happens in background, status updates via SSE
     * @param {Event} e - Form submit event
     */
    async handleFormSubmit(e) {
        e.preventDefault();

        // Get the submit button and show loading state
        const submitBtn = document.getElementById('submitBtn');
        const originalText = submitBtn.textContent;

        // Show loading spinner
        this.showLoadingState(submitBtn);

        try {
            // resolve user_id and generated username
            const userInfo = TerminalsUtilities.getUserInfo();
            const userName = userInfo.name || '';
            const generatedUsername = TerminalsUtilities.normalizeName(userName);

            // form data
            const formData = new FormData(e.target);

            // resolve image name from dropdown selection
            const selectedImageName = (formData.get('os') || '').toString();
            const imageRecord = TerminalsUtilities.findImageByName(selectedImageName);

            // Get resource values (use defaults for non-configurable)
            const cpuValue = this.cpuConfigurable ? parseInt(formData.get('cpu')) : 1;
            const memoryValue = this.memoryConfigurable ? parseInt(formData.get('memory')) : 1;
            const storageValue = this.storageConfigurable ? parseInt(formData.get('storage')) : 2;

            // Step 1: Create container in DB
            const dbData = {
                user_id: userInfo.id || '',
                image_id: imageRecord.id || '',
                name: (formData.get('name') || '').toString(),
                port_mappings: [{
                    publish_port: 2222,
                    target_port: 22,
                    protocol: 'TCP'
                }],
                environment_variables: {
                    SSH_USERNAME: generatedUsername,
                    SSH_PASSWORD: TerminalsUtilities.generatePassword(8)
                },
                cpu_limit: `${cpuValue}`,
                memory_limit: `${memoryValue}Gi`,
                storage_limit: `${storageValue}Gi`
            };

            const dbResponse = await fetch('/create-container-in-db', {
                method: 'POST',
                body: JSON.stringify(dbData),
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            const dbResult = await dbResponse.json();
            if (!dbResponse.ok) {
                throw new Error(dbResult.error);
            }
            console.log('Container created in DB:', dbResult);

            // Close modal immediately after DB success
            this.closeModal();

            // Add the new terminal to the list with loading state
            const newTerminal = {
                id: dbResult.id,
                name: dbResult.name,
                ipAddress: dbResult.ip_address || 'Pending...',
                port: dbResult.port_mappings?.[0]?.publish_port || '-',
                status: dbResult.status || 'Pending'
            };
            this.terminals.unshift(newTerminal);
            this.renderTerminalsList();

            // Show info notification
            TerminalsUtilities.showNotification(
                'info',
                'Terminal Queued',
                'Your terminal is being created. This may take a moment...',
                4000
            );

            // Step 2: Create container in K8s (fire and forget - status updates come via SSE)
            const k8sData = {
                container_id: dbResult.id,
                user_id: userInfo.id || '',
                image_id: imageRecord.id || '',
                container_name: (formData.get('name') || '').toString(),
                network_name: `${userInfo.id}-namespace`,
                exposure_level: 2,  // CLUSTER_LOCAL
                publish_information: [{
                    publish_port: 2222,
                    target_port: 22,
                    protocol: 'TCP'
                }],
                environment_variables: {
                    SSH_USERNAME: generatedUsername,
                    SSH_PASSWORD: dbData.environment_variables.SSH_PASSWORD,
                },
                resource_limits: {
                    cpu_limit: `${cpuValue}`,
                    memory_limit: `${memoryValue}Gi`,
                    storage_limit: `${storageValue}Gi`,
                    snapshot_size_limit: `${storageValue}Gi`
                }
            };

            // Step 2: Create container in K8s
            const k8sResponse = await fetch('/create-container-in-k8s', {
                method: 'POST',
                body: JSON.stringify(k8sData),
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            const k8sResult = await k8sResponse.json();

            if (k8sResult.error) {
                console.error('K8s creation error:', k8sResult.error);
                // K8s creation failed - delete from DB and refresh list
                await this.deleteContainerFromDB(dbResult.id, userInfo.id);
                await this.loadTerminals();
                TerminalsUtilities.showNotification(
                    'error',
                    'Creation Error',
                    k8sResult.error,
                    5000
                );
                return;
            }

            console.log('K8s creation successful:', k8sResult);

            // Step 3: Update container with K8s info
            const updateData = {
                filters: {
                    container_id: dbResult.id
                },
                data: {
                    kubernetes_id: k8sResult.container_id,
                    ip_address: k8sResult.container_ip,
                    associated_resources: k8sResult.associated_resources
                }
            };

            const updateResponse = await fetch('/update-container', {
                method: 'POST',
                body: JSON.stringify(updateData),
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            const updateResult = await updateResponse.json();

            if (updateResult.error) {
                console.error('Update container error:', updateResult.error);
                // Update failed - delete from K8s and DB, then refresh list
                await this.deleteContainerFromK8s(k8sResult.container_id, `${userInfo.id}-namespace`);
                await this.deleteContainerFromDB(dbResult.id, userInfo.id);
                await this.loadTerminals();
                TerminalsUtilities.showNotification(
                    'error',
                    'Update Error',
                    updateResult.error,
                    5000
                );
                return;
            }

            console.log('Container updated with K8s info:', updateResult);

            // Update local terminal data with new IP and kubernetes_id
            const terminalIndex = this.terminals.findIndex(t => t.id === dbResult.id);
            if (terminalIndex !== -1) {
                this.terminals[terminalIndex].ipAddress = k8sResult.container_ip;
                this.terminals[terminalIndex].kubernetes_id = k8sResult.container_id;
                this.renderTerminalsList();
            }

            // Track this container as pending - will auto-cleanup if it fails before Running
            this.pendingContainers.set(dbResult.id, {
                kubernetesId: k8sResult.container_id,
                networkName: `${userInfo.id}-namespace`,
                userId: userInfo.id
            });
            console.log(`Container ${dbResult.id} added to pending tracking - will auto-cleanup on failure`);

        } catch (error) {
            console.error('Error submitting form:', error);
            TerminalsUtilities.showNotification(
                'error',
                'Submission Error',
                error.message,
                5000
            );
        } finally {
            // Hide loading state and restore button
            this.hideLoadingState(submitBtn, originalText);
        }
    }

    /**
     * Delete container from K8s
     * @param {string} containerId - Container ID (kubernetes_id)
     * @param {string} networkName - Network name
     */
    async deleteContainerFromK8s(containerId, networkName) {
        try {
            const response = await fetch('/delete-container-in-k8s', {
                method: 'POST',
                body: JSON.stringify({
                    container_id: containerId,
                    network_name: networkName
                }),
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            const result = await response.json();
            if (result.error) {
                console.error('K8s deletion error:', result.error);
            }
            return result;
        } catch (error) {
            console.error('Error deleting from K8s:', error);
        }
    }

    /**
     * Delete container from DB
     * @param {string} containerId - Container ID
     * @param {string} userId - User ID
     */
    async deleteContainerFromDB(containerId, userId) {
        try {
            const response = await fetch('/delete-container-in-db', {
                method: 'POST',
                body: JSON.stringify({
                    container_id: containerId,
                    user_id: userId
                }),
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            const result = await response.json();
            if (result.error) {
                console.error('DB deletion error:', result.error);
            }
            return result;
        } catch (error) {
            console.error('Error deleting from DB:', error);
        }
    }

    /**
     * Show loading state on button
     * @param {HTMLElement} button - Button element to show loading state
     */
    showLoadingState(button) {
        if (!button) return;
        button.disabled = true;
        button.innerHTML = `
            <span class="loading-spinner"></span>
            Creating Terminal...
        `;
        button.classList.add('loading');
    }

    /**
     * Hide loading state and restore button
     * @param {HTMLElement} button - Button element to restore
     * @param {string} originalText - Original button text
     */
    hideLoadingState(button, originalText) {
        if (!button) return;
        button.disabled = false;
        button.textContent = originalText;
        button.classList.remove('loading');
    }

    /**
     * Show error message in UI
     * @param {string} message - Error message
     */
    showError(message) {
        this.elements.terminalsList.innerHTML = 
            `<div class="loading-message error">${message}</div>`;
    }
}

// Initialize terminals handler when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('Terminals page DOM is ready');
    const terminalsHandler = new TerminalsHandler();
    terminalsHandler.init();
});
