# builtins
import asyncio
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

# fastapi
from fastapi import Request

# browseterm_db enums (RESUMING/RUNNING/HIBERNATED must exist in the installed browseterm_db)
from browseterm_db.models.containers import ContainerStatus, SaveStatus

# module under test (imports cleanly off-cluster: CertificateUtils now inits its k8s clients lazily)
import src.api_handlers as api_handlers

# dto used to build a realistic ContainerService response
from src.containers.dto.container_response_dto import ContainerResponseModel


def _mock_request(body: dict) -> MagicMock:
    '''
    A FastAPI Request stand-in whose .json() coroutine returns `body`, mirroring how
    api_handlers reads request data (await request.json()).
    '''
    request: MagicMock = MagicMock(spec=Request)
    request.json = AsyncMock(return_value=body)
    return request


class TestResumeContainer(TestCase):
    '''
    Handler-level tests for api_handlers.resume_container.

    We call the UNDECORATED handler via resume_container.__wrapped__ (the
    @authenticate_session decorator uses functools.wraps) so no Redis session is needed,
    and patch ContainerOps + ContainerService at their import site in src.api_handlers so
    no live Postgres or gRPC/k8s is touched (the repo's "mock the boundary" convention).
    '''

    def setUp(self) -> None:
        self.container_id: str = 'container-123'
        self.saved_image: str = 'registry/my-container:snap'

        # Stored DB row for a HIBERNATED container that WAS saved.
        self.row: dict = {
            'id': self.container_id,
            'user_id': 'user-42',
            'image_id': 'image-1',
            'name': 'my-container',
            'status': ContainerStatus.HIBERNATED.value,
            'cpu_limit': '1',
            'memory_limit': '1Gi',
            'storage_limit': '2Gi',
            'ip_address': '10.0.0.5',              # OLD (stale) ClusterIP
            'port_mappings': [{'publish_port': 2222, 'target_port': 22, 'protocol': 'TCP'}],
            'environment_vars': {'FOO': 'bar'},
            'associated_resources': [{'kind': 'Service', 'name': 'old-svc'}],
            'kubernetes_id': 'old-pod-uid',
            'saved_image': self.saved_image,
            'save_status': SaveStatus.SUCCEEDED.value,
        }

        # create_container_in_k8s response: NEW pod identity + NEW ip.
        self.response: ContainerResponseModel = ContainerResponseModel(
            container_name='my-container',
            container_id='new-pod-uid',
            container_ip='10.0.0.99',              # NEW ClusterIP
            container_network='user-42-namespace',
            container_ports=[],
            associated_resources=[{'kind': 'Service', 'name': 'new-svc'}],
        )

    def _run_resume(self, body: dict):
        mock_ops: MagicMock = MagicMock()
        mock_ops.find_one.return_value = SimpleNamespace(data=self.row)
        mock_ops.update.return_value = SimpleNamespace(data=None)

        mock_service: MagicMock = MagicMock()
        mock_service.create_container_in_k8s = AsyncMock(return_value=self.response)

        with patch('src.api_handlers.ContainerOps', return_value=mock_ops), \
             patch('src.api_handlers.ContainerService', return_value=mock_service):
            result = asyncio.run(
                api_handlers.resume_container.__wrapped__(request=_mock_request(body))
            )
        return result, mock_ops, mock_service

    def _final_update_data(self, mock_ops: MagicMock) -> dict:
        '''The data dict of the ops.update call that set status=RUNNING (the final sync).'''
        for call in mock_ops.update.call_args_list:
            data = call.kwargs.get('data', {})
            if data.get('status') == ContainerStatus.RUNNING:
                return data
        raise AssertionError('resume_container never issued the final RUNNING update')

    def test_resume_recreates_pod_from_saved_image(self) -> None:
        '''A HIBERNATED container with a saved_image is recreated FROM that snapshot.'''
        result, _ops, mock_service = self._run_resume({'container_id': self.container_id})
        self.assertEqual(result.status_code, 200)
        mock_service.create_container_in_k8s.assert_called_once()
        self.assertEqual(
            mock_service.create_container_in_k8s.call_args.kwargs['image_name_override'],
            self.saved_image,
        )

    def test_resume_updates_ip_address_and_kubernetes_id(self) -> None:
        '''
        Regression: resume creates a brand-new Service (new ClusterIP), so the row MUST get
        the NEW ip_address + kubernetes_id and status RUNNING. The bug was ip_address not
        being updated, leaving the terminal dialing the deleted pod's IP (SSH handshake timeout).
        '''
        _result, mock_ops, _service = self._run_resume({'container_id': self.container_id})
        data = self._final_update_data(mock_ops)
        self.assertEqual(data['ip_address'], self.response.container_ip)   # 10.0.0.99, not 10.0.0.5
        self.assertNotEqual(data['ip_address'], self.row['ip_address'])
        self.assertEqual(data['kubernetes_id'], self.response.container_id)
        self.assertEqual(data['associated_resources'], self.response.associated_resources)
        self.assertEqual(data['status'], ContainerStatus.RUNNING)

    def test_resume_marks_resuming_before_recreate(self) -> None:
        '''The row flips to RESUMING before the (slow) recreate so the UI can show progress.'''
        _result, mock_ops, _service = self._run_resume({'container_id': self.container_id})
        statuses = [c.kwargs.get('data', {}).get('status') for c in mock_ops.update.call_args_list]
        self.assertIn(ContainerStatus.RESUMING, statuses)
        self.assertLess(statuses.index(ContainerStatus.RESUMING),
                        statuses.index(ContainerStatus.RUNNING))

    def test_resume_missing_container_returns_404(self) -> None:
        '''No row -> 404, and k8s is never touched.'''
        mock_ops: MagicMock = MagicMock()
        mock_ops.find_one.return_value = SimpleNamespace(data=None)
        mock_service: MagicMock = MagicMock()
        mock_service.create_container_in_k8s = AsyncMock()
        with patch('src.api_handlers.ContainerOps', return_value=mock_ops), \
             patch('src.api_handlers.ContainerService', return_value=mock_service):
            result = asyncio.run(
                api_handlers.resume_container.__wrapped__(request=_mock_request({'container_id': 'nope'}))
            )
        self.assertEqual(result.status_code, 404)
        mock_service.create_container_in_k8s.assert_not_called()

    def test_resume_after_crash_still_resumes_from_saved_image(self) -> None:
        '''
        save -> crash -> resume (server-testable slice): even if the pod died unexpectedly
        (row left non-RUNNING, e.g. UNKNOWN), resume takes the SAME path as hibernate-resume:
        recreate from saved_image, write the new identity + ip, RUNNING. Crash detection itself
        is kubelet-driven and lives in container-maker, not here.
        '''
        self.row['status'] = ContainerStatus.UNKNOWN.value
        result, mock_ops, mock_service = self._run_resume({'container_id': self.container_id})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            mock_service.create_container_in_k8s.call_args.kwargs['image_name_override'],
            self.saved_image,
        )
        self.assertEqual(self._final_update_data(mock_ops)['status'], ContainerStatus.RUNNING)


