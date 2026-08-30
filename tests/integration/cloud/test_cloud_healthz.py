'''
P04: GET /healthz on the Cloud app.

Proves the Cloud HTTP process is alive (always 200) and that PostgreSQL/Redis reachability is
reported as informational fields without ever failing the endpoint -- a transient dependency
outage must not look like the process itself is down (see health_handlers.py's docstring for
why: that would fail the Kubernetes liveness probe and cause a restart loop that cannot fix an
external dependency being down).
'''
from unittest import TestCase
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import app as cloud_app


class TestCloudHealthz(TestCase):
    def setUp(self) -> None:
        self.client = TestClient(cloud_app.app)

    def test_healthz_ok_when_postgres_and_redis_reachable(self) -> None:
        mock_session = MagicMock()
        mock_db_config = MagicMock()
        mock_db_config.get_db_session.return_value = mock_session

        with patch("src.cloud.health_handlers.DB_CONFIG", mock_db_config), \
             patch("src.cloud.health_handlers.redis.Redis") as mock_redis_cls:
            mock_redis_cls.return_value.ping.return_value = True

            response = self.client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {"status": "ok", "postgres": "ok", "redis": "ok"}
        )
        mock_session.execute.assert_called_once()
        mock_session.close.assert_called_once()

    def test_healthz_still_200_when_postgres_unreachable(self) -> None:
        mock_db_config = MagicMock()
        mock_db_config.get_db_session.side_effect = Exception("connection refused")

        with patch("src.cloud.health_handlers.DB_CONFIG", mock_db_config), \
             patch("src.cloud.health_handlers.redis.Redis") as mock_redis_cls:
            mock_redis_cls.return_value.ping.return_value = True

            response = self.client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["postgres"], "unreachable")
        self.assertEqual(body["redis"], "ok")

    def test_healthz_still_200_when_redis_unreachable(self) -> None:
        mock_session = MagicMock()
        mock_db_config = MagicMock()
        mock_db_config.get_db_session.return_value = mock_session

        with patch("src.cloud.health_handlers.DB_CONFIG", mock_db_config), \
             patch("src.cloud.health_handlers.redis.Redis") as mock_redis_cls:
            mock_redis_cls.return_value.ping.side_effect = Exception("connection refused")

            response = self.client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["postgres"], "ok")
        self.assertEqual(body["redis"], "unreachable")

    def test_healthz_error_details_not_leaked_in_response(self) -> None:
        '''The raw exception text (which could include connection/DSN details) must never reach
        the HTTP response body -- only the generic "unreachable" status.'''
        mock_db_config = MagicMock()
        mock_db_config.get_db_session.side_effect = Exception(
            "secret-looking-connection-detail"
        )

        with patch("src.cloud.health_handlers.DB_CONFIG", mock_db_config), \
             patch("src.cloud.health_handlers.redis.Redis") as mock_redis_cls:
            mock_redis_cls.return_value.ping.return_value = True

            response = self.client.get("/healthz")

        self.assertNotIn("secret-looking-connection-detail", response.text)
