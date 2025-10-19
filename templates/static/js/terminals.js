/**
 * TerminalsUtilities
 * Utility methods for terminals page functionality
 */
class TerminalsUtilities {
    /**
     * Dummy data for terminals (for testing)
     */
    static DUMMY_TERMINALS = [
        {
            id: "term-001",
            name: "ubuntu-dev",
            ipAddress: "192.168.1.100",
            port: "8080",
            status: "running"
        },
        {
            id: "term-002", 
            name: "node-app",
            ipAddress: "192.168.1.101",
            port: "3000",
            status: "stopped"
        },
        {
            id: "term-003",
            name: "python-script", 
            ipAddress: "192.168.1.102",
            port: "5000",
            status: "pending"
        },
        {
            id: "term-004",
            name: "docker-container",
            ipAddress: "192.168.1.103", 
            port: "80",
            status: "active"
        },
        {
            id: "term-005",
            name: "react-frontend",
            ipAddress: "192.168.1.104",
            port: "3001", 
            status: "running"
        }
    ];

    /**
     * Dummy data for operating systems (for testing)
     */
    static DUMMY_OPERATING_SYSTEMS = [
        { id: "ubuntu", name: "Ubuntu" }
    ];

    /**
     * Dummy user data (for testing)
     */
    static DUMMY_USER = {
        name: "Namah Shrestha",
        email: "test@gmail.com"
    };

    /**
     * Simulate API call to fetch terminals
     * @returns {Promise<Object>} Terminals data
     */
    static async fetchTerminals() {
        console.log('Fetching terminals...');
        await new Promise(resolve => setTimeout(resolve, 1000));
        return { terminals: TerminalsUtilities.DUMMY_TERMINALS };
    }

    /**
     * Simulate API call to fetch operating systems
     * @returns {Promise<Object>} Operating systems data
     */
    static async fetchOperatingSystems() {
        console.log('Fetching operating systems...');
        await new Promise(resolve => setTimeout(resolve, 500));
        return { operatingSystems: TerminalsUtilities.DUMMY_OPERATING_SYSTEMS };
    }

    /**
     * Simulate API call to fetch user data
     * @returns {Promise<Object>} User data
     */
    static async fetchUser() {
        console.log('Fetching user data...');
        await new Promise(resolve => setTimeout(resolve, 200));
        return { user: TerminalsUtilities.DUMMY_USER };
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
    }

    /**
     * Initialize terminals page
     */
    async init() {
        console.log('Terminals page loaded successfully!');

        // Cache DOM elements
        this.cacheElements();

        // Load terminals
        await this.loadTerminals();

        // Load operating systems for modal
        await this.loadOperatingSystems();

        // Setup event listeners
        this.setupEventListeners();
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
            memoryIncrease: document.getElementById('memoryIncrease')
        };
    }

    /**
     * Load terminals from API
     */
    async loadTerminals() {
        try {
            const data = await TerminalsUtilities.fetchTerminals();
            this.terminals = data.terminals;
            console.log('Terminals loaded:', this.terminals);
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
     * Render a single terminal item
     * @param {Object} terminal - Terminal data
     * @returns {string} HTML string for terminal item
     */
    renderTerminalItem(terminal) {
        const statusClass = terminal.status.toLowerCase();
        const statusText = TerminalsUtilities.formatStatus(terminal.status);

        return `
            <div class="terminal-item" data-terminal-id="${terminal.id}">
                <div class="terminal-info">
                    <div class="terminal-name">${terminal.name}</div>
                    <div class="terminal-ip">
                        <div class="ip-address">${terminal.ipAddress}</div>
                        <div class="port">${terminal.port}</div>
                    </div>
                    <div class="terminal-status ${statusClass}">${statusText}</div>
                </div>
                <div class="terminal-controls">
                    <button class="control-btn play-btn" data-terminal-id="${terminal.id}">
                        <i class="fas fa-play"></i>
                    </button>
                    <button class="control-btn delete-btn" data-terminal-id="${terminal.id}">
                        <i class="fas fa-trash"></i>
                    </button>
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
                const terminalId = e.target.closest('button').getAttribute('data-terminal-id');
                this.handleDelete(terminalId);
            });
        });
    }

    /**
     * Setup number input controls (CPU/Memory)
     */
    setupNumberInputs() {
        // CPU controls
        if (this.elements.cpuDecrease && this.elements.cpuIncrease && this.elements.cpuInput) {
            this.elements.cpuDecrease.addEventListener('click', () => 
                TerminalsUtilities.adjustNumber(this.elements.cpuInput, -1)
            );
            this.elements.cpuIncrease.addEventListener('click', () => 
                TerminalsUtilities.adjustNumber(this.elements.cpuInput, 1)
            );
        }

        // Memory controls
        if (this.elements.memoryDecrease && this.elements.memoryIncrease && this.elements.memoryInput) {
            this.elements.memoryDecrease.addEventListener('click', () => 
                TerminalsUtilities.adjustNumber(this.elements.memoryInput, -1)
            );
            this.elements.memoryIncrease.addEventListener('click', () => 
                TerminalsUtilities.adjustNumber(this.elements.memoryInput, 1)
            );
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
     * @param {string} terminalId - Terminal ID
     */
    handleDelete(terminalId) {
        console.log('Delete button clicked for terminal:', terminalId);
        // TODO: Implement delete functionality
        TerminalsUtilities.showNotification(
            'info',
            'Coming Soon',
            'Terminal deletion will be available soon!',
            3000
        );
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
    }

    /**
     * Load operating systems for modal select
     */
    async loadOperatingSystems() {
        try {
            const data = await TerminalsUtilities.fetchOperatingSystems();
            this.operatingSystems = data.operatingSystems;
            console.log('Operating systems loaded:', this.operatingSystems);
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
            option.value = os.id;
            option.textContent = os.name;
            this.elements.operatingSystemSelect.appendChild(option);
        });
    }

    /**
     * Handle form submission
     * @param {Event} e - Form submit event
     */
    async handleFormSubmit(e) {
        e.preventDefault();

        try {
            // Get form data
            const formData = new FormData(e.target);
            const terminalData = {
                name: formData.get('name'),
                os: formData.get('os'),
                network: formData.get('network'),
                cpu: parseInt(formData.get('cpu')),
                memory: parseInt(formData.get('memory'))
            };

            // Get user data
            const userData = await TerminalsUtilities.fetchUser();

            // Combine all data
            const submissionData = {
                terminal: terminalData,
                user: userData.user,
                timestamp: new Date().toISOString()
            };

            // Console log the data
            console.log('Terminal Creation Data:', submissionData);

            // Show success notification
            TerminalsUtilities.showNotification(
                'success',
                'Terminal Created',
                'Terminal creation data logged to console!',
                4000
            );

            // Close modal
            this.closeModal();

        } catch (error) {
            console.error('Error submitting form:', error);
            TerminalsUtilities.showNotification(
                'error',
                'Submission Error',
                'Error submitting form. Please try again.',
                5000
            );
        }
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
