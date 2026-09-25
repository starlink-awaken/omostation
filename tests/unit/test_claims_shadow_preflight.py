import importlib.util
import hashlib
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

        @staticmethod
        def production_verifier_closure_digest():
            return "sha256:" + "c" * 64

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
        "high_water_exists": False,
        "highwater_exists": False,
        "activation_witness_exists": False,
    }
    recovery = report["recovery"]
    assert recovery["schema"] == "claims-preflight-recovery/v1"
    assert recovery["activation_authorized"] is False
    assert recovery["canonical_workspace_mutation_recommended"] is True
    assert recovery["isolated_workspace_recovery"] == [
    ]
    assert recovery["human_authorization_required"] == [
        "operation_specific_host_authorization_unproven"
    ]
    assert recovery["remaining_after_isolated_recovery"] == [
        "accepted_spec_digest_mismatch",
        "operation_specific_host_authorization_unproven"
    ]
    assert recovery["items"]["accepted_spec_digest_mismatch"][
        "canonical_mutation_required"
    ] is True
    assert recovery["items"][
        "operation_specific_host_authorization_unproven"
    ]["classification"] == "human_authorization_required"


class _StubVerifiers:
    @staticmethod
    def operator_authorization_verifier_digest():
        return "sha256:" + "a" * 64

    @staticmethod
    def stopped_process_verifier_digest():
        return "sha256:" + "b" * 64

    @staticmethod
    def production_verifier_closure_digest():
        return "sha256:" + "c" * 64


def _prepare_valid_root(tmp_path, module):
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
    subprocess.run(
        ["git", "-C", str(root), "update-ref", "refs/remotes/origin/main", "HEAD"],
        check=True,
    )
    original_digest = module.ACCEPTED_SPEC_SHA256
    module.ACCEPTED_SPEC_SHA256 = "sha256:" + hashlib.sha256(
        (root / module.CLOSURE_PATHS["spec"]).read_bytes()
    ).hexdigest()
    return root, original_digest


def _authority_report(tmp_path, module, *, store=False, high_water=False, legacy=False):
    root, original_digest = _prepare_valid_root(tmp_path, module)
    authority_dir = tmp_path / "home/agents/_shared/runtime/omo-claims-authority-r0"
    authority_dir.mkdir(parents=True)
    if store:
        (authority_dir / "store.sqlite3").write_bytes(b"sqlite")
    if high_water:
        (authority_dir / "high-water.json").write_text("{}", encoding="utf-8")
    if legacy:
        (authority_dir / "highwater.json").write_text("{}", encoding="utf-8")
    try:
        return module.collect_preflight(
            root,
            account_home=tmp_path / "home",
            observed_at="2026-09-22T00:00:00+00:00",
            verifiers=_StubVerifiers,
        )
    finally:
        module.ACCEPTED_SPEC_SHA256 = original_digest


def test_preflight_accepts_production_high_water_filename(tmp_path) -> None:
    report = _authority_report(
        tmp_path, _module(), store=True, high_water=True
    )
    assert "authority_store_asymmetric_presence" not in report["hard_blockers"]
    assert report["runtime_state"]["high_water_exists"] is True
    assert report["runtime_state"]["highwater_exists"] is False


def test_preflight_rejects_legacy_highwater_filename(tmp_path) -> None:
    report = _authority_report(
        tmp_path, _module(), store=True, legacy=True
    )
    assert "authority_store_asymmetric_presence" in report["hard_blockers"]
    assert report["runtime_state"]["high_water_exists"] is False
    assert report["runtime_state"]["highwater_exists"] is True


def test_preflight_rejects_store_without_high_water(tmp_path) -> None:
    report = _authority_report(tmp_path, _module(), store=True)
    assert "authority_store_asymmetric_presence" in report["hard_blockers"]
    assert report["runtime_state"]["high_water_exists"] is False


def test_preflight_accepts_pristine_authority_layout(tmp_path) -> None:
    report = _authority_report(tmp_path, _module())
    assert "authority_store_asymmetric_presence" not in report["hard_blockers"]
    assert report["runtime_state"]["high_water_exists"] is False
    assert report["runtime_state"]["highwater_exists"] is False


