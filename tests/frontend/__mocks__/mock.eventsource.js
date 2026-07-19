/*
    Minimal manual mock for the browser EventSource API.

    Mirrors the mocking style used in socket-ssh (tests/__mocks__/mock.websocket.js):
    a hand-written class we assign onto the relevant global, rather than a Jest
    automock. The real EventSource opens a persistent HTTP connection and fires
    `onmessage` when the server pushes an SSE event. Here we skip the network and
    let the test drive `onmessage` / `onerror` directly via helper methods.
*/

class MockEventSource {
    constructor(url) {
        this.url = url;
        this.onmessage = null;
        this.onerror = null;
        this.readyState = 0; // CONNECTING
        this.closed = false;
        MockEventSource.instances.push(this);
    }

    // Simulate a server-sent event carrying `dataObj` as its JSON payload.
    emitMessage(dataObj) {
        if (typeof this.onmessage === 'function') {
            this.onmessage({ data: JSON.stringify(dataObj) });
        }
    }

    // Simulate an SSE that arrives with non-JSON data (parse should fail silently).
    emitRaw(rawString) {
        if (typeof this.onmessage === 'function') {
            this.onmessage({ data: rawString });
        }
    }

    emitError() {
        if (typeof this.onerror === 'function') {
            this.onerror(new Error('stream error'));
        }
    }

    close() {
        this.closed = true;
        this.readyState = 2; // CLOSED
    }
}

// Track every instance the code under test creates so assertions can inspect them.
MockEventSource.instances = [];
MockEventSource.reset = () => { MockEventSource.instances = []; };

module.exports = MockEventSource;
