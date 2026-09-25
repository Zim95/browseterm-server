/**
 * TerminalsUtilities
 * Utility methods for terminals page functionality
 */
class TerminalsUtilities {
    static getUserInfo() {
        return window.userInfo || {};
    }

    static getOperatingSystems() {
        return window.images || [];
    }

    static getActiveDevice() {
        return window.activeDevice || null;
    }

    /**
     * "Play disabled when device/tunnel offline." Mirrors (approximately - this is a UX hint
     * only) Cloud's own real enforcement in src/cloud/terminal_handlers.py::_tunnel_is_online: the
     * device must be Active, its tunnel Online, and its last heartbeat recent. A real Play attempt
     * is always re-validated server-side regardless of what this returns.
     * @returns {boolean}
     */
    static isActiveDeviceTunnelOnline() {
        const device = TerminalsUtilities.getActiveDevice();
        if (!device || device.status !== 'Active' || device.tunnel_status !== 'Online') return false;
        if (!device.tunnel_last_heartbeat_at) return false;
        const isoUtc = /[zZ]|[+-]\d{2}:?\d{2}$/.test(device.tunnel_last_heartbeat_at)
            ? device.tunnel_last_heartbeat_at
            : `${device.tunnel_last_heartbeat_at}Z`;
        const ageMs = Date.now() - new Date(isoUtc).getTime();
        return Number.isFinite(ageMs) && ageMs <= 90 * 1000;
    }

    static normalizeName(name) {
        if (!name || typeof name !== 'string') return '';
        const lowered = name.trim().toLowerCase();
        const underscored = lowered.replace(/\s+/g, '_');
        return underscored.replace(/[^a-z0-9_]/g, '');
    }

    static generatePassword(length = 8) {
        const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
        let pwd = '';
        for (let i = 0; i < length; i += 1) {
            const idx = Math.floor(Math.random() * chars.length);
            pwd += chars.charAt(idx);
        }
        return pwd;
    }

    static findImageByName(name) {
        const images = TerminalsUtilities.getOperatingSystems();
        if (!Array.isArray(images)) return null;
        const target = (name || '').toString().trim();
        return images.find((img) => (img.name || '').toString().trim() === target) || null;
    }

    static formatStatus(status) {
        return status.charAt(0).toUpperCase() + status.slice(1);
    }

    /**
     * Maps the backend's full ContainerStatus enum (Pending/Running/Succeeded/Failed/Unknown/
     * Hibernated/Resuming/Queued/Creating/Hibernating/Deleting/DeviceOffline/Stranded) onto the
     * five states this UI actually has real coloring/highlighting for: pending, running, failed,
     * hibernated, resuming. Transitional/in-flight statuses (Queued, Creating, Hibernating,
     * Deleting) read as "still working" to a user regardless of which specific step they're on,
     * so they collapse into `pending` (the existing loading/spinner treatment) rather than each
     * showing its own raw, unstyled label. Genuine problem states (Failed, DeviceOffline,
     * Stranded) collapse into `failed`. This is the single source of truth for both the status
     * badge's CSS class/text and which controls getControlsHTML shows - never branch on the raw
     * status directly elsewhere.
     */
    static mapStatusToDisplay(status) {
        const key = (status || 'pending').toLowerCase();
        const displayMap = {
            pending: 'pending', queued: 'pending', creating: 'pending', deleting: 'pending',
            hibernating: 'pending', unknown: 'pending',
            running: 'running', succeeded: 'running',
            failed: 'failed', deviceoffline: 'failed', stranded: 'failed',
            hibernated: 'hibernated',
            resuming: 'resuming',
        };
        return displayMap[key] || 'pending';
    }

