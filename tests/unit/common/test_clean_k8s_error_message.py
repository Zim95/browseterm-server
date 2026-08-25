# builtins
from unittest import TestCase

# module under test
from src.common.utils import clean_k8s_error_message


class TestCleanK8sErrorMessage(TestCase):
    '''
    Unit tests for clean_k8s_error_message.

    Guards against ever showing a user the raw Kubernetes ApiException/gRPC exception
    text (nested "Reason: None", HTTPHeaderDict dumps, embedded JSON) that used to leak
    straight through to the frontend on failures like a quota-exceeded resume/create.
    '''

    def test_extracts_quota_message_from_embedded_json(self) -> None:
        raw = (
            '(403)\nReason: Forbidden\n'
            'HTTP response headers: HTTPHeaderDict({\'Content-Type\': \'application/json\'})\n'
            'HTTP response body: {"kind":"Status","message":'
            '"pods \\"foo\\" is forbidden: exceeded quota: browseterm-quota","code":403}\n'
        )
        result = clean_k8s_error_message(raw, fallback='fallback text')
        self.assertNotIn('HTTPHeaderDict', result)
        self.assertNotIn('Reason: Forbidden', result)
        self.assertIn('resource limit', result)

    def test_extracts_non_quota_message_from_embedded_json(self) -> None:
        raw = 'HTTP response body: {"kind":"Status","message":"namespace not found","code":404}'
        result = clean_k8s_error_message(raw, fallback='fallback text')
        self.assertEqual(result, 'namespace not found')

    def test_matches_quota_phrase_without_json(self) -> None:
        raw = 'container creation failed: exceeded quota on namespace'
        result = clean_k8s_error_message(raw, fallback='fallback text')
        self.assertIn('resource limit', result)

    def test_falls_back_when_nothing_recognized(self) -> None:
        raw = 'some totally unrelated internal error'
        result = clean_k8s_error_message(raw, fallback='fallback text')
        self.assertEqual(result, 'fallback text')

    def test_falls_back_on_malformed_json(self) -> None:
        raw = 'HTTP response body: {not: valid json}'
        result = clean_k8s_error_message(raw, fallback='fallback text')
        self.assertEqual(result, 'fallback text')
