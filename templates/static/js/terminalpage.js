/**
 * TerminalPageUtilities
 * Utility methods for terminal page functionality
 */
class TerminalPageUtilities {
    /**
     * Get terminal info from window object (passed from backend)
     * @returns {Object} Terminal info
     */
    static getTerminalInfoFromTemplate() {
        return window.terminalInfo || {};
    }

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

    /**
     * Migration Part 3 - every state-changing /app/* call needs the double-submit CSRF header.
     */
    static getCookie(name) {
        const match = document.cookie.match('(?:^|; )' + name + '=([^;]*)');
        return match ? decodeURIComponent(match[1]) : null;
    }

    static csrfHeaders(extra = {}) {
        return { 'X-CSRF-Token': TerminalPageUtilities.getCookie('csrf_token') || '', ...extra };
    }
}

/**
 * TerminalPageHandler
 * Handles terminal page functionality and xterm.js integration
 */
class TerminalPageHandler {
    constructor() {
        console.log('TerminalPageHandler initialized');
        this.elements = {};
        this.terminalId = null;
        this.terminalInfo = null;
        this.term = null;
        this.fitAddon = null;
        this.websocket = null;
        this.sshHash = '';
        this.isConnected = false;
        this.isSSHConnected = false;
        // remotetunelling.md Phase 6/7: one of 'idle' | 'connecting' | 'authenticating' |
        // 'connected' | 'reconnecting' | 'device-offline' | 'session-expired' |
        // 'authorization-failed' | 'error'. Every terminal-session/ticket/WS step below funnels
        // through setConnectionState() so this always reflects reality.
        this.connectionState = 'idle';
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.cleanedUp = false;
    }

    async init() {
        console.log('Terminal page loaded successfully!');

        // Migration Part 3: the terminal ID comes from the page's own server-rendered
        // terminalInfo (route is /terminal/{container_id}, a path param resolved server-side by
        // page_handlers.py), not a ?id= query string parsed client-side any more.
        this.terminalInfo = TerminalPageUtilities.getTerminalInfoFromTemplate();
        this.terminalId = this.terminalInfo.id || null;

        console.log('Terminal ID:', this.terminalId);
        console.log('Terminal info:', this.terminalInfo);

        this.cacheElements();
        this.initializeDarkMode();

        if (this.terminalInfo.error) {
            this.showError(this.terminalInfo.error);
            return;
        }

        if (this.terminalInfo.status !== 'Running') {
            this.showError(`Terminal is not running. Current status: ${this.terminalInfo.status}`);
            return;
        }

        this.sshHash = `ssh_${this.terminalId}_${Date.now()}`;

        this.initializeTerminal();
        this.loadTerminalInfo();
        this.setupEventListeners();
        this.connectToTerminal();

        window.addEventListener('resize', () => this.handleResize());
    }

    cacheElements() {
        this.elements = {
            terminal: document.getElementById('terminal'),
            terminalName: document.getElementById('terminalName'),
            terminalIp: document.getElementById('terminalIp'),
            terminalPort: document.getElementById('terminalPort'),
            saveStatusInfo: document.getElementById('saveStatusInfo'),
            saveStatusLastSaved: document.getElementById('saveStatusLastSaved'),
            saveStatusLastAttempt: document.getElementById('saveStatusLastAttempt'),
            saveStatusBadge: document.getElementById('saveStatusBadge'),
            saveActionBtn: document.getElementById('saveActionBtn')
        };
    }

    initializeDarkMode() {
        const savedTheme = localStorage.getItem('theme');
        if (!savedTheme) {
            localStorage.setItem('theme', 'light');
        }
        if (savedTheme === 'dark') {
            document.body.classList.add('dark-mode');
        }
        document.documentElement.classList.remove('dark-mode-loading');
    }

    initializeTerminal() {
        console.log('Initializing terminal...');
        const terminalTheme = TerminalPageUtilities.getXtermTheme();

        this.term = new Terminal({
            cursorBlink: true,
            fontSize: 14,
            fontFamily: 'Menlo, Monaco, "Courier New", monospace',
            theme: terminalTheme,
            scrollback: 10000,
            convertEol: true
        });

        window.xtermTheme = {
            applyTheme: (isDark) => {
                console.log('UI theme updated:', isDark ? 'dark' : 'light', '(terminal stays dark)');
            }
        };

        this.fitAddon = new FitAddon.FitAddon();
        this.term.loadAddon(this.fitAddon);
        this.term.open(this.elements.terminal);
        this.fitAddon.fit();
        this.writeWelcomeMessage();

        this.term.onWriteParsed(() => {
            setTimeout(() => {
                this.fitAddon.fit();
                this.term.scrollToBottom();
            }, 0);
        });

        this.term.onData(data => this.handleTerminalInput(data));

        console.log('Terminal initialized successfully!');
    }

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

