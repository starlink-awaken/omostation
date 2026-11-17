"""strategy_sources 资产必须从 **workspace** 根读 `.omo/_delivery/agent-workflows/runs`。

背景 (债条目 PANORAMA-A9-SOURCES-STALE-12D, 2026-11-10 立, 2026-11-17 复测仍在):
线上 `refresh.py` 调 `collect_strategy_sources(workspace=code_root(),
state_root=state_root(), ...)`; 而 state 根下的 `.omo/_delivery/agent-workflows`
是**指向 workspace 的符号链接** (状态面镜像桥)。资产的 `_collect_runs` 用
`reader.discover("state", ...)` 去读它 —— `BoundedReader` 按构造**不可穿软链**
(`resolve()` 后 `is_relative_to(root)` 为假 ⇒ `outside_allowlisted_root`),
于是 runs 恒采不到, strategy 恒 PARTIAL, A9 无法闭合。

同一份逻辑在 `projects/cockpit/src/cockpit/observatory/strategy_sources.py`
(权威源) 早已是 `"workspace"`; 资产副本漂移了。本用例复刻线上拓扑, 钉住这两个根参数。
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path

import pytest

ASSET = Path(__file__).resolve().parents[1] / "bin/panorama/assets/host/strategy_sources.py.asset"


def _load():
    # 资产 import probe_utils —— 该模块只存在于部署目录, 仓里没有 .asset 副本
    # (zhixing-host-sync 的 HOST_FILES 也不含它)。本用例只关心根选择, 打桩即可。
    if "probe_utils" not in sys.modules:
        stub = types.ModuleType("probe_utils")
        stub.redact_secrets = lambda text: text
        sys.modules["probe_utils"] = stub
    # `.py.asset` 后缀不被 spec_from_file_location 识别 ⇒ 显式给 SourceFileLoader
    loader = importlib.machinery.SourceFileLoader("strategy_sources_asset", str(ASSET))
    spec = importlib.util.spec_from_loader("strategy_sources_asset", loader)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["strategy_sources_asset"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def planes(tmp_path: Path) -> dict[str, Path]:
    """复刻线上拓扑: state 根下的 `.omo/_delivery/agent-workflows` 是指向 workspace 的软链。"""
    mod = _load()
    workspace = tmp_path / "Workspace"
    state_root = tmp_path / "state"
    library = tmp_path / "library"
    app = tmp_path / "app"
    for d in (workspace, state_root, library, app):
        d.mkdir(parents=True, exist_ok=True)

    (workspace / ".git").mkdir()
    (workspace / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (workspace / ".git" / "refs" / "heads").mkdir(parents=True)
    (workspace / ".git" / "refs" / "heads" / "main").write_text("0" * 40 + "\n", encoding="utf-8")

    runs = workspace / ".omo" / "_delivery" / "agent-workflows" / "runs"
    runs.mkdir(parents=True)
    (runs / "run-1.yaml").write_text(
        "run_id: RUN-1\nstatus: ok\ntitle: t\nupdated_at: '2026-11-17T00:00:00Z'\n",
        encoding="utf-8",
    )
    retros = workspace / ".omo" / "_knowledge" / "retros"
    retros.mkdir(parents=True)

    mirror = state_root / ".omo" / "_delivery"
    mirror.mkdir(parents=True)
    (mirror / "agent-workflows").symlink_to(workspace / ".omo" / "_delivery" / "agent-workflows")

    assert (mirror / "agent-workflows" / "runs" / "run-1.yaml").is_file(), "装置: 软链必须可达"
    return {"workspace": workspace, "state_root": state_root, "library": library, "app": app, "mod": mod}


def test_collect_runs_reads_workspace_not_the_state_symlink(planes):
    """线上调用形态 (refresh.py: 同时传 workspace 与 state_root) 必须采到 runs。"""
    mod = planes["mod"]
    result = mod._collect_strategy_sources(
        planes["workspace"], planes["library"], planes["app"],
        state_root=planes["state_root"],
    )
    runs = result["records"]["runs"]
    assert [r.get("id") for r in runs] == ["RUN-1"], (
        f"runs 未采到 —— 资产仍从 state 根读软链: runs={runs} "
        f"errors={result['errors'][:3]}"
    )


def test_state_root_symlink_does_not_emit_allowlist_error(planes):
    """不得出现 `outside_allowlisted_root` —— 那是读者拒绝穿软链的信号。"""
    mod = planes["mod"]
    result = mod._collect_strategy_sources(
        planes["workspace"], planes["library"], planes["app"],
        state_root=planes["state_root"],
    )
    codes = [e.get("code") for e in result["errors"]]
    assert "outside_allowlisted_root" not in codes, (
        f"state 根软链被判出库外: errors={result['errors'][:5]}"
    )


def test_asset_matches_authoritative_cockpit_root_choice(planes):
    """资产与权威源在 `_collect_runs` 的根选择上必须一致 (防再次漂移)。

    权威源 `projects/cockpit/src/cockpit/observatory/strategy_sources.py`
    的 `_collect_runs` 用 `"workspace"`; 资产漂移过一次, 这里逐字比对那两行。
    """
    cockpit = (
        Path(__file__).resolve().parents[1]
        / "projects/cockpit/src/cockpit/observatory/strategy_sources.py"
    )
    if not cockpit.is_file():
        pytest.skip("cockpit 子模块未检出 —— 权威源缺席, 无法对拍 (检出形态, 不是回归)")
    asset_text = ASSET.read_text(encoding="utf-8")
    cockpit_text = cockpit.read_text(encoding="utf-8")
    for marker in (
        'reader.discover("workspace", ".omo/_delivery/agent-workflows/runs"',
    ):
        assert marker in cockpit_text, f"权威源已改口径, 本钉要更新: {marker}"
        assert marker in asset_text, f"资产漂移到非 workspace 根: {marker}"
    assert 'reader.discover("state", ".omo/_delivery/agent-workflows/runs"' not in asset_text, (
        "资产又回到 state 根读 runs"
    )
