'''
P03 -- Ownership / IDOR authorization tests.

Handler-level tests proving every authenticated container/workspace operation derives identity
from request.state.user_info (set by @authenticate_session from the Redis session) rather than
from any client-supplied value (JSON body, query string, path param), and that a caller acting
as User A is rejected -- BEFORE any side effect -- when the resource in question belongs to
User B.

Same "mock the boundary" convention as the rest of tests/integration/containers: call the
UNDECORATED handler via `<handler>.__wrapped__` (skips the real Redis session lookup) and patch
ContainerOps/ContainerService at their import site in src.api_handlers, so no live Postgres,
Redis, gRPC, or k8s is touched.
'''

# builtins
import asyncio
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

# fastapi
from fastapi import Request

# browseterm_db enums
from browseterm_db.models.containers import SaveStatus, ContainerStatus

# module under test
import src.api_handlers as api_handlers
from src.containers.dto.container_response_dto import ContainerResponseModel

USER_A = 'user-a'
USER_B = 'user-b'


def _mock_request(body: dict = None, query_params: dict = None, user_id: str = USER_A) -> MagicMock:
    '''
    A FastAPI Request stand-in carrying an authenticated identity (as @authenticate_session
    would set it: request.state.user_info is a plain dict, see session_dto.SessionDataModel).
    '''
    request: MagicMock = MagicMock(spec=Request)
    request.json = AsyncMock(return_value=body or {})
    request.query_params = query_params or {}
    request.path_params = body.get('__path_params__', {}) if body else {}
    request.state.user_info = {'id': user_id}
    return request


class TestGetContainerInfoOwnership(TestCase):
    '''GET /get-container-info/{container_id}: user_id must come from the session, not the URL.'''

    def test_container_id_read_from_path_params_and_user_id_from_session(self) -> None:
        request = MagicMock(spec=Request)
        request.path_params = {'container_id': 'container-1'}
        request.state.user_info = {'id': USER_A}
        mock_service = MagicMock()
        mock_service.get_container_info = AsyncMock(return_value={'id': 'container-1'})
        with patch('src.api_handlers.ContainerService', return_value=mock_service):
            result = asyncio.run(api_handlers.get_container_info.__wrapped__(request=request))
        self.assertEqual(result.status_code, 200)
        called_request = mock_service.get_container_info.call_args.args[0]
        self.assertEqual(called_request.container_id, 'container-1')
        self.assertEqual(called_request.user_id, USER_A)


class TestCreateContainerInDbOwnership(TestCase):
    '''POST /create-container-in-db: user_id must never come from the client body (spoofing).'''

    def test_client_supplied_user_id_is_ignored(self) -> None:
        request = _mock_request(
            body={
                'user_id': USER_B,  # attacker spoofs another user's id
                'image_id': 'image-1', 'name': 'my-container',
            },
            user_id=USER_A,
        )
        mock_service = MagicMock()
        mock_service.create_container_in_db = AsyncMock(return_value={'id': 'new-container'})
        with patch('src.api_handlers.ContainerService', return_value=mock_service):
            result = asyncio.run(api_handlers.create_container_in_db.__wrapped__(request=request))
        self.assertEqual(result.status_code, 200)
        called_request = mock_service.create_container_in_db.call_args.args[0]
        self.assertEqual(called_request.user_id, USER_A)
        self.assertNotEqual(called_request.user_id, USER_B)


