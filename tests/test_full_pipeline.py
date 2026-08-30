#!/usr/bin/env python3
"""全链路端到端测试 — 验证信号→场景→旅程→价值→进化 完整流水线。

测试覆盖:
1. 信号路由 (signal_router)
2. 场景卡激活状态
3. 能力发现 (cockpit capabilities)
4. 探测器心跳
5. 编排引擎连通性
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    status = "PASS" if condition else "FAIL"
    if condition:
        PASSED += 1
    else:
        FAILED += 1
    msg = f"  [{status}] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO))


def test_signal_router() -> None:
    """测试信号路由器。"""
    print("\n=== 信号路由 ===")
    result = run_cmd(
        [
            sys.executable,
            str(REPO / "bin" / "bc-os" / "signal_router.py"),
            "--calendar",
            str(REPO / ".omo" / "_delivery" / "personal-signals" / "calendars" / "events.ics"),
            "--json",
        ]
    )
    check("signal_router executes", result.returncode == 0)
    if result.returncode == 0:
        data = json.loads(result.stdout)
        check("calendar routed > 0", data["summary"]["total_routed"] > 0, f"routed={data['summary']['total_routed']}")
        scenes = data["summary"].get("by_scene", {})
        check("meeting-supervision routed", "meeting-supervision" in scenes)
        check("research-pipeline routed", "research-pipeline" in scenes)


def test_scene_cards() -> None:
    """测试场景卡激活状态。"""
    print("\n=== 场景卡 ===")
    cards_dir = REPO / "docs" / "scene-cards"
    if not cards_dir.exists():
        check("scene-cards directory exists", False)
        return

    active_count = 0
    supervised_count = 0
    for f in sorted(cards_dir.glob("*.yaml")):
        text = f.read_text(encoding="utf-8")
        if "activation: active" in text or "status: active" in text:
            active_count += 1
        if "lifecycle: supervised" in text or "lifecycle: routine" in text:
            supervised_count += 1

    check("10+ active scene cards", active_count >= 10, f"active={active_count}")
    check("8+ supervised+ cards", supervised_count >= 8, f"supervised={supervised_count}")


def test_capabilities() -> None:
    """测试能力发现。"""
    print("\n=== 能力发现 ===")
    commands_dir = REPO / "projects" / "cockpit" / "src" / "cockpit" / "commands"
    capabilities_file = commands_dir / "capabilities.py"
    check("capabilities.py exists", capabilities_file.exists())


def test_probes() -> None:
    """测试探测器心跳。"""
    print("\n=== 探测器心跳 ===")
    result = run_cmd(
        [
            sys.executable,
            str(REPO / "bin" / "gac" / "probe-heartbeat-monitor.py"),
            "--status",
        ]
    )
    check("probe monitor executes", result.returncode == 0)
    # Check output mentions 8 normal
    output = result.stdout
    check("8/8 probes healthy", "正常: 8" in output or "异常: 0" in output, output.strip())


def test_orchestrator() -> None:
    """测试编排引擎连通性。"""
    print("\n=== 编排引擎 ===")
    result = run_cmd(
        [
            sys.executable,
            str(REPO / "bin" / "gac" / "unified-orchestrator.py"),
            "--run-all",
        ]
    )
    check("orchestrator executes", result.returncode == 0)
    if result.returncode == 0:
        try:
            # Find the JSON in output
            output = result.stdout
            start = output.find("{")
            if start >= 0:
                data = json.loads(output[start:])
                connectivity = data.get("connectivity", 0)
                check("100% connectivity", connectivity == 100.0, f"connectivity={connectivity}%")
        except json.JSONDecodeError:
            check("orchestrator JSON parse", False)


def test_documentation() -> None:
    """测试文档完整性。"""
    print("\n=== 文档 ===")
    check("AGENTS.md exists", (REPO / "AGENTS.md").exists())
    check("README.md exists", (REPO / "README.md").exists())
    check("scene-cards exist", (REPO / "docs" / "scene-cards").exists())
    check("journey-specs exist", (REPO / "docs" / "journey-specs").exists())


def main() -> int:
    print("=" * 60)
    print("全链路端到端测试")
    print("=" * 60)

    test_signal_router()
    test_scene_cards()
    test_capabilities()
    test_probes()
    test_orchestrator()
    test_documentation()

    print("\n" + "=" * 60)
    print(f"结果: {PASSED} passed, {FAILED} failed")
    print("=" * 60)
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
