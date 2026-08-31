'''
P07 -- unit tests for the three new Redis-backed auth managers. `redis.Redis` is mocked with an
in-memory dict standing in for the Redis keyspace, so GETDEL/SETEX/GET semantics are exercised for
real (not just "was called with...") without touching a live Redis.
'''
import json
import time
import unittest
from unittest.mock import patch

from src.authentication.oauth_state_manager import OAuthStateManager
from src.authentication.handoff_manager import HandoffManager
from src.authentication.device_token_manager import DeviceTokenManager


class _FakeRedis:
    '''Just enough of the redis.Redis API (setex/get/getdel/delete) for these managers.'''

    def __init__(self):
        self._store: dict = {}

    def setex(self, name, time, value):
        self._store[name] = value

    def get(self, name):
        return self._store.get(name)

    def getdel(self, name):
        return self._store.pop(name, None)

    def delete(self, name):
        self._store.pop(name, None)


class TestOAuthStateManager(unittest.TestCase):
    def setUp(self):
        self.fake_redis = _FakeRedis()
        patcher = patch("src.authentication.oauth_state_manager.redis.Redis", return_value=self.fake_redis)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.manager = OAuthStateManager()

    def test_state_is_random_and_unguessable(self):
        s1 = self.manager.create_state("google", "local")
        s2 = self.manager.create_state("google", "local")
        self.assertNotEqual(s1, s2)
        self.assertGreater(len(s1), 20)

    def test_valid_state_succeeds(self):
        state = self.manager.create_state("google", "local")
        data = self.manager.consume_state(state, "google")
        self.assertIsNotNone(data)
        self.assertEqual(data["target"], "local")

    def test_missing_state_rejected(self):
        self.assertIsNone(self.manager.consume_state("never-issued", "google"))

    def test_wrong_provider_rejected(self):
        '''A state minted for google must not validate against the github callback.'''
        state = self.manager.create_state("google", "local")
        self.assertIsNone(self.manager.consume_state(state, "github"))

    def test_replayed_state_rejected(self):
        state = self.manager.create_state("google", "local")
        first = self.manager.consume_state(state, "google")
        second = self.manager.consume_state(state, "google")
        self.assertIsNotNone(first)
        self.assertIsNone(second)

    def test_corrupt_state_value_rejected_not_raised(self):
        self.fake_redis._store["oauth:state:corrupt"] = "not-json"
        self.assertIsNone(self.manager.consume_state("corrupt", "google"))


class TestHandoffManager(unittest.TestCase):
    def setUp(self):
        self.fake_redis = _FakeRedis()
        patcher = patch("src.authentication.handoff_manager.redis.Redis", return_value=self.fake_redis)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.manager = HandoffManager()

    def test_valid_handoff_redeem_succeeds(self):
        code = self.manager.create_handoff("local_login", "u1", "s1")
        data = self.manager.consume_handoff(code, "local_login")
        self.assertEqual(data["user_id"], "u1")
        self.assertEqual(data["session_id"], "s1")

    def test_second_redemption_fails(self):
        code = self.manager.create_handoff("local_login", "u1", "s1")
        self.assertIsNotNone(self.manager.consume_handoff(code, "local_login"))
        self.assertIsNone(self.manager.consume_handoff(code, "local_login"))

    def test_invalid_code_fails(self):
        self.assertIsNone(self.manager.consume_handoff("never-issued", "local_login"))

    def test_wrong_purpose_handoff_fails(self):
        '''A local_login code must not redeem as a device_bootstrap and vice versa.'''
        code = self.manager.create_handoff("local_login", "u1")
        self.assertIsNone(self.manager.consume_handoff(code, "device_bootstrap"))

    def test_device_bootstrap_purpose_round_trips(self):
        code = self.manager.create_handoff("device_bootstrap", "u1")
        data = self.manager.consume_handoff(code, "device_bootstrap")
        self.assertEqual(data["user_id"], "u1")
        self.assertIsNone(data["session_id"])


class TestDeviceTokenManager(unittest.TestCase):
    def setUp(self):
        self.fake_redis = _FakeRedis()
        patcher = patch("src.authentication.device_token_manager.redis.Redis", return_value=self.fake_redis)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.manager = DeviceTokenManager()

    def test_token_resolves_correct_user_and_device(self):
        token = self.manager.issue_token("u1", "d1", ["device:read"])
        data = self.manager.validate_token(token)
        self.assertEqual(data["user_id"], "u1")
        self.assertEqual(data["device_id"], "d1")

    def test_invalid_token_rejected(self):
        self.assertIsNone(self.manager.validate_token("bst_device_totally-made-up"))

    def test_raw_token_is_never_stored_only_its_hash(self):
        token = self.manager.issue_token("u1", "d1", [])
        stored_keys = list(self.fake_redis._store.keys())
        self.assertEqual(len(stored_keys), 1)
        self.assertNotIn(token, stored_keys[0])  # key is a hash of the token, not the token itself
        self.assertNotIn(token, json.dumps(self.fake_redis._store))  # nor is it in the stored value

    def test_each_device_gets_an_independent_token(self):
        '''p07.md section 18: D1's token must not resolve as D2's, and revoking one must not
        affect the other.'''
        t1 = self.manager.issue_token("u1", "d1", [])
        t2 = self.manager.issue_token("u1", "d2", [])
        self.assertNotEqual(t1, t2)
        self.manager.revoke_token(t2)
        self.assertIsNotNone(self.manager.validate_token(t1))
        self.assertIsNone(self.manager.validate_token(t2))


if __name__ == "__main__":
    unittest.main()