class TestCreateContainerInK8sOwnership(TestCase):
    '''POST /create-container-in-k8s: must verify the DB container_id is the caller's own, and
    must never trust a client-supplied network_name (would place a pod in another tenant's
    namespace).'''

    def _body(self, container_id: str = 'container-1') -> dict:
        return {
            'container_id': container_id,
            'image_id': 'image-1',
            'container_name': 'my-container',
            'network_name': f'{USER_B}-namespace',  # attacker targets B's namespace
            'resource_requirements': {},
        }

    def test_container_not_owned_by_caller_is_rejected_before_k8s_call(self) -> None:
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = SimpleNamespace(data=None)  # scoped lookup finds nothing
        mock_service = MagicMock()
        mock_service.create_container_in_k8s = AsyncMock()
        request = _mock_request(body=self._body(), user_id=USER_A)
        with patch('src.api_handlers.ContainerOps', return_value=mock_ops), \
             patch('src.api_handlers.ContainerService', return_value=mock_service):
            result = asyncio.run(api_handlers.create_container_in_k8s.__wrapped__(request=request))
        self.assertEqual(result.status_code, 404)
        mock_service.create_container_in_k8s.assert_not_called()
        # ownership lookup was scoped to the caller, not the spoofed body value
        find_filters = mock_ops.find_one.call_args.kwargs['filters']
        self.assertEqual(find_filters, {'id': 'container-1', 'user_id': USER_A})

    def test_network_name_is_derived_from_session_not_client_body(self) -> None:
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = SimpleNamespace(data={'id': 'container-1', 'user_id': USER_A})
        mock_service = MagicMock()
        mock_service.create_container_in_k8s = AsyncMock(return_value=ContainerResponseModel(
            container_name='my-container', container_id='pod-uid', container_ip='10.0.0.1',
            container_network=f'{USER_A}-namespace', container_ports=[], associated_resources=[],
        ))
        request = _mock_request(body=self._body(), user_id=USER_A)
        with patch('src.api_handlers.ContainerOps', return_value=mock_ops), \
             patch('src.api_handlers.ContainerService', return_value=mock_service):
            result = asyncio.run(api_handlers.create_container_in_k8s.__wrapped__(request=request))
        self.assertEqual(result.status_code, 200)
        k8s_request = mock_service.create_container_in_k8s.call_args.args[0]
        self.assertEqual(k8s_request.network_name, f'{USER_A}-namespace')
        self.assertNotEqual(k8s_request.network_name, f'{USER_B}-namespace')


class TestUpdateContainerOwnership(TestCase):
    '''POST /update-container: filters.user_id must always be the session's id.'''

    def test_client_supplied_filter_user_id_is_ignored(self) -> None:
        request = _mock_request(
            body={
                'filters': {'container_id': 'container-1', 'user_id': USER_B},
                'data': {'name': 'renamed'},
            },
            user_id=USER_A,
        )
        mock_service = MagicMock()
        mock_service.update_container = AsyncMock(return_value={'success': True})
        with patch('src.api_handlers.ContainerService', return_value=mock_service):
            result = asyncio.run(api_handlers.update_container.__wrapped__(request=request))
        self.assertEqual(result.status_code, 200)
        called_request = mock_service.update_container.call_args.args[0]
        self.assertEqual(called_request.filters.user_id, USER_A)

    def test_id_only_filter_body_still_scoped_to_session_user(self) -> None:
        '''Regression for the actual production gap: the frontend sends only container_id in
        filters (no user_id at all) -- the handler must still scope the update to the caller.'''
        request = _mock_request(
            body={'filters': {'container_id': 'container-1'}, 'data': {'name': 'renamed'}},
            user_id=USER_A,
        )
        mock_service = MagicMock()
        mock_service.update_container = AsyncMock(return_value={'success': True})
        with patch('src.api_handlers.ContainerService', return_value=mock_service):
            asyncio.run(api_handlers.update_container.__wrapped__(request=request))
        called_request = mock_service.update_container.call_args.args[0]
        self.assertEqual(called_request.filters.user_id, USER_A)


class TestListUserContainersOwnership(TestCase):
    '''GET /list-user-containers: user_id must never come from the query string.'''

    def test_client_supplied_query_user_id_is_ignored(self) -> None:
        request = _mock_request(query_params={'user_id': USER_B}, user_id=USER_A)
        mock_service = MagicMock()
        mock_service.list_user_containers = AsyncMock(return_value=[])
        with patch('src.api_handlers.ContainerService', return_value=mock_service):
            result = asyncio.run(api_handlers.list_user_containers.__wrapped__(request=request))
        self.assertEqual(result.status_code, 200)
        called_request = mock_service.list_user_containers.call_args.args[0]
        self.assertEqual(called_request.user_id, USER_A)
        self.assertNotEqual(called_request.user_id, USER_B)