class TestCountActiveContainers(TestCase):
    '''
    Unit tests for api_handlers._count_active_containers -- what actually counts against a
    plan's max_containers limit.
    '''

    def _rows(self, statuses_and_ids, deleted_ids=frozenset()):
        return [
            {'id': cid, 'status': status, 'deleted_at': ('x' if cid in deleted_ids else None)}
            for cid, status in statuses_and_ids
        ]

    def test_counts_running_pending_resuming_only(self) -> None:
        mock_ops = MagicMock()
        mock_ops.find.return_value = SimpleNamespace(success=True, data=self._rows([
            ('a', ContainerStatus.RUNNING.value),
            ('b', ContainerStatus.PENDING.value),
            ('c', ContainerStatus.RESUMING.value),
            ('d', ContainerStatus.HIBERNATED.value),
            ('e', ContainerStatus.FAILED.value),
        ]))
        count = asyncio.run(api_handlers._count_active_containers(mock_ops, 'user-42', exclude_container_id='none'))
        self.assertEqual(count, 3)

    def test_excludes_the_container_being_resumed(self) -> None:
        mock_ops = MagicMock()
        mock_ops.find.return_value = SimpleNamespace(success=True, data=self._rows([
            ('target', ContainerStatus.RUNNING.value),
            ('other', ContainerStatus.RUNNING.value),
        ]))
        count = asyncio.run(api_handlers._count_active_containers(mock_ops, 'user-42', exclude_container_id='target'))
        self.assertEqual(count, 1)

    def test_excludes_soft_deleted_rows(self) -> None:
        mock_ops = MagicMock()
        mock_ops.find.return_value = SimpleNamespace(success=True, data=self._rows(
            [('a', ContainerStatus.RUNNING.value), ('b', ContainerStatus.RUNNING.value)],
            deleted_ids={'b'},
        ))
        count = asyncio.run(api_handlers._count_active_containers(mock_ops, 'user-42', exclude_container_id='none'))
        self.assertEqual(count, 1)

    def test_raises_on_db_error(self) -> None:
        mock_ops = MagicMock()
        mock_ops.find.return_value = SimpleNamespace(success=False, error='db down', data=None)
        with self.assertRaises(Exception):
            asyncio.run(api_handlers._count_active_containers(mock_ops, 'user-42', exclude_container_id='none'))


