'''
Config for the Cloud Device Control gRPC server. Reuses src.cloud.config's Postgres/Redis
settings rather than duplicating them - see that module's own boundary docstring.
'''
import os

GRPC_CONTROL_PORT: int = int(os.getenv("GRPC_CONTROL_PORT", "50060"))

# A device with no heartbeat/message for longer than this is marked OFFLINE. remotetunelling.md's
# tunnel offline threshold (90s) is the precedent for this kind of value in this codebase; control
# stream heartbeats are expected more often than tunnel heartbeats, so this can be tighter.
DEVICE_OFFLINE_THRESHOLD_SECONDS: int = int(os.getenv("DEVICE_OFFLINE_THRESHOLD_SECONDS", "45"))

# Cloud's own outbound Ping cadence when it hasn't heard anything from a device recently, so a
# genuinely dead TCP connection (no FIN received) is still detected instead of hanging forever.
PING_INTERVAL_SECONDS: int = int(os.getenv("PING_INTERVAL_SECONDS", "20"))

# How long a graceful drain (SIGTERM) waits for in-flight streams to close on their own, after
# sending ServerDraining to every connected device, before the server force-stops.
DRAIN_GRACE_SECONDS: int = int(os.getenv("DRAIN_GRACE_SECONDS", "15"))

# Cloud's minimum accepted Device Agent protocol version. A Hello below this is rejected with a
# clear upgrade instruction (Part 25) rather than accepted into an ambiguous partial-compat state.
MINIMUM_AGENT_PROTOCOL_VERSION: str = os.getenv("MINIMUM_AGENT_PROTOCOL_VERSION", "v1")
