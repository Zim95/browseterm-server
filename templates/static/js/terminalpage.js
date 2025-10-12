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

// Initialize Xterm.js terminal
function initializeTerminal() {
    console.log('Initializing terminal...');
    
    // Create terminal instance
    term = new Terminal({
        cursorBlink: true,
        fontSize: 14,
        fontFamily: 'Menlo, Monaco, "Courier New", monospace',
        theme: {
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
        },
        rows: 30,
        cols: 100
    });
    
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

