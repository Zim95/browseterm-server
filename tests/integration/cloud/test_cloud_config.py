'''
P04: `src.cloud.config` resolves PostgreSQL/Redis settings from the environment, using the same
env-var conventions `src.common.config` already uses (reused, not duplicated).

Run in a subprocess per case: the underlying values are read from `os.getenv(...)` once at
module-import time, so re-reading them within one already-imported pytest process would just
return the first process's values regardless of env changes.
'''
import os
import subprocess
import sys
from pathlib import Path
from unittest import TestCase

REPO_ROOT = Path(__file__).resolve().parents[3]


def _run(code: str, extra_env: dict) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


class TestCloudConfigResolvesPostgres(TestCase):
    def test_postgres_settings_resolved_from_env(self) -> None:
        code = (
            "from src.cloud.config import POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_DB, DB_CONFIG\n"
            "assert POSTGRES_HOST == 'cloud-pg-host', POSTGRES_HOST\n"
            "assert POSTGRES_PORT == 6543, POSTGRES_PORT\n"
            "assert POSTGRES_USER == 'cloud_user', POSTGRES_USER\n"
            "assert POSTGRES_DB == 'cloud_db', POSTGRES_DB\n"
            "assert DB_CONFIG.host == 'cloud-pg-host'\n"
            "assert DB_CONFIG.port == 6543\n"
            "assert DB_CONFIG.database == 'cloud_db'\n"
            "print('OK')\n"
        )
        result = _run(code, {
            "POSTGRES_HOST": "cloud-pg-host",
            "POSTGRES_PORT": "6543",
            "POSTGRES_USER": "cloud_user",
            "POSTGRES_PASSWORD": "cloud_pass",
            "POSTGRES_DB": "cloud_db",
        })
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("OK", result.stdout)


class TestCloudConfigResolvesRedis(TestCase):
    def test_redis_settings_resolved_from_env(self) -> None:
        code = (
            "from src.cloud.config import REDIS_HOST, REDIS_PORT, REDIS_USERNAME, REDIS_PASSWORD, REDIS_DB\n"
            "assert REDIS_HOST == 'cloud-redis-host', REDIS_HOST\n"
            "assert REDIS_PORT == 7000, REDIS_PORT\n"
            "assert REDIS_USERNAME == 'cloud_redis_user', REDIS_USERNAME\n"
            "assert REDIS_PASSWORD == 'cloud_redis_pass', REDIS_PASSWORD\n"
            "assert REDIS_DB == 3, REDIS_DB\n"
            "print('OK')\n"
        )
        result = _run(code, {
            "REDIS_HOST": "cloud-redis-host",
            "REDIS_PORT": "7000",
            "REDIS_USERNAME": "cloud_redis_user",
            "REDIS_PASSWORD": "cloud_redis_pass",
            "REDIS_DB": "3",
        })
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("OK", result.stdout)

    def test_cloud_config_does_not_export_local_only_settings(self) -> None:
        '''`src.cloud.config` must not re-export ContainerMaker/Socket-SSH/payment-gateway/OAuth
        settings -- those belong exclusively to the Local-only configuration surface.'''
        import src.cloud.config as cloud_config
        local_only_names = {
            "CONTAINER_MAKER_HOST", "CONTAINER_MAKER_PORT", "CONTAINER_MAKER_CERTS_SECRET_NAME",
            "SOCKET_SSH_WSS_URL", "PAYMENT_GATEWAY_HOST", "PAYMENT_GATEWAY_PORT",
            "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET",
        }
        exported = set(cloud_config.__all__)
        self.assertTrue(exported.isdisjoint(local_only_names), exported & local_only_names)
