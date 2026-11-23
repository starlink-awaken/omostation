"""Workflow observer runtime selection retains a managed venv invocation path."""

from __future__ import annotations

import contextlib
import importlib
import json
import shutil
import subprocess
import sys
import types
import venv
from pathlib import Path

import pytest


ASSET = Path(__file__).resolve().parents[1] / "bin/panorama/assets/host/workflow_collector.py.asset"
RUNNER = Path(__file__).resolve().parents[1] / "bin/gac/managed-python"
_COLLECTOR_MODULES = ("collectors", "collectors.base", "collectors.registry", "collectors.workflow")


@contextlib.contextmanager
def _sandboxed_collector_modules():
    """导入 `collectors` 族之前把既有键挪开, 退出时**连新建的一起**还原。

    只靠 `monkeypatch.delitem` 是不够的: delitem 只对**原本存在**的键登记还原点,
    而 `import_module` 会**新建** `collectors` / `.base` / `.registry` / `.workflow`
    —— 没有任何还原点覆盖它们, 于是它们留在 `sys.modules` 里污染后续用例。
    """
    saved = {name: sys.modules.get(name) for name in _COLLECTOR_MODULES}
    for name in _COLLECTOR_MODULES:
        sys.modules.pop(name, None)
    importlib.invalidate_caches()
    try:
        yield
    finally:
        for name in _COLLECTOR_MODULES:
            sys.modules.pop(name, None)
        for name, module in saved.items():
            if module is not None:
                sys.modules[name] = module


