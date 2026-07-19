/**
 * Frontend unit tests for the save-session logic in
 * templates/static/js/terminalpage.js
 *
 * Runs under Jest with the jsdom test environment (so `window`, `document`, and
 * `URLSearchParams` exist). terminalpage.js exposes its classes via a guarded
 * `module.exports` (a no-op in the browser), which lets us require it here.
 *
 * We mock the browser boundaries the save logic touches: global.fetch,
 * global.EventSource, window.userInfo / window.terminalInfo, and the
 * TerminalPageUtilities.showNotification helper.
 */

const path = require('path');
const MockEventSource = require('./__mocks__/mock.eventsource');

const {
    TerminalPageUtilities,
    TerminalPageHandler,
} = require(path.join(__dirname, '..', '..', 'templates', 'static', 'js', 'terminalpage.js'));

// Helper: build a handler wired up just enough to exercise the save methods,
// without running the full init() (which needs xterm.js, WebSockets, etc.).
function makeHandler({ containerId = 'container-123', withButton = true } = {}) {
    const handler = new TerminalPageHandler();
    handler.terminalInfo = { id: containerId };

    let saveBtn = null;
    if (withButton) {
        saveBtn = document.createElement('button');
        saveBtn.id = 'saveBtn';
    }
    handler.elements = { saveBtn };
    return { handler, saveBtn };
}

