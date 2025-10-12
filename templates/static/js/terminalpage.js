// Terminal Page JavaScript
console.log('Terminal page loaded successfully!');

// Get terminal info from URL parameters
const urlParams = new URLSearchParams(window.location.search);
const terminalId = urlParams.get('id');
console.log('Terminal ID:', terminalId);

// Get terminal info from backend (passed from template)
const terminalInfo = window.terminalInfo || {};

// Initialize Xterm.js
let term;
let fitAddon;

document.addEventListener('DOMContentLoaded', function() {
    console.log('Terminal page DOM is ready');
    
    // Initialize dark mode
    initializeDarkMode();
    
    // Initialize terminal
    initializeTerminal();
    
    // Load terminal info
    loadTerminalInfo();
    
    // Attach event listeners
    attachEventListeners();
    
    // Handle window resize
    window.addEventListener('resize', () => {
        if (fitAddon) {
            fitAddon.fit();
        }
    });
});

// Initialize dark mode on page load
function initializeDarkMode() {
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
    
    console.log('Terminal page dark mode initialized:', document.body.classList.contains('dark-mode') ? 'enabled' : 'disabled');
}

// Initialize Xterm.js terminal
function initializeTerminal() {
    console.log('Initializing terminal...');
    
    // Determine theme based on dark mode
    const isDarkMode = document.body.classList.contains('dark-mode');
    const terminalTheme = getXtermTheme(isDarkMode);
    
    // Create terminal instance
    term = new Terminal({
        cursorBlink: true,
        fontSize: 14,
        fontFamily: 'Menlo, Monaco, "Courier New", monospace',
        theme: terminalTheme,
        rows: 30,
        cols: 100
    });
    
    // Store xterm theme manager globally
    window.xtermTheme = {
        applyTheme: function(isDark) {
            if (term) {
                term.options.theme = getXtermTheme(isDark);
                console.log('Xterm theme updated:', isDark ? 'dark' : 'light');
            }
        }
    };
    
    // Create fit addon
    fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);
    
    // Open terminal in the container
    const terminalElement = document.getElementById('terminal');
    term.open(terminalElement);
    
    // Fit terminal to container
    fitAddon.fit();
    
    // Write welcome message
    term.writeln('\x1b[1;32m╔══════════════════════════════════════════╗\x1b[0m');
    term.writeln('\x1b[1;32m║                                          ║\x1b[0m');
    term.writeln('\x1b[1;32m║         Welcome to BrowseTerm!           ║\x1b[0m');
    term.writeln('\x1b[1;32m║                                          ║\x1b[0m');
    term.writeln('\x1b[1;32m╚══════════════════════════════════════════╝\x1b[0m');
    term.writeln('');
    term.writeln('\x1b[1;36mHi! Your terminal is initializing...\x1b[0m');
    term.writeln('');
    term.writeln('\x1b[33mTerminal ID: ' + terminalId + '\x1b[0m');
    term.writeln('');
    
    // Handle terminal input (for now, just echo)
    term.onData(data => {
        // For now, just write the data back (echo)
        // In production, this would send data to the backend via WebSocket
        console.log('Terminal input:', data);
    });
    
    console.log('Terminal initialized successfully!');
}

// Load terminal information
function loadTerminalInfo() {
    console.log('Loading terminal info...');
    console.log('Terminal info from backend:', terminalInfo);
    
    // Update UI with terminal info
    if (terminalInfo.name) {
        document.getElementById('terminalName').textContent = terminalInfo.name;
    }
    
    if (terminalInfo.ipAddress) {
        document.getElementById('terminalIp').textContent = terminalInfo.ipAddress;
    }
    
    if (terminalInfo.port) {
        document.getElementById('terminalPort').textContent = terminalInfo.port;
    }
    
    // TODO: In production, establish WebSocket connection here
    // connectToTerminal(terminalInfo);
}

// Attach event listeners
function attachEventListeners() {
    const saveBtn = document.getElementById('saveBtn');
    
    if (saveBtn) {
        saveBtn.addEventListener('click', handleSaveSession);
    }
}

// Handle save session button click
function handleSaveSession() {
    console.log('Save session button clicked');
    
    // TODO: Implement session saving logic
    // For now, just show an alert
    alert('Session save functionality will be implemented soon!\n\nThis will save your terminal history and state.');
}

// TODO: Function to connect to terminal via WebSocket
function connectToTerminal(terminalInfo) {
    console.log('Connecting to terminal:', terminalInfo);
    
    // This will establish WebSocket connection to the backend
    // which will then connect to the SSH container
    
    // Example structure:
    // const ws = new WebSocket('wss://your-backend/terminal');
    // ws.onmessage = (event) => {
    //     term.write(event.data);
    // };
    // term.onData(data => {
    //     ws.send(data);
    // });
}

// Get xterm theme based on dark mode
function getXtermTheme(isDark) {
    if (isDark) {
        // Dark theme
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
    } else {
        // Light theme
        return {
            background: '#ffffff',
            foreground: '#333333',
            cursor: '#333333',
            black: '#000000',
            red: '#cd3131',
            green: '#00BC00',
            yellow: '#949800',
            blue: '#0451a5',
            magenta: '#bc05bc',
            cyan: '#0598bc',
            white: '#555555',
            brightBlack: '#666666',
            brightRed: '#cd3131',
            brightGreen: '#23d18b',
            brightYellow: '#b5ba00',
            brightBlue: '#0451a5',
            brightMagenta: '#bc05bc',
            brightCyan: '#0598bc',
            brightWhite: '#a5a5a5'
        };
    }
}

// Helper function to write colored text to terminal
function writeColoredText(text, color) {
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
    
    term.writeln(colorCodes[color] + text + colorCodes.reset);
}

console.log('Terminal page JavaScript loaded!');