class TestExceedsTierSpec(TestCase):
    '''Unit tests for api_handlers._exceeds_tier_spec -- pure comparison, no mocking needed.'''

    def _tier(self, cpu='1', memory='1Gi', storage='2Gi'):
        return {
            'cpu_limit_per_container': cpu,
            'memory_limit_per_container': memory,
            'storage_limit_per_container': storage,
        }

    def _container(self, cpu='1', memory='1Gi', storage='2Gi'):
        return {'cpu_limit': cpu, 'memory_limit': memory, 'storage_limit': storage}

    def test_within_limits_is_allowed(self) -> None:
        self.assertFalse(api_handlers._exceeds_tier_spec(self._container(), self._tier()))

    def test_cpu_over_limit_is_blocked(self) -> None:
        self.assertTrue(api_handlers._exceeds_tier_spec(self._container(cpu='2'), self._tier(cpu='1')))

    def test_memory_over_limit_is_blocked(self) -> None:
        self.assertTrue(api_handlers._exceeds_tier_spec(self._container(memory='4Gi'), self._tier(memory='1Gi')))

    def test_storage_over_limit_is_blocked(self) -> None:
        self.assertTrue(api_handlers._exceeds_tier_spec(self._container(storage='10Gi'), self._tier(storage='2Gi')))

    def test_exactly_at_limit_is_allowed(self) -> None:
        self.assertFalse(api_handlers._exceeds_tier_spec(self._container(cpu='1'), self._tier(cpu='1')))

    def test_unparseable_tier_value_fails_open(self) -> None:
        '''The Pro tier's seed data uses the literal string "Configurable" -- must not crash
        or incorrectly block on it, just skip that comparison.'''
        self.assertFalse(api_handlers._exceeds_tier_spec(self._container(cpu='1'), self._tier(cpu='Configurable')))


