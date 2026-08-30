'''
Sanity checks that the Cloud deployment artifacts actually point at the Cloud entrypoint,
without needing a real Kubernetes cluster to verify it (plain text/YAML assertions only).
'''
from pathlib import Path
from unittest import TestCase

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]


class TestCloudEntrypointScript(TestCase):
    def test_entrypoint_runs_app(self) -> None:
        content = (REPO_ROOT / "infra/cloud/entrypoint-cloud.sh").read_text()
        self.assertIn("app:app", content)


class TestCloudManifest(TestCase):
    def setUp(self) -> None:
        raw = (REPO_ROOT / "infra/cloud/cloud.yaml").read_text()
        # Manifest uses ${VAR} shell-style placeholders (envsubst), not valid bare YAML scalars
        # in a couple of spots; substitute harmless placeholders so it parses for structural
        # assertions, matching how deployment.yaml is only ever rendered via envsubst too.
        for var in ("NAMESPACE", "REPO_NAME", "REDIS_HOST", "REDIS_PORT", "REDIS_PASSWORD",
                    "REDIS_USERNAME", "REDIS_DB", "POSTGRES_HOST", "POSTGRES_PORT"):
            raw = raw.replace(f"${{{var}}}", f"placeholder-{var.lower()}")
        self.docs = list(yaml.safe_load_all(raw))

    def test_deployment_and_service_present_and_distinguishable(self) -> None:
        kinds = {(d["kind"], d["metadata"]["name"]) for d in self.docs if d}
        self.assertIn(("Deployment", "browseterm-server-cloud"), kinds)
        self.assertIn(("Service", "browseterm-server-cloud-service"), kinds)
        # Must not collide with the existing (Local-ish) browseterm-server manifest names.
        names = {d["metadata"]["name"] for d in self.docs if d}
        self.assertNotIn("browseterm-server", names)
        self.assertNotIn("browseterm-server-service", names)

    def test_deployment_runs_cloud_container_and_healthz_probes(self) -> None:
        deployment = next(d for d in self.docs if d and d["kind"] == "Deployment")
        container = deployment["spec"]["template"]["spec"]["containers"][0]
        self.assertIn("browseterm-server-cloud", container["image"])
        self.assertEqual(container["livenessProbe"]["httpGet"]["path"], "/healthz")
        self.assertEqual(container["readinessProbe"]["httpGet"]["path"], "/healthz")

    def test_deployment_env_has_no_local_only_settings(self) -> None:
        deployment = next(d for d in self.docs if d and d["kind"] == "Deployment")
        container = deployment["spec"]["template"]["spec"]["containers"][0]
        env_names = {e["name"] for e in container.get("env", [])}
        local_only = {
            "CONTAINER_MAKER_HOST", "CONTAINER_MAKER_PORT", "CONTAINER_MAKER_CERTS_SECRET_NAME",
            "SOCKET_SSH_WSS_URL", "PAYMENT_GATEWAY_HOST", "PAYMENT_GATEWAY_PORT",
            "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET",
        }
        self.assertTrue(env_names.isdisjoint(local_only), env_names & local_only)
        self.assertIn("POSTGRES_HOST", env_names)
        self.assertIn("REDIS_HOST", env_names)
