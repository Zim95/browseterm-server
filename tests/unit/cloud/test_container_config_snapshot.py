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


class TestBuildResumeConfigJson(TestCase):
    def test_includes_saved_image_not_image_name(self) -> None:
        cfg = json.loads(build_resume_config_json(_container(saved_image="registry/img:1")))
        self.assertEqual(cfg["saved_image"], "registry/img:1")
        self.assertNotIn("image_name", cfg)


class TestBuildDeleteAndHibernateConfigJson(TestCase):
    def test_delete_config_has_only_network_name(self) -> None:
        cfg = json.loads(build_delete_config_json(_container()))
        self.assertEqual(cfg, {"network_name": "u1-namespace"})

    def test_hibernate_config_has_only_network_name(self) -> None:
        cfg = json.loads(build_hibernate_config_json(_container()))
        self.assertEqual(cfg, {"network_name": "u1-namespace"})
