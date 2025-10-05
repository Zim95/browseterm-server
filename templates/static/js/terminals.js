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

// Dummy operating systems data
const dummyOperatingSystemsData = {
    "operatingSystems": [
        {
            "id": "ubuntu",
            "name": "Ubuntu"
        }
    ]
};

// Dummy user data (same as profile page)
const dummyUserData = {
    "user": {
        "name": "Namah Shrestha",
        "email": "test@gmail.com"
    }
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
    // New terminal button
    const newTerminalBtn = document.querySelector('.new-terminal-btn');
    if (newTerminalBtn) {
        newTerminalBtn.addEventListener('click', openModal);
    }

    // Modal close buttons
    const modalClose = document.getElementById('modalClose');
    const cancelBtn = document.getElementById('cancelBtn');
    const modalOverlay = document.getElementById('modalOverlay');
    
    if (modalClose) {
        modalClose.addEventListener('click', closeModal);
    }
    
    if (cancelBtn) {
        cancelBtn.addEventListener('click', closeModal);
    }
    
    if (modalOverlay) {
        modalOverlay.addEventListener('click', function(e) {
            if (e.target === modalOverlay) {
                closeModal();
            }
        });
    }

    // Form submission
    const terminalForm = document.getElementById('terminalForm');
    if (terminalForm) {
        terminalForm.addEventListener('submit', handleFormSubmit);
    }

    // CPU/Memory increment/decrement buttons
    setupNumberInputs();

    // Play and delete buttons for existing terminals
    const playBtns = document.querySelectorAll('.play-btn');
    const deleteBtns = document.querySelectorAll('.delete-btn');
    
    playBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const terminalId = this.getAttribute('data-terminal-id');
            console.log('Play button clicked for terminal:', terminalId);
            // Add play functionality here
        });
    });
    
    deleteBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const terminalId = this.getAttribute('data-terminal-id');
            console.log('Delete button clicked for terminal:', terminalId);
            // Add delete functionality here
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
    
    // Attach event listeners
    attachEventListeners();
    
    // Load operating systems for modal
    loadOperatingSystems();
});

// Modal Functions
function openModal() {
    const modalOverlay = document.getElementById('modalOverlay');
    modalOverlay.classList.add('active');
    document.body.style.overflow = 'hidden';
    
    // Reset form
    resetForm();
}

function closeModal() {
    const modalOverlay = document.getElementById('modalOverlay');
    modalOverlay.classList.remove('active');
    document.body.style.overflow = '';
}

function resetForm() {
    const form = document.getElementById('terminalForm');
    form.reset();
    
    // Reset CPU and Memory to 1
    document.getElementById('cpu').value = 1;
    document.getElementById('memory').value = 1;
}

// Operating Systems Functions
async function loadOperatingSystems() {
    try {
        const data = await fetchOperatingSystems();
        console.log('Operating systems loaded:', data.operatingSystems);
        populateOperatingSystems(data.operatingSystems);
    } catch (error) {
        console.error('Error loading operating systems:', error);
        const select = document.getElementById('operatingSystem');
        select.innerHTML = '<option value="">Error loading OS</option>';
    }
}

function populateOperatingSystems(operatingSystems) {
    const select = document.getElementById('operatingSystem');
    select.innerHTML = '';
    
    if (operatingSystems.length === 0) {
        select.innerHTML = '<option value="">No operating systems available</option>';
        return;
    }
    
    operatingSystems.forEach(os => {
        const option = document.createElement('option');
        option.value = os.id;
        option.textContent = os.name;
        select.appendChild(option);
    });
}

// Number Input Functions
function setupNumberInputs() {
    // CPU controls
    const cpuDecrease = document.getElementById('cpuDecrease');
    const cpuIncrease = document.getElementById('cpuIncrease');
    const cpuInput = document.getElementById('cpu');
    
    if (cpuDecrease && cpuIncrease && cpuInput) {
        cpuDecrease.addEventListener('click', () => adjustNumber(cpuInput, -1));
        cpuIncrease.addEventListener('click', () => adjustNumber(cpuInput, 1));
    }
    
    // Memory controls
    const memoryDecrease = document.getElementById('memoryDecrease');
    const memoryIncrease = document.getElementById('memoryIncrease');
    const memoryInput = document.getElementById('memory');
    
    if (memoryDecrease && memoryIncrease && memoryInput) {
        memoryDecrease.addEventListener('click', () => adjustNumber(memoryInput, -1));
        memoryIncrease.addEventListener('click', () => adjustNumber(memoryInput, 1));
    }
}

function adjustNumber(input, change) {
    const currentValue = parseInt(input.value) || 1;
    const newValue = currentValue + change;
    
    // Enforce min/max limits
    if (newValue >= 1 && newValue <= 30) {
        input.value = newValue;
    }
}

// Form Submission
async function handleFormSubmit(e) {
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
        const userData = await fetchUser();
        
        // Combine all data
        const submissionData = {
            terminal: terminalData,
            user: userData.user,
            timestamp: new Date().toISOString()
        };
        
        // Console log the data as requested
        console.log('Terminal Creation Data:', submissionData);
        
        // Show success message
        alert('Terminal creation data logged to console!');
        
        // Close modal
        closeModal();
        
    } catch (error) {
        console.error('Error submitting form:', error);
        alert('Error submitting form. Please try again.');
    }
}