    loadTerminalInfo() {
        console.log('Loading terminal info...');
        if (this.terminalInfo.name) {
            this.elements.terminalName.textContent = this.terminalInfo.name;
        }
        if (this.terminalInfo.ipAddress) {
            this.elements.terminalIp.textContent = this.terminalInfo.ipAddress;
        }
        if (this.terminalInfo.port) {
            this.elements.terminalPort.textContent = this.terminalInfo.port;
        }
        // Reflects real save_status/last_saved_at/last_save_attempted_at DB state via SSE,
        // whether it's from this page's own Save button or a Hibernate-triggered save.
        this.renderSaveStatusInfo({
            saveStatus: this.terminalInfo.saveStatus,
            lastSavedAt: this.terminalInfo.lastSavedAt,
            lastSaveAttemptedAt: this.terminalInfo.lastSaveAttemptedAt,
        });
    }

    setupEventListeners() {
        this.setupSaveStatusStream();
        if (this.elements.saveActionBtn) {
            this.elements.saveActionBtn.addEventListener('click', () => this.handleSave());
        }
    }

    /**
     * POST /app/containers/{id}/save - core reliability feature: snapshots this terminal without
     * stopping it (unlike Hibernate, which saves then stops). Sends a durable command to the
     * device agent the same way every other lifecycle action does. Lives here on the terminal
     * page itself, not on the terminals list card - this is the session you're actually using.
     */
    async handleSave() {
        const btn = this.elements.saveActionBtn;
        if (!btn || btn.disabled) return;

        btn.disabled = true;
        const label = btn.querySelector('span');
        const originalLabel = label ? label.textContent : null;
        if (label) label.textContent = 'Saving...';

        try {
            const resp = await fetch(`/app/containers/${this.terminalId}/save`, {
                method: 'POST',
                headers: TerminalPageUtilities.csrfHeaders(),
            });
            const result = await resp.json().catch(() => ({}));
            if (!resp.ok) {
                throw new Error(result.error || `HTTP ${resp.status}`);
            }
            TerminalPageUtilities.showNotification('success', 'Saving', 'A snapshot of this terminal is being saved.', 4000);
        } catch (e) {
            TerminalPageUtilities.showNotification('error', 'Save Failed', e.message, 6000);
        } finally {
            btn.disabled = false;
            if (label && originalLabel) label.textContent = originalLabel;
        }
    }

    handleResize() {
        if (this.fitAddon) {
            this.fitAddon.fit();
            this.term.scrollToBottom();
        }
    }

