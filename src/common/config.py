import os
from browseterm_db.common.config import DBConfig


# Container Maker Config
CONTAINER_MAKER_HOST: str = "container-maker-development-service"
CONTAINER_MAKER_PORT: int = 50052

CONTAINER_MAKER_SERVER_KEY_FILE: str = "./cert/server.key"
CONTAINER_MAKER_SERVER_CERT_FILE: str = "./cert/server.crt"
CONTAINER_MAKER_CLIENT_KEY_FILE: str = "./cert/client.key"
CONTAINER_MAKER_CLIENT_CERT_FILE: str = "./cert/client.crt"
CONTAINER_MAKER_CA_FILE: str = "./cert/ca.crt"

CONTAINER_MAKER_SERVER_CERT_ENV_VAR: str = "CONTAINER_MAKER_SERVER_CRT"
CONTAINER_MAKER_SERVER_KEY_ENV_VAR: str = "CONTAINER_MAKER_SERVER_KEY"
CONTAINER_MAKER_CLIENT_CERT_ENV_VAR: str = "CONTAINER_MAKER_CLIENT_CRT"
CONTAINER_MAKER_CLIENT_KEY_ENV_VAR: str = "CONTAINER_MAKER_CLIENT_KEY"
CONTAINER_MAKER_CA_ENV_VAR: str = "CONTAINER_MAKER_CA_CRT"

# Cert Manager Config
CERT_MANAGER_CRON_JOB_NAME: str = os.getenv("CERT_MANAGER_CRON_JOB_NAME")
CERT_MANAGER_CRON_JOB_NAMESPACE: str = os.getenv("CERT_MANAGER_CRON_JOB_NAMESPACE")


# Auth common config
AUTH_REDIRECT_BASE_URI: str = os.getenv("AUTH_REDIRECT_BASE_URI", "http://localhost:9999")

# Google Authentication Config
GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_AUTH_META_URL: str = 'https://accounts.google.com/o/oauth2/auth'
GOOGLE_AUTH_SCOPE: str = 'openid email profile'
GOOGLE_AUTH_REDIRECT_URI: str = f"{AUTH_REDIRECT_BASE_URI}/google-login-redirect"
GOOGLE_ACCESS_TOKEN_URL: str = 'https://oauth2.googleapis.com/token'
GOOGLE_USER_INFO_URL: str = 'https://www.googleapis.com/oauth2/v2/userinfo'
GOOGLE_TOKEN_EXCHANGE_HEADERS: dict = {'Content-Type': 'application/x-www-form-urlencoded'}

# Github Authentication Config
GITHUB_CLIENT_ID: str = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET: str = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_AUTH_META_URL: str = 'https://github.com/login/oauth/authorize'
GITHUB_AUTH_SCOPE: str = 'user:email user'
GITHUB_AUTH_REDIRECT_URI: str = f"{AUTH_REDIRECT_BASE_URI}/github-login-redirect"
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
