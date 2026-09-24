import json
from unittest import TestCase

from src.cloud.container_config_snapshot import (
    build_create_config_json, build_resume_config_json, build_delete_config_json, build_hibernate_config_json,
)


def _container(**overrides) -> dict:
    row = {
        "id": "c1", "user_id": "u1", "name": "my-terminal", "cpu_limit": "1", "memory_limit": "1Gi",
        "storage_limit": "2Gi", "port_mappings": None, "environment_vars": None, "saved_image": None,
    }
    row.update(overrides)
    return row


class TestBuildCreateConfigJson(TestCase):
    def test_includes_image_name_and_derived_requests(self) -> None:
        cfg = json.loads(build_create_config_json(_container(), "browseterm/base:latest"))
        self.assertEqual(cfg["image_name"], "browseterm/base:latest")
        self.assertEqual(cfg["container_name"], "my-terminal")
        self.assertEqual(cfg["network_name"], "u1-namespace")
        self.assertEqual(cfg["cpu_limit"], "1")
        self.assertEqual(cfg["cpu_request"], "100m")
        self.assertNotIn("saved_image", cfg)

    def test_default_publish_information_used_when_none_stored(self) -> None:
        cfg = json.loads(build_create_config_json(_container(), "img"))
        self.assertEqual(cfg["publish_information"], [{"publish_port": 2222, "target_port": 22, "protocol": "TCP", "node_port": None}])

    def test_container_id_is_injected_into_environment_variables(self) -> None:
        '''
        Regression test for a real, high-impact production bug: this function used to pass
        environment_vars through verbatim, never injecting CONTAINER_ID - container-maker's
        pod_manager.py reads exactly that key to stamp the browseterm/container-id pod label,
        which status_monitor's resource_reconciler.py then reads back to know which DB
        container_id a live pod belongs to. Without it, every genuinely-running pod looked
        invisible to the reconciler, which called mark_lost_if_running on all of them on its next
        pass - silently flipping healthy, running containers to HIBERNATED with no
        device_commands row anywhere to explain why. The container's own stored env vars
        (SSH_USERNAME etc.) must still come through unchanged alongside it.
        '''
        cfg = json.loads(build_create_config_json(_container(environment_vars={"SSH_USERNAME": "ubuntu"}), "img"))
        self.assertEqual(cfg["environment_variables"], {"SSH_USERNAME": "ubuntu", "CONTAINER_ID": "c1"})

    def test_container_id_injected_even_with_no_stored_env_vars(self) -> None:
        cfg = json.loads(build_create_config_json(_container(environment_vars=None), "img"))
        self.assertEqual(cfg["environment_variables"], {"CONTAINER_ID": "c1"})


class TestBuildResumeConfigJson(TestCase):
    def test_includes_saved_image_not_image_name(self) -> None:
        cfg = json.loads(build_resume_config_json(_container(saved_image="registry/img:1")))
        self.assertEqual(cfg["saved_image"], "registry/img:1")
        self.assertNotIn("image_name", cfg)

    def test_container_id_is_injected_into_environment_variables(self) -> None:
        '''Same production bug as CREATE's own regression test - resume must also carry
        CONTAINER_ID so the resumed pod gets the label the reconciler depends on.'''
        cfg = json.loads(build_resume_config_json(_container(saved_image="registry/img:1", environment_vars={"SSH_USERNAME": "ubuntu"})))
        self.assertEqual(cfg["environment_variables"], {"SSH_USERNAME": "ubuntu", "CONTAINER_ID": "c1"})


class TestBuildDeleteAndHibernateConfigJson(TestCase):
    def test_delete_config_has_only_network_name(self) -> None:
        cfg = json.loads(build_delete_config_json(_container()))
        self.assertEqual(cfg, {"network_name": "u1-namespace"})

    def test_hibernate_config_has_only_network_name(self) -> None:
        cfg = json.loads(build_hibernate_config_json(_container()))
        self.assertEqual(cfg, {"network_name": "u1-namespace"})
