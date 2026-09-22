#!/bin/bash
# Cloud entrypoint - run uvicorn directly from the in-project venv (no poetry at runtime, so it
# works as the non-root user; poetry's /root home/cache are not needed).
#
# --proxy-headers --forwarded-allow-ips='*' (migration Part 3): TLS terminates at the Traefik
# ingress, which forwards plain HTTP to this pod - without this, uvicorn (and therefore every
# request.url/url_for() call, e.g. templates/base.html's `{{ url_for('static', ...) }}`) sees
# scheme=http always, generating broken/insecure absolute URLs behind the real HTTPS ingress.
# '*' is safe here specifically because the app-allow-ingress-only NetworkPolicy (infra/cloud/
# cloud-vps.yaml) already restricts inbound traffic to Traefik alone - nothing else can reach this
# pod directly to forge these headers.
exec /app/.venv/bin/uvicorn app:app --host 0.0.0.0 --port 9999 --proxy-headers --forwarded-allow-ips='*'
