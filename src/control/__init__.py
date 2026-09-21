'''
Cloud Device Control gRPC server (BROWSETERM_CLOUD_CONTROL_PLANE_MIGRATION.md Part 6).

Accepts the Device Agent's outbound bidirectional stream, tracks live connections, and delivers
durable commands from browseterm-db's device_commands table. See grpc_server.py for the process
entrypoint.
'''
