// Terminals page JavaScript
console.log('Terminals page loaded successfully!');

// Dummy JSON data for terminals
const dummyTerminalsData = {
    "terminals": [
        {
            "id": "term-001",
            "name": "ubuntu-dev",
            "ipAddress": "192.168.1.100",
            "port": "8080",
            "status": "running"
        },
        {
            "id": "term-002", 
            "name": "node-app",
            "ipAddress": "192.168.1.101",
            "port": "3000",
            "status": "stopped"
        },
        {
            "id": "term-003",
            "name": "python-script", 
            "ipAddress": "192.168.1.102",
            "port": "5000",
            "status": "pending"
        },
        {
            "id": "term-004",
            "name": "docker-container",
            "ipAddress": "192.168.1.103", 
            "port": "80",
            "status": "active"
        },
        {
            "id": "term-005",
            "name": "react-frontend",
            "ipAddress": "192.168.1.104",
            "port": "3001", 
            "status": "running"
        }
    ]
};

// Function to simulate API call
async function fetchTerminals() {
    console.log('Fetching terminals...');
    
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Return dummy data (in real app, this would be a fetch() call)
    return dummyTerminalsData;
}

// Function to render terminal item
function renderTerminalItem(terminal) {
    const statusClass = terminal.status.toLowerCase();
    const statusText = terminal.status.charAt(0).toUpperCase() + terminal.status.slice(1);
    
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

// Function to render terminals list
function renderTerminalsList(terminals) {
    const terminalsList = document.getElementById('terminalsList');
    
    if (terminals.length === 0) {
        terminalsList.innerHTML = '<div class="loading-message">No terminals found.</div>';
        return;
    }
    
    const terminalsHTML = terminals.map(terminal => renderTerminalItem(terminal)).join('');
    terminalsList.innerHTML = terminalsHTML;
    
    // Re-attach event listeners to new buttons
    attachEventListeners();
}

// Function to attach event listeners
function attachEventListeners() {
    // Play buttons
    const playBtns = document.querySelectorAll('.play-btn');
    playBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const terminalId = this.getAttribute('data-terminal-id');
            console.log('Play button clicked for terminal:', terminalId);
            // Add play logic here
        });
    });
    
    // Delete buttons
    const deleteBtns = document.querySelectorAll('.delete-btn');
    deleteBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const terminalId = this.getAttribute('data-terminal-id');
            console.log('Delete button clicked for terminal:', terminalId);
            // Add delete logic here
        });
    });
}

// Function to load terminals
async function loadTerminals() {
    try {
        const data = await fetchTerminals();
        console.log('Terminals loaded:', data.terminals);
        renderTerminalsList(data.terminals);
    } catch (error) {
        console.error('Error loading terminals:', error);
        const terminalsList = document.getElementById('terminalsList');
        terminalsList.innerHTML = '<div class="loading-message">Error loading terminals. Please try again.</div>';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('Terminals page DOM is ready');
    
    // Load terminals from API
    loadTerminals();
    
    // Add click handler for new terminal button
    const newBtn = document.querySelector('.new-terminal-btn');
    if (newBtn) {
        newBtn.addEventListener('click', function() {
            console.log('New terminal button clicked!');
            // Add new terminal logic here
        });
    }
});