describe('terminalpage save logic', () => {
    let notifySpy;

    beforeEach(() => {
        // Fresh notification spy per test.
        notifySpy = jest
            .spyOn(TerminalPageUtilities, 'showNotification')
            .mockImplementation(() => {});

        // Reset browser-boundary globals.
        global.fetch = jest.fn();
        global.EventSource = MockEventSource;
        MockEventSource.reset();

        window.userInfo = { id: 'user-42' };
        window.terminalInfo = { id: 'container-123' };
    });

    afterEach(() => {
        jest.restoreAllMocks();
        delete global.fetch;
        delete global.EventSource;
        delete window.userInfo;
        delete window.terminalInfo;
    });

    describe('setSaveSpinner()', () => {
        test('activating disables the button and adds the "saving" class', () => {
            const { handler, saveBtn } = makeHandler();

            handler.setSaveSpinner(true);

            expect(saveBtn.disabled).toBe(true);
            expect(saveBtn.classList.contains('saving')).toBe(true);
        });

        test('deactivating re-enables the button and removes the "saving" class', () => {
            const { handler, saveBtn } = makeHandler();

            handler.setSaveSpinner(true);
            handler.setSaveSpinner(false);

            expect(saveBtn.disabled).toBe(false);
            expect(saveBtn.classList.contains('saving')).toBe(false);
        });

        test('is a no-op when there is no save button', () => {
            const { handler } = makeHandler({ withButton: false });
            expect(() => handler.setSaveSpinner(true)).not.toThrow();
        });
    });

    describe('handleSaveSession()', () => {
        test('success path: POSTs the right payload, keeps spinner on, shows info notification', async () => {
            const { handler, saveBtn } = makeHandler({ containerId: 'container-123' });
            global.fetch.mockResolvedValue({ ok: true, json: async () => ({}) });

            await handler.handleSaveSession();

            // fetch was called with the expected URL, method and body.
            expect(global.fetch).toHaveBeenCalledTimes(1);
            const [url, opts] = global.fetch.mock.calls[0];
            expect(url).toBe('/save-container');
            expect(opts.method).toBe('POST');
            expect(opts.headers['Content-Type']).toBe('application/json');
            expect(JSON.parse(opts.body)).toEqual({
                container_id: 'container-123',
                network_name: 'user-42-namespace',
            });

            // Spinner stays ON until the SSE reports completion.
            expect(saveBtn.disabled).toBe(true);
            expect(saveBtn.classList.contains('saving')).toBe(true);

            // Info notification shown.
            expect(notifySpy).toHaveBeenCalledWith(
                'info',
                expect.any(String),
                expect.any(String),
                expect.any(Number),
            );
        });

        test('error path: !resp.ok clears the spinner and shows an error notification', async () => {
            const { handler, saveBtn } = makeHandler();
            global.fetch.mockResolvedValue({
                ok: false,
                status: 500,
                json: async () => ({ error: 'boom from server' }),
            });

            await handler.handleSaveSession();

            // Spinner cleared.
            expect(saveBtn.disabled).toBe(false);
            expect(saveBtn.classList.contains('saving')).toBe(false);

            // Error notification carries the server-provided message.
            expect(notifySpy).toHaveBeenCalledWith(
                'error',
                'Save failed',
                'boom from server',
                expect.any(Number),
            );
        });

        test('error path: falls back to HTTP status when body has no error field', async () => {
            const { handler } = makeHandler();
            global.fetch.mockResolvedValue({
                ok: false,
                status: 503,
                json: async () => ({}),
            });

            await handler.handleSaveSession();

            expect(notifySpy).toHaveBeenCalledWith(
                'error',
                'Save failed',
                'HTTP 503',
                expect.any(Number),
            );
        });

        test('bails out (no fetch) when there is no container id', async () => {
            const { handler } = makeHandler({ containerId: null });

            await handler.handleSaveSession();

            expect(global.fetch).not.toHaveBeenCalled();
            expect(notifySpy).toHaveBeenCalledWith(
                'error',
                'Save failed',
                'No container id available.',
                expect.any(Number),
            );
        });
    });

    describe('setupSaveStatusStream()', () => {
        test('opens an EventSource against the user-scoped stream URL', () => {
            const { handler } = makeHandler();

            handler.setupSaveStatusStream();

            expect(MockEventSource.instances).toHaveLength(1);
            expect(MockEventSource.instances[0].url).toBe(
                '/container-status-stream?user_id=user-42',
            );
        });

        test('does not open a stream when userInfo.id is missing', () => {
            window.userInfo = {};
            const { handler } = makeHandler();

            handler.setupSaveStatusStream();

            expect(MockEventSource.instances).toHaveLength(0);
        });

        test('a matching "Succeeded" save_status_change clears the spinner and shows success', () => {
            const { handler, saveBtn } = makeHandler({ containerId: 'container-123' });
            handler.setSaveSpinner(true); // simulate an in-flight save

            handler.setupSaveStatusStream();
            const es = MockEventSource.instances[0];

            es.emitMessage({
                type: 'save_status_change',
                container_id: 'container-123',
                save_status: 'Succeeded',
                saved_image: 'my-image:latest',
            });

            expect(saveBtn.disabled).toBe(false);
            expect(saveBtn.classList.contains('saving')).toBe(false);
            expect(notifySpy).toHaveBeenCalledWith(
                'success',
                'Saved',
                expect.stringContaining('my-image:latest'),
                expect.any(Number),
            );
        });

        test('a matching "Failed" save_status_change clears the spinner and shows error', () => {
            const { handler, saveBtn } = makeHandler({ containerId: 'container-123' });
            handler.setSaveSpinner(true);

            handler.setupSaveStatusStream();
            const es = MockEventSource.instances[0];

            es.emitMessage({
                type: 'save_status_change',
                container_id: 'container-123',
                save_status: 'Failed',
                save_error: 'disk full',
            });

            expect(saveBtn.disabled).toBe(false);
            expect(saveBtn.classList.contains('saving')).toBe(false);
            expect(notifySpy).toHaveBeenCalledWith(
                'error',
                'Save failed',
                'disk full',
                expect.any(Number),
            );
        });

        test('ignores events for a different container', () => {
            const { handler, saveBtn } = makeHandler({ containerId: 'container-123' });
            handler.setSaveSpinner(true);

            handler.setupSaveStatusStream();
            MockEventSource.instances[0].emitMessage({
                type: 'save_status_change',
                container_id: 'some-other-container',
                save_status: 'Succeeded',
            });

            // Spinner untouched, no notification.
            expect(saveBtn.disabled).toBe(true);
            expect(saveBtn.classList.contains('saving')).toBe(true);
            expect(notifySpy).not.toHaveBeenCalled();
        });

        test('ignores events of an unrelated type', () => {
            const { handler, saveBtn } = makeHandler({ containerId: 'container-123' });
            handler.setSaveSpinner(true);

            handler.setupSaveStatusStream();
            MockEventSource.instances[0].emitMessage({
                type: 'some_other_event',
                container_id: 'container-123',
                save_status: 'Succeeded',
            });

            expect(saveBtn.disabled).toBe(true);
            expect(notifySpy).not.toHaveBeenCalled();
        });

        test('silently ignores malformed (non-JSON) event data', () => {
            const { handler } = makeHandler({ containerId: 'container-123' });

            handler.setupSaveStatusStream();
            const es = MockEventSource.instances[0];

            expect(() => es.emitRaw('not-json{')).not.toThrow();
            expect(notifySpy).not.toHaveBeenCalled();
        });
    });
});
