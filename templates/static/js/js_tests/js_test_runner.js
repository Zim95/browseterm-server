/**
 * Custom Test Runner UI
 * Manages test execution, progress bars, and log display
 */

class TestRunner {
    constructor() {
        this.testFiles = [
            { name: 'test_base_class.js', displayName: 'Base Class Tests', suite: 'Base Class' },
            { name: 'test_oauth_callback.js', displayName: 'OAuth Callback Tests', suite: 'OAuth Callback' },
            { name: 'test_login.js', displayName: 'Login Tests', suite: 'Login' },
            { name: 'test_profile.js', displayName: 'Profile Tests', suite: 'Profile' },
            { name: 'test_home.js', displayName: 'Home Tests', suite: 'Home' }
        ];
        this.testResults = {};
        this.totalStats = {
            total: 0,
            passed: 0,
            failed: 0,
            duration: 0
        };
    }

    /**
     * Initialize the test runner
     */
    init() {
        this.buildUI();
        this.setupEventListeners();
        // Auto-run tests on load
        setTimeout(() => this.runAllTests(), 500);
    }

    /**
     * Build the test UI cards
     */
    buildUI() {
        const container = document.getElementById('testFilesContainer');
        this.testFiles.forEach(testFile => {
            const card = this.createTestCard(testFile);
            container.appendChild(card);
        });
    }

    /**
     * Create a test card for a test file
     */
    createTestCard(testFile) {
        const card = document.createElement('div');
        card.className = 'test-file-card';
        card.id = `card-${testFile.name}`;
        card.innerHTML = `
            <div class="test-file-header">
                <div class="test-file-name">
                    📄 ${testFile.displayName}
                </div>
                <div class="test-file-status" id="status-${testFile.name}">Pending</div>
            </div>
            <div class="test-count" id="count-${testFile.name}">
                <span class="passed">0</span> / <span class="total">0</span> tests
            </div>
            <div class="progress-bar-container">
                <div class="progress-bar" id="progress-${testFile.name}"></div>
            </div>
            <button class="toggle-logs-btn" id="toggle-${testFile.name}">
                <span>▶ Show Logs</span>
                <span class="toggle-icon">▼</span>
            </button>
            <div class="logs-container" id="logs-${testFile.name}">
                <!-- Logs will be inserted here -->
            </div>
        `;
        return card;
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Run all button
        document.getElementById('runAllBtn').addEventListener('click', () => {
            this.runAllTests();
        });

        // Toggle logs buttons
        this.testFiles.forEach(testFile => {
            const toggleBtn = document.getElementById(`toggle-${testFile.name}`);
            const logsContainer = document.getElementById(`logs-${testFile.name}`);
            const toggleIcon = toggleBtn.querySelector('.toggle-icon');
            toggleBtn.addEventListener('click', () => {
                logsContainer.classList.toggle('expanded');
                toggleIcon.classList.toggle('expanded');
                if (logsContainer.classList.contains('expanded')) {
                    toggleBtn.querySelector('span').textContent = '▼ Hide Logs';
                } else {
                    toggleBtn.querySelector('span').textContent = '▶ Show Logs';
                }
            });
        });
    }

