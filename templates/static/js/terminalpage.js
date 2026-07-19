/**
 * TerminalPageUtilities
 * Utility methods for terminal page functionality
 */
class TerminalPageUtilities {
    /**
     * Get terminal ID from URL parameters
     * @returns {string|null} Terminal ID
     */
    static getTerminalIdFromURL() {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get('id');
    }

    /**
     * Get terminal info from window object (passed from backend)
     * @returns {Object} Terminal info
     */
    static getTerminalInfoFromTemplate() {
        return window.terminalInfo || {};
    }

    /**
     * Get Socket SSH WebSocket URL from window object (passed from backend)
     * @returns {string} WebSocket URL
     */
    static getSocketSSHUrl() {
        return window.socketSSHUrl || '';
    }

    /**
     * Get WebSocket token from window object (passed from backend)
     * @returns {string} WebSocket token
     */
    static getWsToken() {
        return window.wsToken || '';
    }

    /**
     * Get xterm theme configuration (terminal always uses dark theme)
     * @returns {Object} Xterm theme object
     */
    static getXtermTheme() {
        return {
            background: '#1e1e1e',
            foreground: '#d4d4d4',
            cursor: '#d4d4d4',
            black: '#000000',
            red: '#cd3131',
            green: '#0dbc79',
            yellow: '#e5e510',
            blue: '#2472c8',
            magenta: '#bc3fbc',
            cyan: '#11a8cd',
            white: '#e5e5e5',
            brightBlack: '#666666',
            brightRed: '#f14c4c',
            brightGreen: '#23d18b',
            brightYellow: '#f5f543',
            brightBlue: '#3b8eea',
            brightMagenta: '#d670d6',
            brightCyan: '#29b8db',
            brightWhite: '#ffffff'
        };
    }