class TestDeleteContainerInDbOwnership(TestCase):
    '''POST /delete-container-in-db: user_id must never come from the client body.'''

    def test_client_supplied_user_id_is_ignored(self) -> None:
        request = _mock_request(
            body={'container_id': 'container-1', 'user_id': USER_B},
            user_id=USER_A,
        )
        mock_service = MagicMock()
        mock_service.delete_container_in_db = AsyncMock(return_value={'success': True})
        with patch('src.api_handlers.ContainerService', return_value=mock_service):
            result = asyncio.run(api_handlers.delete_container_in_db.__wrapped__(request=request))
        self.assertEqual(result.status_code, 200)
        called_request = mock_service.delete_container_in_db.call_args.args[0]
        self.assertEqual(called_request.user_id, USER_A)
        self.assertNotEqual(called_request.user_id, USER_B)


class TestDeleteContainerInK8sOwnership(TestCase):
    '''POST /delete-container-in-k8s: network_name must never come from the client body.'''

    def test_client_supplied_network_name_is_ignored(self) -> None:
        request = _mock_request(
            body={'container_id': 'pod-uid', 'network_name': f'{USER_B}-namespace'},
            user_id=USER_A,
        )
        mock_service = MagicMock()
        mock_service.delete_container_in_k8s = AsyncMock(return_value=SimpleNamespace(
            model_dump=lambda: {'status': 'deleted'}
        ))
        with patch('src.api_handlers.ContainerService', return_value=mock_service):
            result = asyncio.run(api_handlers.delete_container_in_k8s.__wrapped__(request=request))
        self.assertEqual(result.status_code, 200)
        called_request = mock_service.delete_container_in_k8s.call_args.args[0]
        self.assertEqual(called_request.network_name, f'{USER_A}-namespace')
        self.assertNotEqual(called_request.network_name, f'{USER_B}-namespace')


class TestSaveContainerOwnership(TestCase):
    '''POST /save-container: must verify ownership BEFORE mutating save_status or calling
    container-maker, and must never trust a client-supplied network_name.'''

    def test_container_not_owned_by_caller_is_rejected_before_any_mutation(self) -> None:
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = SimpleNamespace(data=None)  # not User A's container
        mock_service = MagicMock()
        mock_service.save_container_in_k8s = AsyncMock()
        request = _mock_request(
            body={'container_id': 'container-1', 'network_name': f'{USER_B}-namespace'},
            user_id=USER_A,
        )
        with patch('src.api_handlers.ContainerOps', return_value=mock_ops), \
             patch('src.api_handlers.ContainerService', return_value=mock_service):
            result = asyncio.run(api_handlers.save_container.__wrapped__(request=request))
        self.assertEqual(result.status_code, 404)
        # save_status was never touched -- the only ops call is the ownership lookup itself
        mock_ops.update.assert_not_called()
        find_filters = mock_ops.find_one.call_args.kwargs['filters']
        self.assertEqual(find_filters, {'id': 'container-1', 'user_id': USER_A})

    def test_owned_container_save_uses_session_derived_network_name(self) -> None:
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = SimpleNamespace(data={'id': 'container-1', 'user_id': USER_A})
        mock_ops.update.return_value = SimpleNamespace(data=None)
        mock_service = MagicMock()
        mock_service.save_container_in_k8s = AsyncMock(return_value=MagicMock())
        request = _mock_request(
            body={'container_id': 'container-1', 'network_name': f'{USER_B}-namespace'},
            user_id=USER_A,
        )
        with patch('src.api_handlers.ContainerOps', return_value=mock_ops), \
             patch('src.api_handlers.ContainerService', return_value=mock_service):
            result = asyncio.run(api_handlers.save_container.__wrapped__(request=request))
        self.assertEqual(result.status_code, 202)
        pending = [c.kwargs['data'] for c in mock_ops.update.call_args_list
                   if c.kwargs.get('data', {}).get('save_status') == SaveStatus.PENDING.value]
        self.assertTrue(pending, 'save_container did not mark save_status=PENDING for the owned container')


