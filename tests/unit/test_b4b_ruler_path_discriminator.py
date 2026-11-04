"""B4b 验收尺的 PATH 判别力自证 (BET-Y2Q4-T10-282).

scripts/tools/launchd-workspace-reality-check.py 的 pointing_to_workspace_count 是
plan §分期 B4b 判据「指向 Workspace 的 plist 由 N → 0」的读数。它原先把 plist 整份
文件文本当扫描面, 于是 ai.hermes.gateway 仅因 EnvironmentVariables.PATH 里列了
<检出根>/bin 就被记成「指向 Workspace」—— 解释器搜索路径不是被指认的服务目标,
这条假阳让 B4b 的终局读数不可能归零 (剩下的每一条都得靠人肉分辨是不是 PATH)。

反方向同样要紧: 若把「排除 PATH」写成丢整行, 或多行 plist 看着对、压缩成一行就 silently
丢证据; 若把 install_root 的判定留在文本面上, PATH 里出现过安装位就会虚报「该服务已改道」。
四条用例: 同一份扫描目录里的假阳被排除而真字面量仍计入、EnvironmentVariables 里除 PATH
以外的写根仍计入、丢整行的写法在压缩 plist 上必红、install 桶共享同一判别。
"""

from __future__ import annotations

import importlib.util
import plistlib
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
RULER = REPO / "scripts" / "tools" / "launchd-workspace-reality-check.py"


def _exec(path: Path, name: str) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


def _load_ruler(monkeypatch) -> object:
    # 尺的 canonical_root 会兜底 ~/Workspace; hermetic 复跑不得读 host 面。
    monkeypatch.setenv("OMOSTATION_ROOT", str(REPO))
    monkeypatch.delenv("OMOSTATION_STATE_ROOT", raising=False)
    monkeypatch.delenv("OMOSTATION_ROOT_OVERRIDE", raising=False)
    path_snapshot = list(sys.path)
    try:
        return _exec(RULER, "t282_ruler_under_test")
    finally:
        # 真实尺会把 bin/lib 塞进 sys.path; 不清回去, 后续用例的 import 面就被污染。
        sys.path[:] = path_snapshot
        sys.modules.pop("repo_root", None)


def _write_plist(directory: Path, label: str, data: dict, *, minified: bool = False) -> Path:
    """按 launchd 真会吃到的两种排版落盘 (plistlib.dumps 自带 xml 声明 + DOCTYPE)。"""
    path = directory / f"{label}.plist"
    lines = plistlib.dumps(data, fmt=plistlib.FMT_XML).decode("utf-8").splitlines()
    head, body = lines[:2], "".join(lines[2:])
    text = "\n".join(head) + "\n" + (body if minified else "\n".join(lines[2:]) + "\n")
    path.write_text(text, encoding="utf-8")
    return path


def _service(label: str, *, path_value: str | None = None, **extra: object) -> dict:
    data: dict = {
        "Label": label,
        "ProgramArguments": ["/bin/echo", "noop"],
        "RunAtLoad": True,
    }
    if path_value is not None:
        data["EnvironmentVariables"] = {"PATH": path_value}
    data.update(extra)
    return data


def _ws_roots(module: object) -> tuple[str, ...]:
    return (str(module.canonical_root()), str(module.code_root()))


def _legacy_raw_count(directory: Path, roots: tuple[str, ...]) -> int:
    """旧尺: 整份文件文本做子串判定 —— 这就是被否证的读数。"""
    return sum(
        any(root in p.read_text(encoding="utf-8", errors="replace") for root in roots)
        for p in sorted(directory.glob("*.plist"))
    )


def _naive_line_discard_count(directory: Path, roots: tuple[str, ...]) -> int:
    """把 PATH 所在整行丢掉再扫文本 —— 「排除 PATH」最省事的写法。"""
    total = 0
    for p in sorted(directory.glob("*.plist")):
        kept: list[str] = []
        skip_value = False
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if "<key>PATH</key>" in line:
                skip_value = True
                continue
            if skip_value and "<string>" in line:
                skip_value = False
                continue
            kept.append(line)
        text = "\n".join(kept)
        total += any(root in text for root in roots)
    return total


