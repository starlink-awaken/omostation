"""omo workspace status — worktree dirty 计数唯一 SSOT (ISC-46, 治本 E3).

E3 病根: worktree dirty 计数三处不一致 (system.yaml / mof-drift / 实际未量).
本命令为唯一 SSOT: 输出 dirty count + 写 system.yaml::worktree_dirty_count.

用法:
  omo workspace status
"""

from __future__ import annotations

import subprocess

from omo.omo_paths import STATE_SYSTEM_YAML, WORKSPACE_ROOT


def workspace_status() -> int:
    """输出 worktree dirty 计数 + 写 system.yaml SSOT (ISC-46)."""
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    dirty = len(lines)
    staged = sum(1 for ln in lines if ln[0:1] in "MARC")
    unstaged = sum(1 for ln in lines if ln[1:2] in "MARCD")
    untracked = sum(1 for ln in lines if ln.startswith("??"))

    print("📊 workspace status (SSOT, ISC-46 — 治本 E3 worktree 计数不一致):")
    print(f"   dirty files: {dirty}")
    print(f"   staged: {staged}  unstaged: {unstaged}  untracked: {untracked}")
    _sync_system_yaml(dirty)
    return 0


def _sync_system_yaml(dirty_count: int) -> None:
    """写 system.yaml::worktree_dirty_count (SSOT, 让 system.yaml/mof-drift 指针引用此值)."""
    try:
        import yaml

        if not STATE_SYSTEM_YAML.is_file():
            return
        data = yaml.safe_load(STATE_SYSTEM_YAML.read_text(encoding="utf-8")) or {}
        data["worktree_dirty_count"] = dirty_count
        tmp = STATE_SYSTEM_YAML.with_suffix(".yaml.tmp")
        tmp.write_text(
            yaml.dump(
                data, allow_unicode=True, sort_keys=False, default_flow_style=False
            ),
            encoding="utf-8",
        )
        tmp.replace(STATE_SYSTEM_YAML)
        print(f"   ✅ system.yaml::worktree_dirty_count = {dirty_count}")
    except Exception as e:
        print(f"   ⚠️ system.yaml 同步失败: {e}")


def main(argv: list[str] | None = None) -> int:
    args = list(argv or [])
    # 兼容 "omo workspace status" 与 "omo workspace"
    if args and args[0] not in {"status", "--json", "-h", "--help"}:
        pass  # 任意子参数都跑 status (v1 单功能)
    return workspace_status()


if __name__ == "__main__":
    raise SystemExit(main())
