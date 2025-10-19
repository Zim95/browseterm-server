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
    }

    /**
     * Initialize terminal page
     */
    async init() {
        console.log('Terminal page loaded successfully!');

        // Get terminal ID and info
        this.terminalId = TerminalPageUtilities.getTerminalIdFromURL();
        this.terminalInfo = TerminalPageUtilities.getTerminalInfoFromTemplate();
        
        console.log('Terminal ID:', this.terminalId);
        console.log('Terminal info:', this.terminalInfo);

        // Cache DOM elements
        this.cacheElements();

        // Initialize dark mode
        this.initializeDarkMode();

        // Initialize xterm.js terminal
        this.initializeTerminal();

        // Load terminal info into UI
        this.loadTerminalInfo();

        // Setup event listeners
        this.setupEventListeners();

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
            rows: 30,
            cols: 100
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
        this.term.writeln('\x1b[1;36mHi! Your terminal is initializing...\x1b[0m');
        this.term.writeln('');
        this.term.writeln('\x1b[33mTerminal ID: ' + this.terminalId + '\x1b[0m');
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

        // TODO: In production, establish WebSocket connection here
        // this.connectToTerminal();
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        if (this.elements.saveBtn) {
            this.elements.saveBtn.addEventListener('click', () => this.handleSaveSession());
        }
    }

    /**
     * Handle window resize
     */
    handleResize() {
        if (this.fitAddon) {
            this.fitAddon.fit();
        }
    }

    /**
     * Handle terminal input
     * @param {string} data - Input data from terminal
     */
    handleTerminalInput(data) {
        // For now, just log the data
        // In production, this would send data to the backend via WebSocket
        console.log('Terminal input:', data);

        // TODO: Send data via WebSocket
        // if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
        //     this.websocket.send(data);
        // }
    }

    /**
     * Handle save session button click
     */
    handleSaveSession() {
        console.log('Save session button clicked');
        
        TerminalPageUtilities.showNotification(
            'info',
            'Coming Soon',
            'Session save functionality will be implemented soon! This will save your terminal history and state.',
            6000
        );
    }

    /**
     * Connect to terminal via WebSocket (TODO)
     */
    connectToTerminal() {
        console.log('Connecting to terminal:', this.terminalInfo);

        // TODO: Implement WebSocket connection
        // This will establish WebSocket connection to the backend
        // which will then connect to the SSH container

        // Example structure:
        // this.websocket = new WebSocket('wss://your-backend/terminal');
        // 
        // this.websocket.onopen = () => {
        //     console.log('WebSocket connected');
        // };
        //
        // this.websocket.onmessage = (event) => {
        //     this.term.write(event.data);
        // };
        //
        // this.websocket.onerror = (error) => {
        //     console.error('WebSocket error:', error);
        // };
        //
        // this.websocket.onclose = () => {
        //     console.log('WebSocket disconnected');
        // };
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
}

// Initialize terminal page handler when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('Terminal page DOM is ready');
    const terminalPageHandler = new TerminalPageHandler();
    terminalPageHandler.init();
});