def test_path_only_hit_excluded_but_true_literal_counted_in_one_scan(
    monkeypatch, tmp_path: Path
) -> None:
    """done_when 4: 同一次扫描里假阳被排除、真字面量仍计入 —— 读数 2 → 1。"""
    module = _load_ruler(monkeypatch)
    roots = _ws_roots(module)
    ws = roots[0]

    _write_plist(
        tmp_path,
        "ai.hermes.gateway",
        _service("ai.hermes.gateway", path_value=f"/usr/bin:/bin:{ws}/bin"),
    )
    _write_plist(
        tmp_path,
        "com.omostation.test-archive-purge-7d",
        _service(
            "com.omostation.test-archive-purge-7d",
            path_value="/usr/bin:/bin",
            ProgramArguments=["/bin/bash", "-lc", f"cd {ws} && python3 bin/ops/purge.py"],
            WorkingDirectory=ws,
            StandardOutPath=f"{ws}/runtime/cron/purge.log",
            StandardErrorPath=f"{ws}/runtime/cron/purge.log",
        ),
    )

    result = module.scan_launchd_workspace_targets(launchd_dir=tmp_path)
    assert _legacy_raw_count(tmp_path, roots) == 2, "旧尺读数应仍把两条都算进去"
    assert result["pointing_to_workspace_count"] == 1
    assert [h["label"] for h in result["workspace_hits_sample"]] == [
        "com.omostation.test-archive-purge-7d"
    ]
    assert result["total_plists"] == 2
    assert (
        result["pointing_to_workspace_count"]
        + result["pointing_to_install_count"]
        + result["other_count"]
    ) == result["total_plists"], "排除一条假阳只能换桶, 不能让总数蒸发"


def test_write_root_env_var_other_than_path_still_counts(monkeypatch, tmp_path: Path) -> None:
    """判别必须按键作用域: EnvironmentVariables 里除 PATH 以外的写根仍是服务目标。"""
    module = _load_ruler(monkeypatch)
    ws = _ws_roots(module)[0]
    _write_plist(
        tmp_path,
        "com.example.state-root",
        _service(
            "com.example.state-root",
            EnvironmentVariables={
                "PATH": f"/usr/bin:{ws}/bin",
                "OMOSTATION_STATE_ROOT": ws,
            },
        ),
    )

    result = module.scan_launchd_workspace_targets(launchd_dir=tmp_path)
    assert result["pointing_to_workspace_count"] == 1, "写根被 PATH 的豁免顺带放走了"
    assert result["state_root_distribution"]["checkout"] == 1


def test_line_discard_rule_is_red_on_minified_plist(monkeypatch, tmp_path: Path) -> None:
    """done_when 5 反证: 压缩成一行的 plist 里 PATH 与真目标同处一行,
    丢整行的写法把证据一起丢掉 (报 0), 尺必须仍报 1。"""
    module = _load_ruler(monkeypatch)
    roots = _ws_roots(module)
    ws = roots[0]
    _write_plist(
        tmp_path,
        "com.example.minified",
        _service(
            "com.example.minified",
            EnvironmentVariables={"PATH": f"/usr/bin:{ws}/bin"},
            ProgramArguments=["/bin/bash", "-lc", f"cd {ws} && python3 server.py"],
        ),
        minified=True,
    )

    assert _naive_line_discard_count(tmp_path, roots) == 0, "反例实现未按预期失配"
    result = module.scan_launchd_workspace_targets(launchd_dir=tmp_path)
    assert result["pointing_to_workspace_count"] == 1


def test_install_bucket_shares_the_same_discriminator(monkeypatch, tmp_path: Path) -> None:
    """豁免是对称的: 安装位只出现在 PATH 里时不得记成「已改道到安装位」。"""
    module = _load_ruler(monkeypatch)
    inst = str(module.install_root())
    assert inst, "本机无安装位时本用例不适用"
    _write_plist(
        tmp_path,
        "com.example.path-only-install",
        _service("com.example.path-only-install", path_value=f"/usr/bin:{inst}/bin"),
    )

    result = module.scan_launchd_workspace_targets(launchd_dir=tmp_path)
    assert result["pointing_to_install_count"] == 0, "PATH 里的安装位被当作了改道证据"
    assert result["other_count"] == 1