class TestResumeEntitlementChecks(TestCase):
    '''
    Integration-level tests for the two entitlement gates wired into resume_container itself:
    the plan's concurrent-container limit, and whether the container's own recorded spec still
    fits the current plan. Both must block with 409 (not touch k8s) when violated, and must not
    interfere with a normal resume when the plan permits it.
    '''

    def setUp(self) -> None:
        self.container_id: str = 'container-123'
        self.row: dict = {
            'id': self.container_id,
            'user_id': 'user-42',
            'image_id': 'image-1',
            'name': 'my-container',
            'status': ContainerStatus.HIBERNATED.value,
            'cpu_limit': '1',
            'memory_limit': '1Gi',
            'storage_limit': '2Gi',
            'ip_address': '10.0.0.5',
            'port_mappings': [],
            'environment_vars': {},
            'associated_resources': [],
            'kubernetes_id': 'old-pod-uid',
            'saved_image': 'registry/my-container:snap',
            'save_status': SaveStatus.SUCCEEDED.value,
        }
        self.free_plan: dict = {
            'name': 'Free Plan', 'type': 'free', 'max_containers': 1,
            'cpu_limit_per_container': '1', 'memory_limit_per_container': '1Gi',
            'storage_limit_per_container': '2Gi',
        }

    def _run(self, plan: dict, active_rows: list):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = SimpleNamespace(data=self.row)
        mock_ops.update.return_value = SimpleNamespace(data=None)
        mock_ops.find.return_value = SimpleNamespace(success=True, data=active_rows)

        mock_service = MagicMock()
        mock_service.create_container_in_k8s = AsyncMock(return_value=ContainerResponseModel(
            container_name='my-container', container_id='new-pod-uid', container_ip='10.0.0.99',
            container_network='user-42-namespace', container_ports=[], associated_resources=[],
        ))

        with patch('src.api_handlers.ContainerOps', return_value=mock_ops), \
             patch('src.api_handlers.ContainerService', return_value=mock_service), \
             patch('src.api_handlers.get_user_current_subscription_plan', AsyncMock(return_value=plan)):
            result = asyncio.run(
                api_handlers.resume_container.__wrapped__(request=_mock_request({'container_id': self.container_id}))
            )
        return result, mock_ops, mock_service

    def test_blocks_when_over_container_limit(self) -> None:
        '''Free plan, max_containers=1, user already has one Running -> 409, k8s never touched.'''
        active_rows = [{'id': 'other-container', 'status': ContainerStatus.RUNNING.value, 'deleted_at': None}]
        result, _ops, mock_service = self._run(self.free_plan, active_rows)
        self.assertEqual(result.status_code, 409)
        self.assertIn('Free Plan', result.body.decode())
        mock_service.create_container_in_k8s.assert_not_called()

    def test_blocks_when_spec_exceeds_current_plan(self) -> None:
        '''Container recorded 2 CPU (e.g. saved under a higher tier), current plan only allows 1.'''
        self.row['cpu_limit'] = '2'
        result, _ops, mock_service = self._run(self.free_plan, active_rows=[])
        self.assertEqual(result.status_code, 409)
        self.assertIn('ineligible', result.body.decode())
        mock_service.create_container_in_k8s.assert_not_called()

    def test_allows_resume_within_plan_limits(self) -> None:
        '''No other active containers, spec fits -- resume proceeds exactly as before.'''
        result, _ops, mock_service = self._run(self.free_plan, active_rows=[])
        self.assertEqual(result.status_code, 200)
        mock_service.create_container_in_k8s.assert_called_once()

    def test_resumed_container_itself_not_counted_against_its_own_limit(self) -> None:
        '''The row being resumed is HIBERNATED, but even if find() somehow still returned it,
        it must be excluded from its own limit check by id.'''
        active_rows = [{'id': self.container_id, 'status': ContainerStatus.HIBERNATED.value, 'deleted_at': None}]
        result, _ops, mock_service = self._run(self.free_plan, active_rows)
        self.assertEqual(result.status_code, 200)
        mock_service.create_container_in_k8s.assert_called_once()


