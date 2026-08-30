#!/bin/bash
# Cloud entrypoint - run uvicorn directly from the in-project venv (no poetry at runtime, so it
# works as the non-root user; poetry's /root home/cache are not needed).
exec /app/.venv/bin/uvicorn cloud_app:app --host 0.0.0.0 --port 9999
