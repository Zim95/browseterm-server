import os
from browseterm_db.common.config import DBConfig


# Container Maker Config
CONTAINER_MAKER_HOST: str = os.getenv("CONTAINER_MAKER_HOST", "container-maker-development-service")
CONTAINER_MAKER_PORT: int = int(os.getenv("CONTAINER_MAKER_PORT", "50052"))

# Kubernetes secret configuration for Container Maker certificates
CONTAINER_MAKER_CERTS_SECRET_NAME: str = os.getenv(
    "CONTAINER_MAKER_CERTS_SECRET_NAME",
    "container-maker-development-service-certs"
)

# Payment Gateway Config
PAYMENT_GATEWAY_HOST: str = os.getenv("PAYMENT_GATEWAY_HOST", "payment-gateway-development-service")
PAYMENT_GATEWAY_PORT: int = int(os.getenv("PAYMENT_GATEWAY_PORT", "50053"))

# Kubernetes secret configuration for Payment Gateway certificates
PAYMENT_GATEWAY_CERTS_SECRET_NAME: str = os.getenv(
    "PAYMENT_GATEWAY_CERTS_SECRET_NAME",
    "payment-gateway-development-service-certs"
)
# Kubernetes namespace for the application (used for cross-namespace service access)
NAMESPACE: str = os.getenv("NAMESPACE")

# Cert Manager Config
CERT_MANAGER_CRON_JOB_NAME: str = os.getenv("CERT_MANAGER_CRON_JOB_NAME")
CERT_MANAGER_CRON_JOB_NAMESPACE: str = os.getenv("CERT_MANAGER_CRON_JOB_NAMESPACE")


# Auth common config
#
# P07: Cloud is the sole OAuth authority (see p07.md). AUTH_REDIRECT_BASE_URI is now CLOUD's own
# public base URL (Google/GitHub must only ever know about Cloud callback URLs, never
# browseterm.local.com/127.0.0.1/Desktop directly - p07.md section 5) - default matches Cloud's
# own DNS convention (browseterm-server-local's cloud_client/config.py and browseterm-desktop's
# desktop/config.py both already default BROWSETERM_CLOUD_API_URL to
# http://browseterm.cloud.com:9999).
AUTH_REDIRECT_BASE_URI: str = os.getenv("AUTH_REDIRECT_BASE_URI", "http://browseterm.cloud.com:9999")

# The ONE allowlisted destination Cloud will ever redirect a completed local_login handoff to.
# Never taken from a request parameter (p07.md section 10 - no open redirect). Local's own
# `/auth/callback` route (browseterm-server-local/src/template_handlers.py) redeems the `code`
# query param against POST /auth/handoff/redeem.
BROWSETERM_LOCAL_CALLBACK_URL: str = os.getenv(
    "BROWSETERM_LOCAL_CALLBACK_URL", "http://browseterm.local.com/auth/callback"
)

# TrustedHost protection (p07.md section 28). "*" is the explicit, documented dev-permissive
# default - Starlette's TrustedHostMiddleware default is already "*" (disabled), we're just
# making the choice visible/configurable rather than hardcoding a production hostname that
# doesn't exist yet. Comma-separated in production, e.g. "browseterm.cloud.com".
BROWSETERM_ALLOWED_HOSTS: list = [h.strip() for h in os.getenv("BROWSETERM_ALLOWED_HOSTS", "*").split(",")]

# Google Authentication Config
GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_AUTH_META_URL: str = 'https://accounts.google.com/o/oauth2/auth'
GOOGLE_AUTH_SCOPE: str = 'openid email profile'
GOOGLE_AUTH_REDIRECT_URI: str = f"{AUTH_REDIRECT_BASE_URI}/auth/google/callback"
GOOGLE_ACCESS_TOKEN_URL: str = 'https://oauth2.googleapis.com/token'
GOOGLE_USER_INFO_URL: str = 'https://www.googleapis.com/oauth2/v2/userinfo'
GOOGLE_TOKEN_EXCHANGE_HEADERS: dict = {'Content-Type': 'application/x-www-form-urlencoded'}

# Github Authentication Config
GITHUB_CLIENT_ID: str = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET: str = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_AUTH_META_URL: str = 'https://github.com/login/oauth/authorize'
GITHUB_AUTH_SCOPE: str = 'user:email user'
GITHUB_AUTH_REDIRECT_URI: str = f"{AUTH_REDIRECT_BASE_URI}/auth/github/callback"
GITHUB_ACCESS_TOKEN_URL: str = 'https://github.com/login/oauth/access_token'
GITHUB_USER_INFO_URL: str = 'https://api.github.com/user'
GITHUB_TOKEN_EXCHANGE_HEADERS: dict = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Accept': 'application/json',
    'Accept-Encoding': 'application/json'
}

# Redis Configuration
REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
REDIS_USERNAME: str = os.getenv("REDIS_USERNAME", "")
REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
REDIS_SESSION_EXPIRY: int = 86400
REDIS_SESSION_PREFIX: str = "session:"

# Cookie Security Configuration
# Set secure=True in production (HTTPS), False in development (HTTP)
COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"
# samesite options: "strict", "lax", or "none"
COOKIE_SAMESITE: str = os.getenv("COOKIE_SAMESITE", "lax")

# Socket SSH WebSocket Configuration
# Set via SOCKET_SSH_WSS_URL environment variable
# For Ingress: ws://browseterm.local/ws
# For production: wss://yourdomain.com/ws
SOCKET_SSH_WSS_URL: str = os.getenv("SOCKET_SSH_WSS_URL", "ws://localhost:8000")


# Postgres Configuration
POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "blahbob")
POSTGRES_DB: str = os.getenv("POSTGRES_DB", "blahbob")
DB_CONFIG: DBConfig = DBConfig(
    username=POSTGRES_USER,
    password=POSTGRES_PASSWORD,
    host=POSTGRES_HOST,
    port=POSTGRES_PORT,
    database=POSTGRES_DB
)


# Resource Request Ratios (request = limit * ratio)
# CPU: 10% of limit
RESOURCE_CPU_REQUEST_RATIO: float = float(os.getenv("RESOURCE_CPU_REQUEST_RATIO", "0.1"))
# Memory: 50% of limit
RESOURCE_MEMORY_REQUEST_RATIO: float = float(os.getenv("RESOURCE_MEMORY_REQUEST_RATIO", "0.5"))
# Ephemeral storage: 50% of limit
RESOURCE_EPHEMERAL_REQUEST_RATIO: float = float(os.getenv("RESOURCE_EPHEMERAL_REQUEST_RATIO", "0.5"))

# P16 (see ~/browseterm/p.md's "P16" section, plan section 6): flat Docker Hub repository prefix
# for workspace snapshots - "browseterm/<user_id>_<container_id>", never a nested
# "browseterm/<user>/<container>" path (Docker Hub doesn't support arbitrary nesting) and never a
# mutable name (UUIDs only). Configurable per the plan's explicit instruction.
SNAPSHOT_REGISTRY_REPO_PREFIX: str = os.getenv("SNAPSHOT_REGISTRY_REPO_PREFIX", "browseterm")
