'''
End to end tests send actual api input and compare the response with the expected response.
'''

from unittest import TestCase
from fastapi import Response
from fastapi.testclient import TestClient
from app import app


class TestEcho(TestCase):
    '''
    End to end test for echo endpoint.
    '''
    def setUp(self) -> None:
        '''
        Setup the API test client.
        '''
        self.client: TestClient = TestClient(app)

    def test_echo(self) -> None:
        '''
        Test the echo endpoint.
        '''
        test_message: str = "Hello, World!"
        response: Response = self.client.post("/echo", json={"message": test_message})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": test_message})
