from unittest import TestCase
from fastapi import Response
from fastapi.testclient import TestClient
from app import app


class TestEcho(TestCase):
    def setUp(self) -> None:
        self.client: TestClient = TestClient(app)

    def test_echo(self) -> None:
        test_data: dict = {
            'message': 'Hello, World!'
        }
        response: Response = self.client.post('/echo', json=test_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), test_data)