    /**
     * Get color code for colored terminal text
     * @param {string} color - Color name
     * @returns {string} ANSI color code
     */
    static getColorCode(color) {
        const colorCodes = {
            red: '\x1b[31m',
            green: '\x1b[32m',
            yellow: '\x1b[33m',
            blue: '\x1b[34m',
            magenta: '\x1b[35m',
            cyan: '\x1b[36m',
            white: '\x1b[37m',
            reset: '\x1b[0m'
        };
        return colorCodes[color] || colorCodes.reset;
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
 * TerminalPageHandler
 * Handles terminal page functionality and xterm.js integration
 */
class TerminalPageHandler {
    /**
     * Initialize the terminal page handler
     */
    constructor() {
        console.log('TerminalPageHandler initialized');
        this.elements = {};
        this.terminalId = null;
        this.terminalInfo = null;
        this.term = null;
        this.fitAddon = null;
        this.websocket = null;
        this.socketSSHUrl = '';
        this.wsToken = '';  // WebSocket authentication token
        this.sshHash = '';  // Unique hash for this SSH session
        this.isConnected = false;
        this.isSSHConnected = false;
    }

    /**
     * Initialize terminal page
     */
    async init() {
        console.log('Terminal page loaded successfully!');

        // Get terminal ID and info
        this.terminalId = TerminalPageUtilities.getTerminalIdFromURL();
        this.terminalInfo = TerminalPageUtilities.getTerminalInfoFromTemplate();
        this.socketSSHUrl = TerminalPageUtilities.getSocketSSHUrl();
        this.wsToken = TerminalPageUtilities.getWsToken();
        
        console.log('Terminal ID:', this.terminalId);
        console.log('Terminal info:', this.terminalInfo);
        console.log('Socket SSH URL:', this.socketSSHUrl);

        // Cache DOM elements
        this.cacheElements();

        // Initialize dark mode
        this.initializeDarkMode();

        // Check for errors in terminal info
        if (this.terminalInfo.error) {
            this.showError(this.terminalInfo.error);
            return;
        }

        // Check if terminal is in Running status
        if (this.terminalInfo.status !== 'Running') {
            this.showError(`Terminal is not running. Current status: ${this.terminalInfo.status}`);
            return;
        }

        // Generate SSH hash for this session
        this.sshHash = `ssh_${this.terminalId}_${Date.now()}`;

        // Initialize xterm.js terminal
        this.initializeTerminal();

        // Load terminal info into UI
        this.loadTerminalInfo();

        // Setup event listeners
        this.setupEventListeners();

        // Connect to terminal via WebSocket
        this.connectToTerminal();

        // Handle window resize
        window.addEventListener('resize', () => this.handleResize());
    }

    /**
     * Cache DOM elements
     */
    cacheElements() {
        this.elements = {
            terminal: document.getElementById('terminal'),
            terminalName: document.getElementById('terminalName'),
            terminalIp: document.getElementById('terminalIp'),
            terminalPort: document.getElementById('terminalPort'),
            saveBtn: document.getElementById('saveBtn')
        };
    }

    /**
     * Initialize dark mode on page load
     */
    initializeDarkMode() {
        const savedTheme = localStorage.getItem('theme');
        
        // Set default to 'light' if no preference is saved
        if (!savedTheme) {
            localStorage.setItem('theme', 'light');
        }

        // Apply dark mode if explicitly saved as 'dark'
        if (savedTheme === 'dark') {
            document.body.classList.add('dark-mode');
        }

        // Remove loading class
        document.documentElement.classList.remove('dark-mode-loading');

        console.log('Terminal page dark mode initialized:', 
            document.body.classList.contains('dark-mode') ? 'enabled' : 'disabled');
    }

    /**
     * Initialize xterm.js terminal
     */
    initializeTerminal() {
        console.log('Initializing terminal...');

        // Terminal is always dark - only the UI changes with theme toggle
        const terminalTheme = TerminalPageUtilities.getXtermTheme();

        // Create terminal instance
        this.term = new Terminal({
            cursorBlink: true,
            fontSize: 14,
            fontFamily: 'Menlo, Monaco, "Courier New", monospace',
            theme: terminalTheme,
            scrollback: 10000,  // Enable 10000 lines of scrollback buffer
            convertEol: true    // Automatically convert line endings
        });

        // Note: Terminal theme doesn't change with dark mode toggle
        // Only the surrounding UI changes
        window.xtermTheme = {
            applyTheme: (isDark) => {
                // Terminal stays dark regardless of UI theme
                console.log('UI theme updated:', isDark ? 'dark' : 'light', '(terminal stays dark)');
            }
        };

        // Create fit addon
        this.fitAddon = new FitAddon.FitAddon();
        this.term.loadAddon(this.fitAddon);

        // Open terminal in the container
        this.term.open(this.elements.terminal);

        // Fit terminal to container
        this.fitAddon.fit();

        // Write welcome message
        this.writeWelcomeMessage();

        // Auto-scroll to bottom when content is written - use xterm's built-in scrollToBottom
        this.term.onWriteParsed(() => {
            // Refit and scroll after any content change
            setTimeout(() => {
                this.fitAddon.fit();
                this.term.scrollToBottom();
            }, 0);
        });

        // Handle terminal input
        this.term.onData(data => this.handleTerminalInput(data));

        console.log('Terminal initialized successfully!');
    }

    /**
     * Write welcome message to terminal
     */
    writeWelcomeMessage() {
        this.term.writeln('\x1b[1;32m╔══════════════════════════════════════════╗\x1b[0m');
        this.term.writeln('\x1b[1;32m║                                          ║\x1b[0m');
        this.term.writeln('\x1b[1;32m║         Welcome to BrowseTerm!           ║\x1b[0m');
        this.term.writeln('\x1b[1;32m║                                          ║\x1b[0m');
        this.term.writeln('\x1b[1;32m╚══════════════════════════════════════════╝\x1b[0m');
        this.term.writeln('');
        this.term.writeln('\x1b[1;36mConnecting to your terminal...\x1b[0m');
        this.term.writeln('');
    }

    /**
     * Load terminal information into UI
     */
    loadTerminalInfo() {
        console.log('Loading terminal info...');

        // Update UI with terminal info
        if (this.terminalInfo.name) {
            this.elements.terminalName.textContent = this.terminalInfo.name;
        }
        if (this.terminalInfo.ipAddress) {
            this.elements.terminalIp.textContent = this.terminalInfo.ipAddress;
        }
        if (this.terminalInfo.port) {
            this.elements.terminalPort.textContent = this.terminalInfo.port;
        }
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        if (this.elements.saveBtn) {
            this.elements.saveBtn.addEventListener('click', () => this.handleSaveSession());
        }
        this.setupSaveStatusStream();
    }

    /**
     * Handle window resize
     */
    handleResize() {
        if (this.fitAddon) {
            this.fitAddon.fit();
            this.term.scrollToBottom();
        }
    }

    /**
     * Handle terminal input
     * @param {string} data - Input data from terminal
     */
    handleTerminalInput(data) {
        // Send data to SSH server via WebSocket
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN && this.isSSHConnected) {
            const sshSendMessage = {
                type: 'sshSendData',
                data: {
                    ssh_hash: this.sshHash,
                    ssh_command: data
                }
            };
            this.websocket.send(JSON.stringify(sshSendMessage));
        } else {
            console.warn('WebSocket not connected or SSH not established');
        }
    }

    /**
     * Handle save session button click
     */
    async handleSaveSession() {
        const containerId = this.terminalInfo.id;
        const userInfo = window.userInfo || {};
        const networkName = `${userInfo.id}-namespace`;

        if (!containerId) {
            TerminalPageUtilities.showNotification('error', 'Save failed', 'No container id available.', 5000);
            return;
        }

        this.setSaveSpinner(true);
        try {
            const resp = await fetch('/save-container', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ container_id: containerId, network_name: networkName })
            });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.error || `HTTP ${resp.status}`);
            }
            // Spinner stays on until the SSE reports Succeeded/Failed.
            TerminalPageUtilities.showNotification('info', 'Saving', 'Snapshotting your container… this can take a little while.', 4000);
        } catch (e) {
            this.setSaveSpinner(false);
            TerminalPageUtilities.showNotification('error', 'Save failed', e.message, 6000);
        }
    }

    /**
     * Toggle the save button's in-progress (spinner) state.
     */
    setSaveSpinner(active) {
        const btn = this.elements.saveBtn;
        if (!btn) return;
        btn.disabled = active;
        btn.classList.toggle('saving', active);
        // Swap the label to "Saving…" while in progress, restore it afterwards.
        const label = btn.querySelector('span');
        if (label) {
            if (active) {
                if (!btn.dataset.label) btn.dataset.label = label.textContent;
                label.textContent = 'Saving…';
            } else if (btn.dataset.label) {
                label.textContent = btn.dataset.label;
            }
        }
    }

    /**
     * Subscribe to server-sent save-status events for this container and stop the
     * spinner when the snapshot finishes (Succeeded/Failed).
     */
    setupSaveStatusStream() {
        const userInfo = window.userInfo || {};
        if (!userInfo.id) return;
        const containerId = String(this.terminalInfo.id);

        const es = new EventSource(`/container-status-stream?user_id=${userInfo.id}`);
        es.onmessage = (event) => {
            let data;
            try { data = JSON.parse(event.data); } catch (e) { return; }
            if (data.type !== 'save_status_change') return;
            if (String(data.container_id) !== containerId) return;

            if (data.save_status === 'Succeeded') {
                this.setSaveSpinner(false);
                TerminalPageUtilities.showNotification('success', 'Saved', `Snapshot saved${data.saved_image ? ': ' + data.saved_image : ''}.`, 6000);
            } else if (data.save_status === 'Failed') {
                this.setSaveSpinner(false);
                TerminalPageUtilities.showNotification('error', 'Save failed', data.save_error || 'Snapshot failed.', 8000);
            }
            // Pending / Running: keep the spinner running.
        };
        es.onerror = () => { /* EventSource auto-reconnects */ };
        this._saveEventSource = es;
    }

    /**
     * Connect to terminal via WebSocket
     */
    connectToTerminal() {
        console.log('Connecting to terminal:', this.terminalInfo);

        if (!this.socketSSHUrl) {
            this.showError('WebSocket URL not configured');
            return;
        }

        if (!this.wsToken) {
            this.showError('WebSocket authentication token not available');
            return;
        }

        try {
            // Append WebSocket token to URL as query parameter
            const wsUrl = `${this.socketSSHUrl}?token=${this.wsToken}`;
            
            // Create WebSocket connection to socket-ssh server
            this.websocket = new WebSocket(wsUrl);

            this.websocket.onopen = () => {
                console.log('WebSocket connected to socket-ssh server');
                this.isConnected = true;
                this.term.writeln('\x1b[1;32m✓ Connected to WebSocket server\x1b[0m');
                this.term.writeln('\x1b[1;36m✓ Waiting for server to be ready...\x1b[0m');
            };

            this.websocket.onmessage = (event) => {
                this.handleWebSocketMessage(event);
            };

            this.websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.term.writeln('\x1b[1;31m✗ WebSocket connection error\x1b[0m');
                this.showError('Failed to connect to terminal server');
            };

            this.websocket.onclose = () => {
                console.log('WebSocket disconnected');
                this.isConnected = false;
                this.isSSHConnected = false;
                this.term.writeln('\x1b[1;33m\r\nConnection closed.\x1b[0m');
            };
        } catch (error) {
            console.error('Error creating WebSocket:', error);
            this.showError(`Failed to connect: ${error.message}`);
        }
    }

    /**
     * Initiate SSH connection through the WebSocket
     */
    initiateSSHConnection() {
        console.log('Initiating SSH connection...');

        if (!this.terminalInfo.sshUsername || !this.terminalInfo.sshPassword) {
            this.showError('SSH credentials not available');
            return;
        }

        // Send SSH connect request
        const sshConnectMessage = {
            type: 'sshConnect',
            data: {
                ssh_hash: this.sshHash,
                ssh_host: this.terminalInfo.ipAddress,
                ssh_port: parseInt(this.terminalInfo.port),
                ssh_username: this.terminalInfo.sshUsername,
                ssh_password: this.terminalInfo.sshPassword
            }
        };

        console.log('Sending SSH connect message:', {
            ...sshConnectMessage,
            data: { ...sshConnectMessage.data, ssh_password: '***' }
        });

        this.websocket.send(JSON.stringify(sshConnectMessage));
        this.term.writeln('\x1b[1;36m✓ Initiating SSH connection...\x1b[0m');
    }

    /**
     * Handle WebSocket messages
     * @param {MessageEvent} event - WebSocket message event
     */
    handleWebSocketMessage(event) {
        try {
            const data = JSON.parse(event.data);
            console.log('WebSocket message received:', data);

            // Handle 'ready' message from server
            if (data.type === 'ready') {
                console.log('Server ready - initiating SSH connection');
                this.term.writeln('\x1b[1;36m✓ Server ready\x1b[0m');
                this.initiateSSHConnection();
                return;
            }

            // Handle error messages
            if (data.error) {
                console.error('Server error:', data.error);
                this.term.writeln(`\r\n\x1b[1;31mError: ${data.error}\x1b[0m\r\n`);
                return;
            }

            // Handle SSH connection success (look for SSH prompt or welcome message)
            if (data.message && !this.isSSHConnected) {
                this.isSSHConnected = true;
                this.term.writeln('\x1b[1;32m✓ SSH connection established!\x1b[0m\r\n');
                
                // Show sudo password modal
                if (this.terminalInfo.sshPassword) {
                    this.showPasswordModal();
                }
            }

            // Write SSH output to terminal
            if (data.message) {
                this.term.write(data.message);
            }
        } catch (error) {
            // If not JSON, treat as raw SSH output
            console.log('Raw message:', event.data);
            this.term.write(event.data);
        }
    }

    /**
     * Write colored text to terminal
     * @param {string} text - Text to write
     * @param {string} color - Color name
     */
    writeColoredText(text, color) {
        const colorCode = TerminalPageUtilities.getColorCode(color);
        const resetCode = TerminalPageUtilities.getColorCode('reset');
        this.term.writeln(colorCode + text + resetCode);
    }

    /**
     * Show error message in terminal
     * @param {string} message - Error message
     */
    showError(message) {
        if (this.term) {
            this.term.writeln('');
            this.term.writeln('\x1b[1;31m╔══════════════════════════════════════════╗\x1b[0m');
            this.term.writeln('\x1b[1;31m║              ERROR                       ║\x1b[0m');
            this.term.writeln('\x1b[1;31m╚══════════════════════════════════════════╝\x1b[0m');
            this.term.writeln('');
            this.term.writeln(`\x1b[1;31m${message}\x1b[0m`);
            this.term.writeln('');
        }
        console.error('Terminal error:', message);
    }

    /**
     * Show password modal
     */
    showPasswordModal() {
        const modal = document.getElementById('passwordModal');
        const modalContent = document.getElementById('passwordModalContent');
        const passwordText = document.getElementById('passwordText');
        const closeBtn = document.getElementById('closePasswordModal');

        // Apply theme colors
        const isDark = document.body.classList.contains('dark-mode');
        modalContent.style.background = isDark ? '#252526' : '#ffffff';
        modalContent.style.color = isDark ? '#d4d4d4' : '#333333';

        // Set password
        passwordText.value = this.terminalInfo.sshPassword;
        
        // Show modal
        modal.style.display = 'flex';

        // Allow user to select and copy password manually
        passwordText.onclick = () => {
            passwordText.select();
        };

        // Close button
        closeBtn.onclick = () => {
            modal.style.display = 'none';
        };
    }

    /**
     * Cleanup: close WebSocket and SSH connection
     */
    cleanup() {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            // Send SSH close message
            if (this.isSSHConnected) {
                const sshCloseMessage = {
                    type: 'sshClose',
                    data: {
                        ssh_hash: this.sshHash
                    }
                };
                this.websocket.send(JSON.stringify(sshCloseMessage));
            }
            // Close WebSocket
            this.websocket.close();
        }
    }
}

// Export for unit tests (Node/Jest). No-op in the browser where `module` is undefined.
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { TerminalPageUtilities, TerminalPageHandler };
}

// Initialize terminal page handler when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('Terminal page DOM is ready');
    const terminalPageHandler = new TerminalPageHandler();
    terminalPageHandler.init();
    
    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
        terminalPageHandler.cleanup();
    });
});
