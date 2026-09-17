import importlib.util
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/gac/claims-shadow-preflight.py"


def _module():
    spec = importlib.util.spec_from_file_location("claims_shadow_preflight_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _init_repo(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True)


def _commit_all(path: Path):
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", "init", "-q"], check=True)


def test_preflight_reports_blocked_but_read_only_root(tmp_path) -> None:
    module = _module()
    root = tmp_path / "root"
    child = root / "projects/omo"
    _init_repo(root)
    child.mkdir(parents=True)
    _init_repo(child)
    for relative in module.CLOSURE_PATHS.values():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("closure\n", encoding="utf-8")
    (root / "projects/omo/.gitkeep").write_text("", encoding="utf-8")
    _commit_all(child)
    _commit_all(root)
    subprocess.run(["git", "-C", str(root), "add", "projects/omo"], check=True)
    subprocess.run(["git", "-C", str(root), "update-ref", "refs/remotes/origin/main", "HEAD"], check=True)

    class verifiers:
        @staticmethod
        def operator_authorization_verifier_digest():
            return "sha256:" + "a" * 64

        @staticmethod
        def stopped_process_verifier_digest():
            return "sha256:" + "b" * 64

        @staticmethod
        def production_verifier_closure_digest():
            return "sha256:" + "c" * 64

    report = module.collect_preflight(
        root,
        account_home=tmp_path / "home",
        observed_at="2026-09-17T00:00:00+00:00",
        verifiers=verifiers,
    )

    assert report["available"] is True
    assert report["activation_allowed"] is False
    assert report["operation_specific_authorization"] == "UNPROVEN"
    assert report["readiness"] == "BLOCKED"
    assert "operation_specific_host_authorization_unproven" in report["blockers"]
    assert "accepted_spec_digest_mismatch" in report["blockers"]
    assert report["runtime_state"] == {
        "store_exists": False,
        "highwater_exists": False,
        "activation_witness_exists": False,
    }