    static adjustNumber(input, change) {
        const min = parseInt(input.min, 10) || 1;
        const max = parseInt(input.max, 10);
        const currentValue = parseInt(input.value, 10) || min;
        const newValue = currentValue + change;

        if (newValue >= min && (Number.isNaN(max) || newValue <= max)) {
            input.value = newValue;
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }
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
     * Migration Part 3 - every state-changing /app/* call needs the double-submit CSRF header
     * (src/cloud/session_auth.py:csrf_ok). Read from the non-HttpOnly csrf_token cookie set at
     * login (src/cloud/oauth_handlers.py:oauth_callback -> session_auth.set_session_cookies).
     */
    static getCookie(name) {
        const match = document.cookie.match('(?:^|; )' + name + '=([^;]*)');
        return match ? decodeURIComponent(match[1]) : null;
    }

    static csrfHeaders(extra = {}) {
        return { 'X-CSRF-Token': TerminalsUtilities.getCookie('csrf_token') || '', ...extra };
    }
}

/**
 * TerminalsHandler
 * Handles terminals page functionality
 */
class TerminalsHandler {
    constructor() {
        console.log('TerminalsHandler initialized');
        this.elements = {};
        this.terminals = [];
        this.operatingSystems = [];
        this.deviceQuota = null;
        // Container IDs whose creation is still pending confirmation - cleared up on Running/Failed.
        this.pendingContainers = new Set();
        this.hibernatingIds = new Set();
    }

    async init() {
        console.log('Terminals page loaded successfully!');
        this.cacheElements();
        this.loadDeviceQuota();
        this.configureResourceControls();
        await this.loadTerminals();
        await this.loadOperatingSystems();
        this.setupEventListeners();
        this.setupStatusStream();
        this.setupDeviceStatusPolling();
    }

    cacheElements() {
        this.elements = {
            terminalsList: document.getElementById('terminalsList'),
            newTerminalBtn: document.querySelector('.new-terminal-btn'),
            modalOverlay: document.getElementById('modalOverlay'),
            modalClose: document.getElementById('modalClose'),
            cancelBtn: document.getElementById('cancelBtn'),
            infoModalOverlay: document.getElementById('infoModalOverlay'),
            infoModalClose: document.getElementById('infoModalClose'),
            infoModalBody: document.getElementById('infoModalBody'),
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
            storageIncrease: document.getElementById('storageIncrease'),
            cpuQuota: document.getElementById('cpuQuota'),
            memoryQuota: document.getElementById('memoryQuota'),
            storageQuota: document.getElementById('storageQuota'),
            submitBtn: document.getElementById('submitBtn')
        };
    }

    loadDeviceQuota() {
        const device = TerminalsUtilities.getActiveDevice();
        if (!device) {
            this.deviceQuota = null;
            return;
        }
        const bytesToGb = (bytes) => Math.max(0, Math.floor(bytes / (1024 ** 3)));
        this.deviceQuota = {
            availableCpu: Math.max(0, device.available_cpu),
            availableMemoryGb: bytesToGb(device.available_memory_bytes),
            availableStorageGb: bytesToGb(device.available_storage_bytes),
        };
    }

    configureResourceControls() {
        const quota = this.deviceQuota || { availableCpu: 0, availableMemoryGb: 0, availableStorageGb: 0 };
        this.configureResourceControl('cpu', quota.availableCpu);
        this.configureResourceControl('memory', quota.availableMemoryGb);
        this.configureResourceControl('storage', quota.availableStorageGb);
        this.updateSubmitButtonState();
    }

    configureResourceControl(resource, available) {
        const decreaseBtn = this.elements[`${resource}Decrease`];
        const increaseBtn = this.elements[`${resource}Increase`];
        const input = this.elements[`${resource}Input`];
        const quotaDisplay = this.elements[`${resource}Quota`];
        const info = document.getElementById(`${resource}Info`);
        const min = parseInt(input.min, 10) || 1;
        const unit = resource === 'cpu' ? 'cores' : 'GiB';

        if (quotaDisplay) quotaDisplay.textContent = `/ ${available} ${unit}`;

        if (available >= min) {
            input.max = available;
            input.value = Math.min(parseInt(input.value, 10) || min, available);
            decreaseBtn.disabled = false;
            increaseBtn.disabled = false;
            input.disabled = false;
            if (info) info.style.display = 'none';
        } else {
            decreaseBtn.disabled = true;
            increaseBtn.disabled = true;
            input.disabled = true;
            if (info) {
                info.textContent = 'ℹ️ Not enough device quota remaining for this resource';
                info.style.display = 'block';
            }
        }
    }

