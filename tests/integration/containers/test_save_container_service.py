# builtins
import asyncio
from unittest import TestCase
from unittest.mock import MagicMock

# grpc types
from container_maker_spec.types_pb2 import SaveContainerRequest as GRPCSaveContainerRequest

# module under test
from src.containers.containers_service import ContainerService
from src.data_models.containers import SaveContainerK8SRequest

# exceptions
from src.common.exceptions import ContainerMakerException

# fastapi
from fastapi import HTTPException


class TestSaveContainerInK8S(TestCase):
    '''
    Unit tests for ContainerService.save_container_in_k8s.

    We bypass ContainerService.__init__ (which reads certs from Kubernetes secrets
    and opens a gRPC channel) and inject a mocked stub, mirroring how the delete/create
    stub calls are exercised elsewhere. No live cluster or gRPC server is contacted.
    '''
    def setUp(self) -> None:
        # Build the service without running __init__ (no k8s secrets / gRPC channel).
        self.container_service: ContainerService = ContainerService.__new__(ContainerService)
        self.mock_stub: MagicMock = MagicMock()
        self.container_service.stub = self.mock_stub

        self.save_request: SaveContainerK8SRequest = SaveContainerK8SRequest(
            container_id='container-123',
            network_name='test-network'
        )

    def test_save_container_builds_request_and_returns_response(self) -> None:
        '''
        save_container_in_k8s should build a GRPCSaveContainerRequest with the right
        container_id/network_name, call the stub's saveContainer once, and return
        the stub response unchanged.
        '''
        expected_response = GRPCSaveContainerRequest(
            container_id='container-123',
            network_name='test-network'
        )
        self.mock_stub.saveContainer.return_value = expected_response

        result = asyncio.run(self.container_service.save_container_in_k8s(self.save_request))

        # stub called exactly once
        self.mock_stub.saveContainer.assert_called_once()

        # the request handed to the stub carries the correct values
        called_request = self.mock_stub.saveContainer.call_args.args[0]
        self.assertIsInstance(called_request, GRPCSaveContainerRequest)
        self.assertEqual(called_request.container_id, 'container-123')
        self.assertEqual(called_request.network_name, 'test-network')

        # the stub response is returned unchanged
        self.assertEqual(result, expected_response)

    def test_save_container_wraps_container_maker_exception(self) -> None:
        '''
        A ContainerMakerException from the stub should be wrapped in a 500 HTTPException.
        '''
        self.mock_stub.saveContainer.side_effect = ContainerMakerException('boom')

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(self.container_service.save_container_in_k8s(self.save_request))
        self.assertEqual(ctx.exception.status_code, 500)
        self.assertIn('ContainerMaker', ctx.exception.detail)

    def test_save_container_wraps_generic_exception(self) -> None:
        '''
        Any other error from the stub should also become a 500 HTTPException.
        '''
        self.mock_stub.saveContainer.side_effect = RuntimeError('unexpected')

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(self.container_service.save_container_in_k8s(self.save_request))
        self.assertEqual(ctx.exception.status_code, 500)