@pytest.fixture
def workflow_collector(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """导入 collectors.workflow 真身, 用完把 `sys.modules` 还原到位。

    实测 (2026-11-23): 跑 `tests/` 全量选择时, `tests/unit/test_panorama_pending_authorizations.py`
    五条用例恒红 `ModuleNotFoundError: No module named 'collectors.personal_value'` ——
    它自己的 `deploy_collectors` 装的是含 `personal_value` 的包, 但 `sys.modules["collectors"]`
    已被本文件的临时包占住。单独跑该文件、或只跑 `tests/unit`, 都不复现 (污染源在 `tests/`)。
    """
    package = tmp_path / "collectors"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    shutil.copy2(ASSET.parent / "collectors.base.py.asset", package / "base.py")
    shutil.copy2(ASSET.parent / "collectors.registry.py.asset", package / "registry.py")
    shutil.copy2(ASSET, package / "workflow.py")
    monkeypatch.syspath_prepend(str(tmp_path))
    with _sandboxed_collector_modules():
        yield importlib.import_module("collectors.workflow")


def test_sandboxed_collector_modules_restores_preexisting_entry():
    """既有键要原样还回去。"""
    sentinel = types.ModuleType("collectors")
    sys.modules["collectors"] = sentinel
    try:
        with _sandboxed_collector_modules():
            assert "collectors" not in sys.modules
        assert sys.modules["collectors"] is sentinel, "既有键未还原"
    finally:
        sys.modules.pop("collectors", None)


def test_sandboxed_collector_modules_drops_newly_imported_entries():
    """新建出来的 collectors* 键一个都不准留下 —— 这正是旧实现漏的那半。"""
    with _sandboxed_collector_modules():
        sys.modules["collectors"] = types.ModuleType("collectors")
    assert "collectors" not in sys.modules, "新建的键漏在了 sys.modules 里"



@pytest.fixture
def managed_venv(tmp_path: Path):
    root = tmp_path / "workspace"
    selector = root / "bin/gac/managed-python"
    selector.parent.mkdir(parents=True)
    runtime = root / ".venv"
    venv.EnvBuilder(with_pip=False, symlinks=True, system_site_packages=True).create(runtime)
    executable = runtime / "bin/python"
    assert executable.is_symlink(), "regression requires a real virtualenv symlink"
    purelib = subprocess.run(
        [str(executable), "-B", "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    Path(purelib, "yaml.py").write_text("# selector capability fixture\n", encoding="utf-8")
    Path(purelib, "workflow_venv_dependency.py").write_text(
        "VALUE = 'venv-only-observer-dependency'\n", encoding="utf-8"
    )
    return root, selector, executable


def _metadata(executable: Path) -> list[int]:
    return json.loads(subprocess.run(
        [str(executable), "-B", "-c", "import json, sys; print(json.dumps(list(sys.version_info[:3])))"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout)


def _write_legacy_selector(
    selector: Path,
    receipt: dict,
    runtime: Path | None = None,
    metadata: dict | None = None,
) -> None:
    root = selector.parents[2]
    (root / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    if metadata is not None:
        run = f"  run) printf '%s\\n' {json.dumps(metadata)!r} ;;\n"
    else:
        assert runtime is not None
        run = f"  run) shift 4; exec {str(runtime)!r} \"$@\" ;;\n"
    source = (
        "#!/bin/sh\n"
        "case \"$1\" in\n"
        "  probe) exec /bin/cat \"$(dirname \"$0\")/../../receipt.json\" ;;\n"
        + run
        + "  *) exit 2 ;;\n"
        + "esac\n"
    )
    selector.write_text(source, encoding="utf-8")
    selector.chmod(0o755)


def test_module_import_keeps_the_sandboxed_managed_runtime(
    workflow_collector, managed_venv,
) -> None:
    root, selector, executable = managed_venv
    shutil.copy2(RUNNER, selector)
    collector = workflow_collector

    argv = collector.readonly_observe_argv(root)

    assert argv[:4] == ["/usr/bin/sandbox-exec", "-p", collector.READ_ONLY_PROFILE, str(executable)]
    assert argv[4:7] == ["-B", "-c", collector.READ_ONLY_OBSERVER]
    assert argv[-1] == str(root)


@pytest.mark.parametrize("exit_code, decision", [(0, "continue"), (1, "escalate")])
def test_current_selector_receipt_and_selected_runtime_preserve_venv_context(
    workflow_collector, managed_venv, exit_code: int, decision: str,
) -> None:
    root, selector, executable = managed_venv
    shutil.copy2(RUNNER, selector)
    collector = workflow_collector

    selected = collector._select_managed_python(root)
    result = subprocess.run(
        [str(selected), "-B", "-c", "import workflow_venv_dependency as dep; print(dep.VALUE)"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert selected == executable
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "venv-only-observer-dependency"
    diagnostic = collector.parse_diagnostic(
        json.dumps({"ok": exit_code == 0, "decision": decision, "run_count": 0, "lock_count": 0, "findings": []}),
        exit_code,
    )
    assert diagnostic["command_exit_code"] == exit_code


def test_legacy_realpath_receipt_uses_selector_run_metadata_context(
    workflow_collector, managed_venv,
) -> None:
    root, selector, executable = managed_venv
    collector = workflow_collector
    _write_legacy_selector(selector, {
        "schema": "managed-python-runtime-receipt/v1",
        "profile": "pyyaml",
        "provider": "workspace-venv",
        "capabilities": ["stdlib", "pyyaml"],
        "python_version": _metadata(executable),
        "executable": str(executable.resolve(strict=True)),
    }, executable)

    selected = collector._select_managed_python(root)

    assert selected == executable
    result = subprocess.run(
        [str(selected), "-B", "-c", "import workflow_venv_dependency as dep; print(dep.VALUE)"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "venv-only-observer-dependency"


def test_runtime_metadata_must_identify_the_probed_interpreter(
    workflow_collector, managed_venv,
) -> None:
    root, selector, executable = managed_venv
    collector = workflow_collector
    _write_legacy_selector(selector, {
        "schema": "managed-python-runtime-receipt/v1",
        "profile": "pyyaml",
        "provider": "workspace-venv",
        "capabilities": ["stdlib", "pyyaml"],
        "python_version": _metadata(executable),
        "executable": str(executable),
    }, metadata={
        "executable": "/bin/sh",
        "python_version": _metadata(executable),
        "has_pyyaml": True,
    })

    with pytest.raises(collector.CollectionError, match="runtime identity mismatch"):
        collector._select_managed_python(root)


def test_observe_timeout_leaves_room_under_the_collector_budget(
    workflow_collector,
) -> None:
    """The sandboxed observer must not burn the whole worker budget.

    Regression: a hardcoded 20s inner timeout fired under host load and the
    source reported "timed out after 20 seconds" instead of an observation.
    """
    collector = workflow_collector
    assert collector.OBSERVE_TIMEOUT >= 30
    assert collector.OBSERVE_TIMEOUT < 48
    assert collector._run_cmd.__defaults__[0] == collector.OBSERVE_TIMEOUT
    assert collector.SELECTOR_TIMEOUT >= 20
    assert collector.SELECTOR_TIMEOUT < collector.OBSERVE_TIMEOUT