    /**
     * Load terminals from Cloud's own session-authenticated API (migration Part 3 - no more
     * user_id query param, the session cookie IS the authorization).
     */
    async loadTerminals() {
        try {
            const response = await fetch('/app/containers');
            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'Failed to load terminals');
            }

            this.terminals = (result.containers || [])
                .map(container => ({
                    id: container.id,
                    name: container.name,
                    ipAddress: container.ip_address || 'Pending...',
                    port: container.port_mappings?.[0]?.publish_port || '-',
                    status: container.status || 'Pending',
                    createdAt: container.created_at,
                    deviceId: container.device_id || null,
                }))
                .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));

            this.renderTerminalsList();
        } catch (error) {
            console.error('Error loading terminals:', error);
            this.showError('Error loading terminals. Please try again.');
            TerminalsUtilities.showNotification('error', 'Loading Error', 'Failed to load terminals', 5000);
        }
    }

    renderTerminalsList() {
        if (this.terminals.length === 0) {
            this.elements.terminalsList.innerHTML = '<div class="loading-message">No terminals found.</div>';
            return;
        }

        const terminalsHTML = this.terminals.map(terminal => this.renderTerminalItem(terminal)).join('');
        this.elements.terminalsList.innerHTML = terminalsHTML;
        this.attachTerminalControls();
    }

    getControlsHTML(terminalId, status) {
        if (this.hibernatingIds.has(terminalId)) {
            return `
                <div class="terminal-loading">
                    <span class="loading-spinner"></span>
                    <span class="loading-text">Hibernating...</span>
                </div>`;
        }
        // Keyed by TerminalsUtilities.mapStatusToDisplay's output (the 5 states this UI shows),
        // not the raw backend status - callers must map before calling this.
        const controlsConfig = {
            running: { showPlay: true, showInfo: true, showHibernate: true, showDelete: true, showLoading: false },
            failed: { showPlay: false, showInfo: true, showDelete: true, showLoading: false },
            pending: { showPlay: false, showDelete: false, showLoading: true },
            hibernated: { showResume: true, showInfo: true, showDelete: true, showLoading: false },
            resuming: { showLoading: true },
        };

        const config = controlsConfig[status] || controlsConfig.pending;

        if (config.showLoading) {
            return `
                <div class="terminal-loading">
                    <span class="loading-spinner"></span>
                    <span class="loading-text">Working...</span>
                </div>`;
        }

        let html = '';
        if (config.showPlay) {
            const deviceOnline = TerminalsUtilities.isActiveDeviceTunnelOnline();
            html += deviceOnline
                ? `
                <button class="control-btn play-btn" data-terminal-id="${terminalId}">
                    <i class="fas fa-play"></i>
                </button>`
                : `
                <span class="play-btn-wrapper" title="Reconnecting to your machine - this usually resolves within a minute">
                    <button class="control-btn play-btn" data-terminal-id="${terminalId}" disabled>
                        <i class="fas fa-play"></i>
                    </button>
                </span>`;
        }
        if (config.showInfo) {
            html += `
                <button class="control-btn info-btn" data-terminal-id="${terminalId}" title="Terminal info">
                    <i class="fas fa-circle-info"></i>
                </button>`;
        }
        if (config.showHibernate) {
            html += `
                <button class="control-btn hibernate-btn" data-terminal-id="${terminalId}" title="Hibernate">
                    <i class="fas fa-moon"></i>
                </button>`;
        }
        if (config.showResume) {
            html += `
                <button class="control-btn resume-btn" data-terminal-id="${terminalId}" title="Resume from snapshot">
                    <i class="fas fa-power-off"></i>
                </button>`;
        }
        if (config.showDelete) {
            html += `
                <button class="control-btn delete-btn" data-terminal-id="${terminalId}">
                    <i class="fas fa-trash"></i>
                </button>`;
        }
        return html;
    }

    renderTerminalItem(terminal) {
        const statusLower = (terminal.status || 'Pending').toLowerCase();
        const statusText = terminal.status || 'Pending';
        // The badge's CSS class and which controls are shown are both driven by the mapped
        // display status (pending/running/failed/hibernated/resuming - the only states this UI
        // has real coloring/highlighting for), not the raw backend status - a raw value like
        // "Queued" or "Deleting" has no styling of its own and would render as an unstyled,
        // default-colored badge. The label text itself still shows the raw status verbatim
        // (accurate wording), and the icon map below still keys off it too (so e.g. a
        // "Hibernating" row still gets its own spin icon even though it shares the "pending"
        // bucket's coloring with other in-flight states).
        const displayStatus = TerminalsUtilities.mapStatusToDisplay(statusLower);
        const controlsHTML = this.getControlsHTML(terminal.id, displayStatus);

        const statusIconMap = {
            hibernated: '<i class="fas fa-moon"></i> ',
            hibernating: '<i class="fas fa-rotate spin-icon"></i> ',
            resuming: '<i class="fas fa-rotate spin-icon"></i> ',
        };
        const statusIcon = statusIconMap[statusLower] || '';

        return `
            <div class="terminal-item" data-terminal-id="${terminal.id}">
                <div class="terminal-info">
                    <div class="terminal-name">${terminal.name}</div>
                    <div class="terminal-ip">
                        <div class="ip-address">${terminal.ipAddress || 'Pending...'}</div>
                        <div class="port">${terminal.port || '-'}</div>
                    </div>
                    <div class="terminal-status ${displayStatus}">${statusIcon}${statusText}</div>
                </div>
                <div class="terminal-controls">
                    ${controlsHTML}
                </div>
            </div>
        `;
    }

    setupEventListeners() {
        if (this.elements.newTerminalBtn) {
            this.elements.newTerminalBtn.addEventListener('click', () => this.openModal());
        }
        if (this.elements.modalClose) {
            this.elements.modalClose.addEventListener('click', () => this.closeModal());
        }
        if (this.elements.cancelBtn) {
            this.elements.cancelBtn.addEventListener('click', () => this.closeModal());
        }
        if (this.elements.modalOverlay) {
            this.elements.modalOverlay.addEventListener('click', (e) => {
                if (e.target === this.elements.modalOverlay) this.closeModal();
            });
        }
        if (this.elements.infoModalClose) {
            this.elements.infoModalClose.addEventListener('click', () => this.closeInfoModal());
        }
        if (this.elements.infoModalOverlay) {
            this.elements.infoModalOverlay.addEventListener('click', (e) => {
                if (e.target === this.elements.infoModalOverlay) this.closeInfoModal();
            });
        }
        if (this.elements.terminalForm) {
            this.elements.terminalForm.addEventListener('submit', (e) => this.handleFormSubmit(e));
        }
        this.setupNumberInputs();
    }

    attachTerminalControls() {
        document.querySelectorAll('.play-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.handlePlay(e.target.closest('button').getAttribute('data-terminal-id')));
        });
        document.querySelectorAll('.info-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.handleInfo(e.target.closest('button').getAttribute('data-terminal-id')));
        });
        document.querySelectorAll('.hibernate-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.handleHibernate(e.target.closest('button').getAttribute('data-terminal-id')));
        });
        document.querySelectorAll('.resume-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.handleResume(e.target.closest('button').getAttribute('data-terminal-id')));
        });
        document.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.handleDelete(e.target.closest('button').getAttribute('data-terminal-id')));
        });
    }

    setupNumberInputs() {
        if (this.elements.cpuDecrease && this.elements.cpuIncrease && this.elements.cpuInput) {
            this.elements.cpuDecrease.addEventListener('click', () => TerminalsUtilities.adjustNumber(this.elements.cpuInput, -1));
            this.elements.cpuIncrease.addEventListener('click', () => TerminalsUtilities.adjustNumber(this.elements.cpuInput, 1));
        }
        if (this.elements.memoryDecrease && this.elements.memoryIncrease && this.elements.memoryInput) {
            this.elements.memoryDecrease.addEventListener('click', () => TerminalsUtilities.adjustNumber(this.elements.memoryInput, -1));
            this.elements.memoryIncrease.addEventListener('click', () => TerminalsUtilities.adjustNumber(this.elements.memoryInput, 1));
        }
        if (this.elements.storageDecrease && this.elements.storageIncrease && this.elements.storageInput) {
            this.elements.storageDecrease.addEventListener('click', () => TerminalsUtilities.adjustNumber(this.elements.storageInput, -1));
            this.elements.storageIncrease.addEventListener('click', () => TerminalsUtilities.adjustNumber(this.elements.storageInput, 1));
        }
        [this.elements.cpuInput, this.elements.memoryInput, this.elements.storageInput].forEach((input) => {
            if (input) input.addEventListener('input', () => this.updateSubmitButtonState());
        });
    }

    updateSubmitButtonState() {
        if (!this.elements.submitBtn) return;
        const allWithinBounds = [this.elements.cpuInput, this.elements.memoryInput, this.elements.storageInput]
            .every((input) => this.isWithinDeviceQuota(input, parseInt(input && input.value, 10)));
        this.elements.submitBtn.disabled = !allWithinBounds;
    }

    isWithinDeviceQuota(input, value) {
        if (!input || Number.isNaN(value)) return false;
        const min = parseInt(input.min, 10) || 1;
        const max = parseInt(input.max, 10);
        return value >= min && (Number.isNaN(max) || value <= max);
    }

    /**
     * Same-origin now (migration Part 3) - connects directly to /events/stream on this same
     * host, authenticated by the sseToken minted server-side at page render (page_handlers.py).
     */
    setupStatusStream() {
        if (!window.sseToken) {
            console.log('No SSE token available, skipping SSE setup');
            return;
        }

        let hasConnectedBefore = false;
        const eventSource = new EventSource(`/events/stream?token=${window.sseToken}`);

        eventSource.onopen = () => {
            console.log('SSE connection established for status updates');
            if (hasConnectedBefore) {
                this.loadTerminals();
            }
            hasConnectedBefore = true;
        };

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'connected') return;
                if (data.type === 'status_change') this.handleStatusChange(data);
            } catch (error) {
                console.error('Error parsing SSE message:', error);
            }
        };

        eventSource.onerror = (error) => {
            console.error('SSE connection error:', error);
        };

        this.eventSource = eventSource;
    }

    /**
     * The Play button's disabled state (TerminalsUtilities.isActiveDeviceTunnelOnline) reads
     * `window.activeDevice`, which is otherwise only refreshed opportunistically (opening the
     * create-terminal modal, or a container status_change SSE event). A device reconnecting in
     * the background is neither of those - it's a heartbeat timestamp aging back under the 90s
     * threshold with no discrete event to react to - so without this, a stale-offline button
     * could stay disabled for minutes after the device is actually reachable again, until the
     * user manually reloads. Polling is the right tool here (not a dedicated SSE event) precisely
     * because "online" is a staleness check, not a state transition.
     */
    setupDeviceStatusPolling() {
        this.deviceStatusPollInterval = setInterval(async () => {
            await this.refreshDeviceQuota();
            this.renderTerminalsList();
        }, 20000);
    }

    async handleStatusChange(data) {
        const { container_id, name, old_status, new_status } = data;
        console.log(`Container ${name} (${container_id}) status changed: ${old_status} -> ${new_status}`);

        const terminalIndex = this.terminals.findIndex(t => t.id === container_id);
        if (terminalIndex === -1) return;

        // The status_change SSE message only ever carries old_status/new_status - never
        // ip_address, port_mappings, or anything else that can change alongside a status
        // transition (a real bug caught live: CREATE succeeding genuinely sets a real IP the
        // instant the container goes Running, but the list item kept showing "Pending..." next
        // to the name until the page was manually refreshed, because this handler only ever
        // patched the cached `.status` field locally instead of re-fetching). Pulling the full,
        // current row from the server on every status change is simpler and more robust than
        // trying to track which other fields a given transition might also have changed.
        await this.loadTerminals();

        if (new_status === 'Running') {
            this.pendingContainers.delete(container_id);
            TerminalsUtilities.showNotification('success', 'Terminal Ready', `Terminal "${name}" is now running!`, 4000);
            this.refreshDeviceQuota();
        } else if (new_status === 'Failed') {
            TerminalsUtilities.showNotification('error', 'Terminal Failed', `Terminal "${name}" failed.`, 5000);
            this.pendingContainers.delete(container_id);
        } else if (new_status === 'Hibernated' || new_status === 'Deleting') {
            // Quota-widget staleness (2026-09-25): only CREATE's own success path and a
            // transition into Running ever refreshed the device-quota widget - Hibernate/Delete
            // free real capacity server-side (confirmed correct in the DB: used_cpu goes back
            // down immediately) but the browser never re-fetched it, so the number on screen
            // looked stuck until the unrelated 20s device-status poll happened to catch up, or
            // the user reopened the create-terminal modal.
            //
            // 'Hibernated' fires exactly when the real release happens (container_mutation.py's
            // _apply_hibernate updates status AND releases quota in the same step) - this catches
            // it instantly. 'Deleting' only ever fires at REQUEST time (the soft-delete stamp) -
            // the container row is later hard-DELETEd, not UPDATEd, when quota is actually
            // released, and a SQL DELETE never fires this UPDATE-only trigger at all - so a
            // delete's own quota release still only becomes visible via the 20s poll. Refreshing
            // here anyway is still a real improvement (catches everything BUT delete's final
            // number instantly) and is harmless even where it's a moment too early.
            this.refreshDeviceQuota();
        }
    }

    handlePlay(terminalId) {
        window.open(`/terminal/${terminalId}`, '_blank');
    }

    async handleInfo(terminalId) {
        try {
            const response = await fetch(`/app/containers/${terminalId}`);
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || `HTTP ${response.status}`);
            }
            this.renderInfoModal(result.container);
            this.elements.infoModalOverlay.classList.add('active');
            document.body.style.overflow = 'hidden';
        } catch (error) {
            TerminalsUtilities.showNotification('error', 'Could Not Load Info', error.message, 5000);
        }
    }

    renderInfoModal(container) {
        const portMappings = Array.isArray(container.port_mappings) ? container.port_mappings : [];
        const portsText = portMappings.length
            ? portMappings.map((p) => `${p.publish_port}→${p.target_port}/${p.protocol || 'TCP'}`).join(', ')
            : '-';
        const createdAt = container.created_at ? new Date(container.created_at).toLocaleString() : '-';
        const lastSavedAt = container.last_saved_at ? new Date(container.last_saved_at).toLocaleString() : 'Never';

        const rows = [
            ['Name', container.name || '-'],
            ['Status', TerminalsUtilities.formatStatus(container.status || 'Unknown')],
            ['CPU limit', container.cpu_limit ? `${container.cpu_limit} core(s)` : '-'],
            ['Memory limit', container.memory_limit || '-'],
            ['Storage limit', container.storage_limit || '-'],
            ['IP address', container.ip_address || 'Pending...'],
            ['Ports', portsText],
            ['Created', createdAt],
            ['Last saved', lastSavedAt],
        ];

        this.elements.infoModalBody.innerHTML = rows
            .map(([label, value]) => `
                <div class="info-row">
                    <span class="info-label">${label}</span>
                    <span class="info-value">${value}</span>
                </div>
            `)
            .join('');
    }

    closeInfoModal() {
        this.elements.infoModalOverlay.classList.remove('active');
        document.body.style.overflow = '';
    }

    /**
     * POST /app/containers/{id}/hibernate - genuinely new capability (migration Part 3), there
     * was no browser-reachable manual hibernate before this.
     */
    async handleHibernate(terminalId) {
        const terminal = this.terminals.find(t => t.id === terminalId);
        const terminalName = terminal?.name || 'this terminal';
        const confirmed = confirm(
            `Hibernate "${terminalName}"? This saves a snapshot, stops it, and frees up this device's resources. It can be resumed later.`
        );
        if (!confirmed) return;

        this.hibernatingIds.add(terminalId);
        this.renderTerminalsList();

        try {
            const resp = await fetch(`/app/containers/${terminalId}/hibernate`, {
                method: 'POST',
                headers: TerminalsUtilities.csrfHeaders(),
            });
            const result = await resp.json().catch(() => ({}));
            if (!resp.ok) {
                throw new Error(result.error || `HTTP ${resp.status}`);
            }
            TerminalsUtilities.showNotification('success', 'Hibernating', `Terminal "${terminalName}" is being hibernated.`, 4000);
        } catch (e) {
            TerminalsUtilities.showNotification('error', 'Hibernate Failed', e.message, 6000);
        } finally {
            this.hibernatingIds.delete(terminalId);
            await this.loadTerminals();
            // Don't wait on the status_change SSE round-trip for this tab's own quota widget -
            // see handleStatusChange's own Hibernated/Deleting branch for the general fix.
            this.refreshDeviceQuota();
        }
    }

    async handleResume(terminalId) {
        try {
            const resp = await fetch(`/app/containers/${terminalId}/resume`, {
                method: 'POST',
                headers: TerminalsUtilities.csrfHeaders(),
            });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.error || `HTTP ${resp.status}`);
            }
            TerminalsUtilities.showNotification('success', 'Resuming', 'Restoring your workspace from its last snapshot…', 4000);
            await this.loadTerminals();
        } catch (e) {
            TerminalsUtilities.showNotification('error', 'Resume failed', e.message, 6000);
        }
    }

    /**
     * A single call now (migration Part 3) - Device Agent handles the actual pod teardown
     * asynchronously once this DELETE command is delivered, no separate DB/K8s two-step needed
     * from the browser's side any more.
     */
    async handleDelete(terminalId) {
        const terminal = this.terminals.find(t => t.id === terminalId);
        const terminalName = terminal?.name || 'Unknown';

        const confirmed = confirm(`Are you sure you want to delete terminal "${terminalName}"?`);
        if (!confirmed) return;

        try {
            const resp = await fetch(`/app/containers/${terminalId}/delete`, {
                method: 'POST',
                headers: TerminalsUtilities.csrfHeaders(),
            });
            const result = await resp.json().catch(() => ({}));
            if (!resp.ok) {
                throw new Error(result.error || `HTTP ${resp.status}`);
            }
            await this.loadTerminals();
            // Don't wait on the status_change SSE round-trip for this tab's own quota widget -
            // see handleStatusChange's own Hibernated/Deleting branch for the general fix.
            this.refreshDeviceQuota();
            TerminalsUtilities.showNotification('info', 'Terminal Deleted', `Terminal "${terminalName}" has been deleted.`, 4000);
        } catch (error) {
            console.error('Error deleting terminal:', error);
            TerminalsUtilities.showNotification('error', 'Deletion Error', error.message, 5000);
        }
    }

    async openModal() {
        this.elements.modalOverlay.classList.add('active');
        document.body.style.overflow = 'hidden';
        await this.refreshDeviceQuota();
        this.resetForm();
    }

    closeModal() {
        this.elements.modalOverlay.classList.remove('active');
        document.body.style.overflow = '';
    }

    /**
     * Re-fetches this session's active device quota from Cloud's own /app/device-quota
     * (migration Part 3 - replaces Local's thin proxy to Cloud's internal active-device lookup).
     */
    async refreshDeviceQuota() {
        try {
            const response = await fetch('/app/device-quota');
            const data = await response.json();
            window.activeDevice = data.device;
        } catch (error) {
            console.error('Error refreshing device quota:', error);
        }
        this.loadDeviceQuota();
        this.configureResourceControls();
    }

    resetForm() {
        this.elements.terminalForm.reset();
        this.elements.cpuInput.value = 1;
        this.elements.memoryInput.value = 1;
        this.elements.storageInput.value = 2;
        this.configureResourceControls();
    }

    async loadOperatingSystems() {
        try {
            this.operatingSystems = TerminalsUtilities.getOperatingSystems();
            this.populateOperatingSystems();
        } catch (error) {
            console.error('Error loading operating systems:', error);
            this.elements.operatingSystemSelect.innerHTML = '<option value="">Error loading OS</option>';
            TerminalsUtilities.showNotification('error', 'Loading Error', 'Failed to load operating systems', 5000);
        }
    }

    populateOperatingSystems() {
        this.elements.operatingSystemSelect.innerHTML = '';
        if (this.operatingSystems.length === 0) {
            this.elements.operatingSystemSelect.innerHTML = '<option value="">No operating systems available</option>';
            return;
        }
        this.operatingSystems.forEach(os => {
            const option = document.createElement('option');
            option.value = os.name;
            option.textContent = os.name;
            this.elements.operatingSystemSelect.appendChild(option);
        });
    }

    /**
     * One call now (migration Part 3) - POST /app/containers creates the container row and
     * (with DEVICE_COMMAND_CREATE_ENABLED, already true in prod) queues a durable CREATE command
     * for Device Agent in the same request. Status updates arrive via the SSE stream, not a
     * second/third follow-up call from here.
     */
    async handleFormSubmit(e) {
        e.preventDefault();

        const submitBtn = document.getElementById('submitBtn');
        const originalText = submitBtn.textContent;
        this.showLoadingState(submitBtn);

        try {
            const userInfo = TerminalsUtilities.getUserInfo();
            const userName = userInfo.name || '';
            const generatedUsername = TerminalsUtilities.normalizeName(userName);

            const formData = new FormData(e.target);
            const selectedImageName = (formData.get('os') || '').toString();
            const imageRecord = TerminalsUtilities.findImageByName(selectedImageName);

            const cpuValue = parseInt(formData.get('cpu'), 10) || 1;
            const memoryValue = parseInt(formData.get('memory'), 10) || 1;
            const storageValue = parseInt(formData.get('storage'), 10) || 2;

            if (!this.isWithinDeviceQuota(this.elements.cpuInput, cpuValue)
                || !this.isWithinDeviceQuota(this.elements.memoryInput, memoryValue)
                || !this.isWithinDeviceQuota(this.elements.storageInput, storageValue)) {
                this.hideLoadingState(submitBtn, originalText);
                TerminalsUtilities.showNotification(
                    'error', 'Not Enough Quota',
                    'The requested CPU, Memory, or Storage exceeds this device\'s remaining quota.',
                    5000
                );
                return;
            }

            const createBody = {
                image_id: imageRecord?.id || '',
                name: (formData.get('name') || '').toString(),
                port_mappings: [{ publish_port: 2222, target_port: 22, protocol: 'TCP' }],
                environment_vars: {
                    SSH_USERNAME: generatedUsername,
                    SSH_PASSWORD: TerminalsUtilities.generatePassword(8),
                },
                cpu_limit: `${cpuValue}`,
                memory_limit: `${memoryValue}Gi`,
                storage_limit: `${storageValue}Gi`,
            };

            const resp = await fetch('/app/containers', {
                method: 'POST',
                headers: TerminalsUtilities.csrfHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify(createBody),
            });
            const result = await resp.json();
            if (!resp.ok) {
                throw new Error(result.error || `HTTP ${resp.status}`);
            }

            this.closeModal();
            this.refreshDeviceQuota();

            const created = result.container || {};
            this.terminals.unshift({
                id: created.id,
                name: created.name,
                ipAddress: created.ip_address || 'Pending...',
                port: created.port_mappings?.[0]?.publish_port || '-',
                status: created.status || 'Queued',
            });
            if (created.id) this.pendingContainers.add(created.id);
            this.renderTerminalsList();

            TerminalsUtilities.showNotification(
                'info', 'Terminal Queued', 'Your terminal is being created. This may take a moment...', 4000
            );
        } catch (error) {
            console.error('Error submitting form:', error);
            TerminalsUtilities.showNotification('error', 'Submission Error', error.message, 5000);
        } finally {
            this.hideLoadingState(submitBtn, originalText);
        }
    }

    showLoadingState(button) {
        if (!button) return;
        button.disabled = true;
        button.innerHTML = `<span class="loading-spinner"></span> Creating Terminal...`;
        button.classList.add('loading');
    }

    hideLoadingState(button, originalText) {
        if (!button) return;
        button.disabled = false;
        button.textContent = originalText;
        button.classList.remove('loading');
    }

    showError(message) {
        this.elements.terminalsList.innerHTML = `<div class="loading-message error">${message}</div>`;
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { TerminalsUtilities, TerminalsHandler };
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('Terminals page DOM is ready');
    const terminalsHandler = new TerminalsHandler();
    terminalsHandler.init();
});