    handleTerminalInput(data) {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN && this.isSSHConnected) {
            const sshSendMessage = {
                type: 'sshSendData',
                data: { ssh_hash: this.sshHash, ssh_command: data }
            };
            this.websocket.send(JSON.stringify(sshSendMessage));
            this.markActivity();
        } else {
            console.warn('WebSocket not connected or SSH not established');
        }
    }

    /**
     * Render the "last saved / last attempt / status" widget. Pure reflection of DB state - no
     * action of its own beyond formatting and a badge color. Hidden entirely if this terminal has
     * no save history at all.
     */
    renderSaveStatusInfo({ saveStatus, lastSavedAt, lastSaveAttemptedAt }) {
        const box = this.elements.saveStatusInfo;
        if (!box) return;

        if (!saveStatus || saveStatus === 'None') {
            box.hidden = true;
            return;
        }
        box.hidden = false;

        const formatDate = (iso) => {
            if (!iso) return '—';
            const d = new Date(iso);
            return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString();
        };

        if (this.elements.saveStatusLastSaved) {
            this.elements.saveStatusLastSaved.textContent = formatDate(lastSavedAt);
        }
        if (this.elements.saveStatusLastAttempt) {
            this.elements.saveStatusLastAttempt.textContent = formatDate(lastSaveAttemptedAt);
        }
        if (this.elements.saveStatusBadge) {
            this.elements.saveStatusBadge.textContent = saveStatus;
            this.elements.saveStatusBadge.className = `save-status-badge ${saveStatus.toLowerCase()}`;
        }
    }

    /**
     * Subscribe to server-sent save-status events for this container. Same-origin now (migration
     * Part 3) - connects directly to /events/stream on this host via the sseToken minted
     * server-side at page render.
     */
    setupSaveStatusStream() {
        if (!window.sseToken) return;
        const containerId = String(this.terminalInfo.id);

        const es = new EventSource(`/events/stream?token=${window.sseToken}`);
        es.onmessage = (event) => {
            let data;
            try { data = JSON.parse(event.data); } catch (e) { return; }
            if (data.type !== 'save_status_change') return;
            if (String(data.container_id) !== containerId) return;

            this.renderSaveStatusInfo({
                saveStatus: data.save_status,
                lastSavedAt: data.last_saved_at,
                lastSaveAttemptedAt: data.last_save_attempted_at,
            });

            if (data.save_status === 'Succeeded') {
                TerminalPageUtilities.showNotification('success', 'Saved', `Snapshot saved${data.saved_image ? ': ' + data.saved_image : ''}.`, 6000);
            } else if (data.save_status === 'Failed') {
                TerminalPageUtilities.showNotification('error', 'Save failed', data.save_error || 'Snapshot failed.', 8000);
            }
        };
        es.onerror = () => { /* EventSource auto-reconnects */ };
        this._saveEventSource = es;
    }

    setConnectionState(state, detail) {
        this.connectionState = state;
        const messages = {
            connecting: '\x1b[1;36mRequesting a terminal session...\x1b[0m',
            authenticating: '\x1b[1;36m✓ Connected - authenticating...\x1b[0m',
            connected: '\x1b[1;32m✓ Server ready\x1b[0m',
            reconnecting: `\x1b[1;33mConnection lost - reconnecting (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})...\x1b[0m`,
            'device-offline': '\x1b[1;31m✗ Your machine appears to be offline. Make sure BrowseTerm is running on it, then reload this page.\x1b[0m',
            'session-expired': '\x1b[1;33mTerminal session expired - requesting a new one...\x1b[0m',
            'authorization-failed': '\x1b[1;31m✗ You are not authorized to access this terminal.\x1b[0m',
            error: '\x1b[1;31m✗ Could not connect to the terminal. Please reload the page.\x1b[0m',
        };
        const message = messages[state];
        if (message) {
            this.term.writeln(detail ? `${message} (${detail})` : message);
        }
    }

    /**
     * Connect to terminal. Migration Part 3: /app/terminal-session (session-cookie + CSRF
     * authenticated, replacing Local's pass-through to Cloud's internal-token route) mints a
     * fresh single-use ticket + this device's current tunnel URL right before every (re)connect
     * attempt - a consumed or expired ticket can never be reused.
     */
    async connectToTerminal() {
        console.log('Connecting to terminal:', this.terminalInfo);
        this.setConnectionState('connecting');

        let session;
        try {
            const resp = await fetch('/app/terminal-session', {
                method: 'POST',
                headers: TerminalPageUtilities.csrfHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({ container_id: this.terminalInfo.id })
            });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                if (resp.status === 404) {
                    this.setConnectionState('authorization-failed');
                } else if (resp.status === 409) {
                    this.setConnectionState('device-offline', err.error);
                } else {
                    this.setConnectionState('error', err.error);
                }
                return;
            }
            session = await resp.json();
        } catch (error) {
            console.error('Error requesting terminal session:', error);
            this.setConnectionState('error', error.message);
            return;
        }

        try {
            this.websocket = new WebSocket(session.websocket_url);

            this.websocket.onopen = () => {
                console.log('WebSocket connected to socket-ssh server');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.setConnectionState('authenticating');
                this.websocket.send(JSON.stringify({ type: 'authenticate', data: { ticket: session.ticket } }));
                this.markActivity();
                this.startActivityHeartbeat();
            };

            this.websocket.onmessage = (event) => {
                this.markActivity();
                this.handleWebSocketMessage(event);
            };

            this.websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
            };

            this.websocket.onclose = (event) => {
                console.log('WebSocket disconnected', event.code, event.reason);
                this.isConnected = false;
                this.isSSHConnected = false;
                this.stopActivityHeartbeat();
                if (this.cleanedUp) return;

                if (event.code === 4401) {
                    this.setConnectionState('session-expired');
                    this.connectToTerminal();
                    return;
                }

                this.attemptReconnect();
            };
        } catch (error) {
            console.error('Error creating WebSocket:', error);
            this.setConnectionState('error', error.message);
        }
    }

    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            this.setConnectionState('error', 'gave up after several reconnect attempts');
            return;
        }
        this.reconnectAttempts += 1;
        this.setConnectionState('reconnecting');
        const delayMs = Math.min(1000 * 2 ** (this.reconnectAttempts - 1), 15000);
        setTimeout(() => {
            if (!this.cleanedUp) this.connectToTerminal();
        }, delayMs);
    }

    markActivity() {
        this._lastActivityAt = Date.now();
    }

    /**
     * Throttled heartbeat: POST /app/containers/{id}/activity while there has been recent
     * terminal activity. Refreshes the login session TTL (any valid session check does that -
     * see src/cloud/session_auth.py:get_session_data) and stamps last_active_at, the idle signal
     * the reaper reads.
     */
    startActivityHeartbeat() {
        if (this._activityHeartbeat) return;
        this._lastFlushAt = 0;
        const INTERVAL_MS = 90 * 1000;
        const flush = () => {
            if (!this._lastActivityAt || this._lastActivityAt <= this._lastFlushAt) return;
            this._lastFlushAt = this._lastActivityAt;
            fetch(`/app/containers/${this.terminalInfo.id}/activity`, {
                method: 'POST',
                headers: TerminalPageUtilities.csrfHeaders(),
            }).catch(() => { /* best-effort; the next tick retries */ });
        };
        flush();
        this._activityHeartbeat = setInterval(flush, INTERVAL_MS);
    }

    stopActivityHeartbeat() {
        if (this._activityHeartbeat) {
            clearInterval(this._activityHeartbeat);
            this._activityHeartbeat = null;
        }
    }

    initiateSSHConnection() {
        console.log('Initiating SSH connection...');
        const sshConnectMessage = { type: 'sshConnect', data: { ssh_hash: this.sshHash } };
        this.websocket.send(JSON.stringify(sshConnectMessage));
        this.term.writeln('\x1b[1;36m✓ Initiating SSH connection...\x1b[0m');
    }

    handleWebSocketMessage(event) {
        try {
            const data = JSON.parse(event.data);
            console.log('WebSocket message received:', data);

            if (data.type === 'ready') {
                console.log('Server ready - initiating SSH connection');
                this.setConnectionState('connected');
                this.initiateSSHConnection();
                return;
            }

            if (data.error) {
                console.error('Server error:', data.error);
                this.term.writeln(`\r\n\x1b[1;31mError: ${data.error}\x1b[0m\r\n`);
                return;
            }

            if (data.message && !this.isSSHConnected) {
                this.isSSHConnected = true;
                this.term.writeln('\x1b[1;32m✓ SSH connection established!\x1b[0m\r\n');
                if (this.terminalInfo.sshPassword) {
                    this.showPasswordModal();
                }
            }

            if (data.message) {
                this.term.write(data.message);
            }
        } catch (error) {
            console.log('Raw message:', event.data);
            this.term.write(event.data);
        }
    }

    writeColoredText(text, color) {
        const colorCode = TerminalPageUtilities.getColorCode(color);
        const resetCode = TerminalPageUtilities.getColorCode('reset');
        this.term.writeln(colorCode + text + resetCode);
    }

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

    showPasswordModal() {
        const modal = document.getElementById('passwordModal');
        const modalContent = document.getElementById('passwordModalContent');
        const passwordText = document.getElementById('passwordText');
        const closeBtn = document.getElementById('closePasswordModal');

        const isDark = document.body.classList.contains('dark-mode');
        modalContent.style.background = isDark ? '#252526' : '#ffffff';
        modalContent.style.color = isDark ? '#d4d4d4' : '#333333';

        passwordText.value = this.terminalInfo.sshPassword;
        modal.style.display = 'flex';

        passwordText.onclick = () => {
            passwordText.select();
        };

        closeBtn.onclick = () => {
            modal.style.display = 'none';
        };
    }

    cleanup() {
        this.cleanedUp = true;
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            if (this.isSSHConnected) {
                const sshCloseMessage = { type: 'sshClose', data: { ssh_hash: this.sshHash } };
                this.websocket.send(JSON.stringify(sshCloseMessage));
            }
            this.websocket.close();
        }
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { TerminalPageUtilities, TerminalPageHandler };
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('Terminal page DOM is ready');
    const terminalPageHandler = new TerminalPageHandler();
    terminalPageHandler.init();

    window.addEventListener('beforeunload', () => {
        terminalPageHandler.cleanup();
    });
});