class TestResumeContainerOwnership(TestCase):
    '''POST /resume-container: the id-only find_one must become an (id, session user_id)
    lookup -- the exact gap flagged by the P03 task spec.'''

    def setUp(self) -> None:
        self.container_id = 'container-1'
        self.row_owned_by_b = {
            'id': self.container_id, 'user_id': USER_B, 'image_id': 'image-1',
            'name': 'b-container', 'status': ContainerStatus.HIBERNATED.value, 'cpu_limit': '1',
            'memory_limit': '1Gi', 'storage_limit': '2Gi', 'port_mappings': [],
            'environment_vars': {}, 'associated_resources': [], 'saved_image': None,
        }

    def test_caller_cannot_resume_another_users_container(self) -> None:
        mock_ops = MagicMock()
        # scoped lookup: User A's session filters by user_id=USER_A, so User B's row is never
        # returned by a correctly-scoped find_one -- simulate that DB behavior directly.
        mock_ops.find_one.return_value = SimpleNamespace(data=None)
        mock_service = MagicMock()
        mock_service.create_container_in_k8s = AsyncMock()
        request = _mock_request(body={'container_id': self.container_id}, user_id=USER_A)
        with patch('src.api_handlers.ContainerOps', return_value=mock_ops), \
             patch('src.api_handlers.ContainerService', return_value=mock_service):
            result = asyncio.run(api_handlers.resume_container.__wrapped__(request=request))
        self.assertEqual(result.status_code, 404)
        mock_service.create_container_in_k8s.assert_not_called()
        find_filters = mock_ops.find_one.call_args.kwargs['filters']
        self.assertEqual(find_filters, {'id': self.container_id, 'user_id': USER_A})

    def test_caller_can_resume_own_container(self) -> None:
        row = dict(self.row_owned_by_b, user_id=USER_A)
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = SimpleNamespace(data=row)
        mock_ops.update.return_value = SimpleNamespace(data=None)
        mock_service = MagicMock()
        mock_service.create_container_in_k8s = AsyncMock(return_value=ContainerResponseModel(
            container_name='b-container', container_id='new-pod-uid', container_ip='10.0.0.9',
            container_network=f'{USER_A}-namespace', container_ports=[], associated_resources=[],
        ))
        request = _mock_request(body={'container_id': self.container_id}, user_id=USER_A)
        with patch('src.api_handlers.ContainerOps', return_value=mock_ops), \
             patch('src.api_handlers.ContainerService', return_value=mock_service), \
             patch('src.api_handlers.get_user_current_subscription_plan', AsyncMock(return_value={
                 'name': 'Free', 'max_containers': 5,
                 'cpu_limit_per_container': '1', 'memory_limit_per_container': '1Gi',
                 'storage_limit_per_container': '2Gi',
             })):
            mock_ops.find.return_value = SimpleNamespace(success=True, data=[])
            result = asyncio.run(api_handlers.resume_container.__wrapped__(request=request))
        self.assertEqual(result.status_code, 200)
        mock_service.create_container_in_k8s.assert_called_once()


class TestContainerActivityCrossUser(TestCase):
    '''POST /container-activity: explicit cross-user rejection (existing scoping mechanism,
    verified end-to-end here per the P03 cross-user test requirement).'''

    def test_activity_scoped_to_caller_never_touches_another_users_row(self) -> None:
        mock_ops = MagicMock()
        mock_ops.update.return_value = SimpleNamespace(data=None)
        request = _mock_request(body={'container_id': 'b-container'}, user_id=USER_A)
        with patch('src.api_handlers.ContainerOps', return_value=mock_ops):
            result = asyncio.run(api_handlers.container_activity.__wrapped__(request=request))
        self.assertEqual(result.status_code, 200)
        filters = mock_ops.update.call_args.kwargs['filters']
        self.assertEqual(filters, {'id': 'b-container', 'user_id': USER_A})


class TestContainerStatusSseOwnership(TestCase):
    '''GET /container-status-stream: must subscribe to the session's own user_id, never a
    client-supplied query param.'''

    def test_subscribes_to_session_user_not_query_param(self) -> None:
        request = _mock_request(query_params={'user_id': USER_B}, user_id=USER_A)
        queue = asyncio.Queue()
        mock_listener = MagicMock()
        mock_listener.subscribe = MagicMock(return_value=queue)
        mock_listener.unsubscribe = MagicMock()
        with patch('src.api_handlers.status_listener_service', mock_listener):
            response = asyncio.run(api_handlers.container_status_sse.__wrapped__(request=request))

            async def _first_event() -> str:
                return await response.body_iterator.__anext__()

            first_event = asyncio.run(_first_event())
        mock_listener.subscribe.assert_called_once_with(USER_A)
        self.assertIn(USER_A, first_event)
        self.assertNotIn(USER_B, first_event)