class TestSaveContainerHandler(TestCase):
    '''
    Handler-level tests for api_handlers.save_container (the server-testable half of
    save -> crash -> resume): the handler marks save_status=PENDING immediately and fires the
    blocking gRPC save in the background; a gRPC failure records save_status=FAILED.
    '''

    def setUp(self) -> None:
        self.container_id: str = 'container-123'

    def test_save_marks_pending_and_returns_202(self) -> None:
        mock_ops: MagicMock = MagicMock()
        mock_ops.update.return_value = SimpleNamespace(data=None)
        mock_service: MagicMock = MagicMock()
        mock_service.save_container_in_k8s = AsyncMock(return_value=MagicMock())
        with patch('src.api_handlers.ContainerOps', return_value=mock_ops), \
             patch('src.api_handlers.ContainerService', return_value=mock_service):
            result = asyncio.run(
                api_handlers.save_container.__wrapped__(
                    request=_mock_request(
                        {'container_id': self.container_id, 'network_name': 'user-42-namespace'}
                    )
                )
            )
        self.assertEqual(result.status_code, 202)
        pending = [c.kwargs['data'] for c in mock_ops.update.call_args_list
                   if c.kwargs.get('data', {}).get('save_status') == SaveStatus.PENDING.value]
        self.assertTrue(pending, 'save_container did not mark save_status=PENDING')
        self.assertIn(
            'last_save_attempted_at', pending[0],
            'save_container must stamp last_save_attempted_at -- this is the one moment a save is initiated',
        )

    def test_run_save_records_failed_on_grpc_error(self) -> None:
        mock_ops: MagicMock = MagicMock()
        mock_ops.update.return_value = SimpleNamespace(data=None)
        mock_service: MagicMock = MagicMock()
        mock_service.save_container_in_k8s = AsyncMock(side_effect=RuntimeError('boom'))
        with patch('src.api_handlers.ContainerOps', return_value=mock_ops):
            asyncio.run(api_handlers._run_save(mock_service, MagicMock(), self.container_id))
        failed = [c.kwargs['data'] for c in mock_ops.update.call_args_list
                  if c.kwargs.get('data', {}).get('save_status') == SaveStatus.FAILED.value]
        self.assertTrue(failed, '_run_save did not record save_status=FAILED')
        self.assertIn('boom', failed[0]['save_error'])
        self.assertNotIn(
            'last_save_attempted_at', failed[0],
            'only the PENDING write (save_container) should stamp last_save_attempted_at, not a later failure',
        )


class TestContainerActivity(TestCase):
    '''
    Handler-level tests for api_handlers.container_activity: it stamps last_active_at scoped to the
    caller's own container (id + user_id), and — via @authenticate_session — refreshes the login
    session (tested there). Uses .__wrapped__ to skip auth and injects request.state.user_info.
    '''

    def _run(self, body: dict, user_id: str = "user-42"):
        req: MagicMock = MagicMock(spec=Request)
        req.json = AsyncMock(return_value=body)
        req.state.user_info = SimpleNamespace(id=user_id)
        mock_ops: MagicMock = MagicMock()
        mock_ops.update.return_value = SimpleNamespace(data=None)
        with patch('src.api_handlers.ContainerOps', return_value=mock_ops):
            result = asyncio.run(api_handlers.container_activity.__wrapped__(request=req))
        return result, mock_ops

    def test_stamps_last_active_at_scoped_to_user(self) -> None:
        result, mock_ops = self._run({'container_id': 'c-1'})
        self.assertEqual(result.status_code, 200)
        mock_ops.update.assert_called_once()
        kwargs = mock_ops.update.call_args.kwargs
        self.assertEqual(kwargs['filters'], {"id": "c-1", "user_id": "user-42"})
        self.assertIn('last_active_at', kwargs['data'])

    def test_missing_container_id_is_400(self) -> None:
        result, mock_ops = self._run({})
        self.assertEqual(result.status_code, 400)
        mock_ops.update.assert_not_called()