def test_preflight_accepts_isolated_integration_root(tmp_path) -> None:
    module = _module()
    canonical = tmp_path / "canonical"
    isolated = tmp_path / "isolated"
    for root in (canonical, isolated):
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
        subprocess.run(
            ["git", "-C", str(root), "update-ref", "refs/remotes/origin/main", "HEAD"],
            check=True,
        )

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

    original_digest = module.ACCEPTED_SPEC_SHA256
    module.ACCEPTED_SPEC_SHA256 = "sha256:" + hashlib.sha256(
        (isolated / module.CLOSURE_PATHS["spec"]).read_bytes()
    ).hexdigest()

    original_load = module._load_verifiers

    def _load_isolated_verifiers(root):
        loaded = original_load(root)
        loaded.production_verifier_closure_digest = lambda: "sha256:" + "c" * 64
        return loaded

    module._load_verifiers = _load_isolated_verifiers
    try:
        (canonical / "canonical-dirty.txt").write_text(
            "canonical-dirty\n", encoding="utf-8"
        )
        report = module.collect_preflight(
            isolated,
            account_home=tmp_path / "home",
            observed_at="2026-09-17T00:00:00+00:00",
            verifiers=verifiers,
        )
    finally:
        module.ACCEPTED_SPEC_SHA256 = original_digest
        module._load_verifiers = original_load

    assert report["readiness"] == "AWAITING_AUTHORIZATION", {
        "hard": report["hard_blockers"],
        "closure": report["closure"],
        "verifier_error": report.get("verifier_error"),
    }
    assert report["hard_blockers"] == [], report["hard_blockers"]
    assert report["dirty_tracked_count"] == 0
    assert report["child_dirty_count"] == 0


def test_preflight_awaits_authorization_for_stale_nonclosure_dirty_root(tmp_path) -> None:
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
    (root / "runtime-local.txt").write_text("committed\n", encoding="utf-8")
    _commit_all(child)
    _commit_all(root)
    (root / "runtime-local.txt").write_text("dirty\n", encoding="utf-8")
    _commit_all(root)
    origin_commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    (root / "runtime-local.txt").write_text("dirty-again\n", encoding="utf-8")
    _commit_all(root)
    (root / "runtime-local.txt").write_text("dirty-observed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "update-ref", "refs/remotes/origin/main", origin_commit], check=True)

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

    spec_path = root / module.CLOSURE_PATHS["spec"]
    original_digest = module.ACCEPTED_SPEC_SHA256
    module.ACCEPTED_SPEC_SHA256 = "sha256:" + hashlib.sha256(spec_path.read_bytes()).hexdigest()
    try:
        report = module.collect_preflight(
            root,
            account_home=tmp_path / "home",
            observed_at="2026-09-17T00:00:00+00:00",
            verifiers=verifiers,
        )
    finally:
        module.ACCEPTED_SPEC_SHA256 = original_digest

    assert report["hard_blockers"] == [], report["hard_blockers"]
    assert report["readiness"] == "AWAITING_AUTHORIZATION"
    assert report["hard_blockers"] == []
    assert report["advisories"] == [
        "root_head_not_equal_origin_main",
        "nonclosure_dirty_tracked_integration_root",
    ]
    assert report["dirty_nonclosure_count"] == 1
    assert report["dirty_closure_paths"] == []
    assert "operation_specific_host_authorization_unproven" in report["blockers"]
    assert report["activation_allowed"] is False
    recovery = report["recovery"]
    assert recovery["canonical_workspace_mutation_recommended"] is False
    assert recovery["isolated_workspace_recovery"] == []
    assert recovery["human_authorization_required"] == [
        "operation_specific_host_authorization_unproven"
    ]
    assert recovery["remaining_after_isolated_recovery"] == [
        "operation_specific_host_authorization_unproven"
    ]
    assert "fresh managed exact-main clone" not in recovery["next_safe_action"]
    assert "inactive" in recovery["next_safe_action"]

def test_accepted_spec_digest_binding_matches_current_source() -> None:
    """防漂移: ACCEPTED_SPEC_SHA256 必须与当前 spec 源文件摘要一致.

    该常量是 claims 激活的**冻结绑定**: spec 一旦改动而未同步重绑定, preflight
    就会以 accepted_spec_digest_mismatch 硬阻塞激活。2026-09-25 #4328 的
    「面向前端全量 frontmatter 补全」批量改写了本 spec 的字节 (仅元数据, +6/-4),
    而该 preflight 的 trigger 仅为 manual, 故无人察觉 —— 直到人工跑 preflight
    才发现。此测试把该漂移提前到 CI 可见: spec 若需变更, 必须在**同一 PR** 内
    重绑定常量并接受治理审查 (canonical_mutation_required=true; 绝不改写历史 receipt)。
    """
    module = _module()
    spec_path = ROOT / module.CLOSURE_PATHS["spec"]
    actual = "sha256:" + hashlib.sha256(spec_path.read_bytes()).hexdigest()
    assert actual == module.ACCEPTED_SPEC_SHA256, (
        "accepted spec digest drifted:\n"
        f"  constant = {module.ACCEPTED_SPEC_SHA256}\n"
        f"  actual   = {actual}\n"
        "若 spec 变更属预期, 请在同一 PR 内重绑定 ACCEPTED_SPEC_SHA256 "
        "(bin/gac/claims-shadow-preflight.py) 并走治理审查; 勿改写历史 receipt。"
    )
