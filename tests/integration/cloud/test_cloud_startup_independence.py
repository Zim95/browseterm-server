'''
Proves the Cloud entrypoint (`app.py`) can be constructed/imported without any of the
local-only runtime dependencies (ContainerMaker, Socket-SSH, local Kubernetes workspace cluster,
MinIO). As of P06 those dependencies (`src.containers.containers_service`,
`src.payments.payments_service`, `src.common.k8s_secrets`, `src.api_handlers`) do not exist
anywhere in this repository at all -- they moved to `browseterm-server-local` -- so this is now
also a structural guarantee, not just an import-graph one.

Each check is run in a fresh subprocess: import side effects (module-level singletons, cached
`sys.modules`) cannot be reliably un-done within one pytest process, and the whole point here is
proving what a *fresh* process does on startup, matching what an actual Cloud pod does.
'''
import subprocess
import sys
from pathlib import Path
from unittest import TestCase

REPO_ROOT = Path(__file__).resolve().parents[3]


def _run(code: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


class TestCloudAppStartupIndependence(TestCase):
    def test_app_imports_without_reachable_kubeconfig(self) -> None:
        '''
        The real regression this guards: importing anything that pulls in
        `src.common.k8s_secrets` with no reachable kubeconfig/in-cluster config raises
        `ConfigException` at import time. `app.py` must not have this problem -- a real
        Cloud pod has no local Kubernetes workspace cluster to talk to.
        '''
        import os
        env = dict(os.environ)
        env["KUBECONFIG"] = "/nonexistent/kubeconfig"
        result = _run("import app", env)
        self.assertEqual(
            result.returncode, 0,
            msg=f"app failed to import without a kubeconfig:\n{result.stderr}",
        )

    def test_app_does_not_pull_in_k8s_or_containermaker_or_payment_modules(self) -> None:
        '''
        Confirms the Cloud entrypoint's import graph never reaches the `kubernetes` client
        library, ContainerMaker's gRPC service module, or the payment-gateway service module --
        i.e. it genuinely does not require ContainerMaker/Socket-SSH/local k8s/MinIO to start,
        rather than merely happening to succeed because this dev machine has a valid kubeconfig.
        '''
        import os
        env = dict(os.environ)
        code = (
            "import sys\n"
            "import app\n"
            "bad = [m for m in sys.modules if m == 'kubernetes' or m.startswith('kubernetes.') "
            "or m in ('src.containers.containers_service', 'src.payments.payments_service', "
            "'src.common.k8s_secrets', 'src.api_handlers')]\n"
            "assert not bad, f'unexpected modules imported: {bad}'\n"
            "print('CLEAN')\n"
        )
        result = _run(code, env)
        self.assertEqual(
            result.returncode, 0,
            msg=f"unexpected local-only dependency import:\n{result.stdout}\n{result.stderr}",
        )
        self.assertIn("CLEAN", result.stdout)