    /**
     * Run all tests
     */
    async runAllTests() {
        // Reset stats
        this.totalStats = { total: 0, passed: 0, failed: 0, duration: 0 };
        // Reset UI
        this.testFiles.forEach(testFile => {
            this.updateStatus(testFile.name, 'Pending');
            this.updateProgress(testFile.name, 0, false);
            this.clearLogs(testFile.name);
        });
        const startTime = Date.now();
        // Run Mocha tests
        const runner = mocha.run();
        // Track current suite
        let currentSuite = null;
        let suiteTests = {};
        // Initialize suite tracking
        this.testFiles.forEach(tf => {
            suiteTests[tf.suite] = { passed: 0, failed: 0, total: 0, logs: [] };
        });

        runner.on('suite', (suite) => {
            if (suite.title && suite.title !== '') {
                currentSuite = suite.title;
                const testFile = this.testFiles.find(tf => tf.suite === suite.title);
                if (testFile) {
                    this.updateStatus(testFile.name, 'Running');
                }
            }
        });

        runner.on('test', (test) => {
            // Test started
        });

        runner.on('pass', (test) => {
            if (currentSuite && suiteTests[currentSuite]) {
                suiteTests[currentSuite].passed++;
                suiteTests[currentSuite].total++;
                suiteTests[currentSuite].logs.push({
                    type: 'success',
                    title: test.title,
                    message: 'Passed ✓',
                    duration: test.duration
                });
                this.totalStats.passed++;
                this.totalStats.total++;
                this.updateTestFileUI(currentSuite, suiteTests[currentSuite]);
            }
        });

        runner.on('fail', (test, err) => {
            if (currentSuite && suiteTests[currentSuite]) {
                suiteTests[currentSuite].failed++;
                suiteTests[currentSuite].total++;
                suiteTests[currentSuite].logs.push({
                    type: 'failure',
                    title: test.title,
                    message: err.message,
                    stack: err.stack,
                    duration: test.duration
                });
                this.totalStats.failed++;
                this.totalStats.total++;
                this.updateTestFileUI(currentSuite, suiteTests[currentSuite]);
            }
        });

        runner.on('end', () => {
            const endTime = Date.now();
            this.totalStats.duration = endTime - startTime;
            // Update final status
            this.testFiles.forEach(testFile => {
                const suite = suiteTests[testFile.suite];
                if (suite.total > 0) {
                    const hasFailed = suite.failed > 0;
                    this.updateStatus(testFile.name, hasFailed ? 'Failed' : 'Passed');
                    this.updateProgress(testFile.name, 100, hasFailed);
                }
            });
            this.updateSummary();
        });
    }

    /**
     * Update test file UI (count, progress, logs)
     */
    updateTestFileUI(suiteName, suiteData) {
        const testFile = this.testFiles.find(tf => tf.suite === suiteName);
        if (!testFile) return;
        // Update count
        const countEl = document.getElementById(`count-${testFile.name}`);
        countEl.innerHTML = `
            <span class="passed">${suiteData.passed}</span> / 
            <span class="total">${suiteData.total}</span> tests
            ${suiteData.failed > 0 ? `<span class="failed">(${suiteData.failed} failed)</span>` : ''}
        `;
        // Update progress
        const progress = (suiteData.passed + suiteData.failed) / suiteData.total * 100;
        this.updateProgress(testFile.name, progress, suiteData.failed > 0);
        // Update logs
        this.updateLogs(testFile.name, suiteData.logs);
    }

    /**
     * Update status badge
     */
    updateStatus(fileName, status) {
        const statusEl = document.getElementById(`status-${fileName}`);
        statusEl.textContent = status;
        statusEl.className = 'test-file-status';
        if (status === 'Running') {
            statusEl.classList.add('running');
        } else if (status === 'Passed') {
            statusEl.classList.add('passed');
        } else if (status === 'Failed') {
            statusEl.classList.add('failed');
        }
    }

    /**
     * Update progress bar
     */
    updateProgress(fileName, percentage, hasFailed) {
        const progressEl = document.getElementById(`progress-${fileName}`);
        progressEl.style.width = `${percentage}%`;
        if (hasFailed) {
            progressEl.classList.add('failed');
        } else {
            progressEl.classList.remove('failed');
        }
    }

    /**
     * Update logs
     */
    updateLogs(fileName, logs) {
        const logsEl = document.getElementById(`logs-${fileName}`);
        logsEl.innerHTML = '';
        logs.forEach(log => {
            const logEntry = document.createElement('div');
            logEntry.className = `log-entry ${log.type}`;
            logEntry.innerHTML = `
                <div class="log-title">${log.title}</div>
                <div class="log-message">${log.message}</div>
                ${log.duration ? `<div class="log-message" style="opacity: 0.6; font-size: 0.8em;">Duration: ${log.duration}ms</div>` : ''}
                ${log.stack ? `<div class="log-stack">${log.stack}</div>` : ''}
            `;
            logsEl.appendChild(logEntry);
        });
    }

    /**
     * Clear logs
     */
    clearLogs(fileName) {
        const logsEl = document.getElementById(`logs-${fileName}`);
        logsEl.innerHTML = '<div class="log-entry info"><div class="log-message">Waiting to run tests...</div></div>';
    }

    /**
     * Update summary statistics
     */
    updateSummary() {
        document.getElementById('totalTests').textContent = this.totalStats.total;
        document.getElementById('passedTests').textContent = this.totalStats.passed;
        document.getElementById('failedTests').textContent = this.totalStats.failed;
        document.getElementById('duration').textContent = `${this.totalStats.duration}ms`;
    }
}

// Initialize test runner when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const testRunner = new TestRunner();
    testRunner.init();
});

