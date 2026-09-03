#!/usr/bin/env python3
"""AUTO-FIX 自动修复环完善 (差距治理 S5).

背景 (复盘实证): 治理闭环 E-D-P-C 缺 F (修复环) — 检测到漂移只报告不修复,
agent 手动补派生文档/登记脚本, 周而复始. post-commit-sync-check 只覆盖
"子模块指针变更" 一种触发, SSOT 源变更 (agent-workflows/mof-capabilities)
未触发自动投影时缺少统一的检测→修复闭环.

本脚本: 统一的"检测→分类→可修复漂移"闭环. 每类漂移都给出:
  - 检测: 是否漂移
  - 分类: DERIVED-STALE / PATH-DRIFT / ORPHAN-SCRIPT / SSOT-UNSYNCED
  - 修复: 干跑 (默认) 给出修复命令; --apply 应用可安全自动修复项

可安全自动修复 (--apply):
  DERIVED-STALE : SSOT 源变更 → 派生文档未同步 → make sync-all-docs
  ORPHAN-SCRIPT : bin/ 新脚本未登记 → script-registry.py register --auto
需要人工 (只报告, 不 --apply):
  PATH-DRIFT    : 注册表 path 指向缺失实现 → 需判断是删除还是迁移 (S1 案例:
                  omo_lint_projection.py → omo_lint.py::subcommand)
  SSOT-UNSYNCED : 派生文档残缺 (totals=0) → CI 完整环境重生成, 本地勿提交

用法:
    python3 bin/gac/auto-fix-loop.py            # 干跑: 检测 + 分类 + 修复建议
    python3 bin/gac/auto-fix-loop.py --apply    # 应用可安全自动修复项
    python3 bin/gac/auto-fix-loop.py --json     # JSON 输出
    python3 bin/gac/auto-fix-loop.py --scope impl|docs|registry  # 单面

SSOT:  .omo/_truth/registry/mof-capabilities.yaml (注册表)
       docs/generated/capability-registry.yaml (派生投影)
返回: 0 = 无漂移或已修复; 1 = 存在需人工漂移 (报告但不自动改).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]

# SSOT 源 → 派生文档映射 (PROJ-FORCE 契约)
SSOT_DERIVED_MAP: dict[str, tuple[str, ...]] = {
    ".omo/_truth/registry/agent-workflows.yaml": ("docs/generated/",),
    ".omo/_truth/registry/mof-capabilities.yaml": ("docs/generated/capability-registry.yaml",),
    ".omo/_truth/registry/profiles.yaml": ("docs/generated/",),
}

# 派生文档 (GEN-FORCE 保护生成物, 检查完整性)
DERIVED_TARGETS = (
    "docs/generated/capability-registry.yaml",
    "projects/cockpit/CAPABILITY-MAP.md",
    "docs/CLI-REFERENCE.md",
    "docs/INDEX-MCP.md",
)

# 注册表 SSOT path
MOF_CAPABILITIES = WORKSPACE / ".omo" / "_truth" / "registry" / "mof-capabilities.yaml"


class Drift:
    __slots__ = ("kind", "severity", "message", "fix_cmd", "auto_fixable")

    def __init__(self, kind: str, severity: str, message: str, fix_cmd: str = "", auto_fixable: bool = False) -> None:
        self.kind = kind
        self.severity = severity
        self.message = message
        self.fix_cmd = fix_cmd
        self.auto_fixable = auto_fixable

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "message": self.message,
            "fix_cmd": self.fix_cmd,
            "auto_fixable": self.auto_fixable,
        }


def _load_yaml(path: Path) -> dict | None:
    """加载 YAML (multi-doc safe_load_all, 取最后非空 doc)."""
    try:
        import yaml

        if not path.exists():
            return None
        docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        for doc in reversed(docs):
            if isinstance(doc, dict) and doc:
                return doc
        return {}
    except Exception:
        return None


def _git_diff_ssot() -> list[str]:
    """检查最近 commit 是否触碰 SSOT 源 (HEAD vs HEAD~1)."""
    try:
        r = subprocess.run(
            ["git", "diff", "HEAD~1", "HEAD", "--name-only"],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return [line.strip() for line in r.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def detect_drifts() -> list[Drift]:
    """检测全部可识别漂移."""
    drifts: list[Drift] = []

    # 1. DERIVED-STALE: SSOT 源变更 → 派生文档未同步
    changed = _git_diff_ssot()
    touched_ssot = [p for p in changed if p in SSOT_DERIVED_MAP]
    if touched_ssot:
        for ssot in touched_ssot:
            drifts.append(
                Drift(
                    "DERIVED-STALE",
                    "warning",
                    f"SSOT 源 {ssot} 已变更, 派生文档可能未同步",
                    "make sync-all-docs",
                    auto_fixable=True,
                )
            )

    # 2. PATH-DRIFT: 注册表 path 指向缺失实现 (删除防腐相关)
    reg = _load_yaml(MOF_CAPABILITIES)
    if isinstance(reg, dict):
        missing: list[str] = []
        for section in ("tools", "omo_tools", "p74_tools"):
            for cap, meta in (reg.get(section) or {}).items():
                if isinstance(meta, dict) and meta.get("path") and "::" not in str(meta["path"]):
                    cand = WORKSPACE / str(meta["path"])
                    if not cand.exists():
                        py = WORKSPACE / f"{str(meta['path'])}.py"
                        if not py.exists():
                            missing.append(f"{cap} → {meta['path']}")
        if missing:
            drifts.append(
                Drift(
                    "PATH-DRIFT",
                    "error",
                    f"注册表 path 指向缺失实现 ({len(missing)}): {'; '.join(missing[:5])} "
                    f"(需判断删除/迁移, S1 案例: omo_lint_projection → omo_lint.py::cmd)",
                    "bin/gac/check-capability-ownership.py",
                    auto_fixable=False,
                )
            )

    # 3. ORPHAN-SCRIPT: bin/ 新脚本未登记 (script-registry)
    try:
        reg_script = WORKSPACE / "bin" / "ssot" / "script-registry.py"
        if reg_script.exists():
            r = subprocess.run(
                [sys.executable, str(reg_script), "validate"],
                cwd=WORKSPACE,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if r.returncode != 0:
                # 提取未登记脚本列表 (从输出)
                orphans = [line.strip().replace("- ", "") for line in r.stdout.splitlines() if line.strip().startswith("- ")]
                if orphans:
                    drifts.append(
                        Drift(
                            "ORPHAN-SCRIPT",
                            "warning",
                            f"bin/ 新脚本未登记 ({len(orphans)}): {'; '.join(orphans[:5])}",
                            f"python3 bin/ssot/script-registry.py register {' '.join(orphans)}",
                            auto_fixable=True,
                        )
                    )
    except Exception:
        pass

    # 4. FRONTMATTER-MISSING: 探测 Markdown 缺失 frontmatter
    try:
        doc_check = WORKSPACE / "bin" / "ssot" / "doc-governance-check.py"
        if doc_check.exists():
            r = subprocess.run(
                [sys.executable, str(doc_check), "--strict"],
                cwd=WORKSPACE,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            missing_files = set()
            for line in r.stdout.splitlines():
                if "missing_frontmatter" in line and "does not start with YAML" in line:
                    missing_files.add(line.split(":")[0])
            if missing_files:
                files_str = " ".join(list(missing_files)[:10]) # fix up to 10 at a time
                drifts.append(
                    Drift(
                        "FRONTMATTER-MISSING",
                        "warning",
                        f"检测到 {len(missing_files)} 个文档缺失 Frontmatter (如: {list(missing_files)[0]})",
                        f"python3 bin/gac/fix-frontmatter.py {files_str}",
                        auto_fixable=True,
                    )
                )
    except Exception:
        pass

    # 5. CELL-STALE: AGE-v2 Cell 状态文件有过期条目
    try:
        cell_state_file = WORKSPACE / ".omo" / "state" / "agent-cell" / "cell_states.json"
        if cell_state_file.exists():
            import json as _json
            from datetime import datetime as _dt
            from datetime import timedelta as _td
            from datetime import timezone as _tz
            data = _json.loads(cell_state_file.read_text())
            now = _dt.now(UTC)
            stale_count = 0
            for state in data.values():
                saved = state.get("saved_at", "")
                if saved:
                    try:
                        ts = _dt.fromisoformat(str(saved).replace("Z", "+00:00"))
                        if (now - ts).total_seconds() > 86400:  # >24h
                            stale_count += 1
                    except (ValueError, TypeError):
                        pass
            if stale_count > 0:
                drifts.append(
                    Drift(
                        "CELL-STALE",
                        "info",
                        f"Cell 状态文件有 {stale_count} 个过期条目 (>24h)",
                        "python3 -c \"from omo.resident.cell_state import CellStateManager; CellStateManager().cleanup_stale(max_age_hours=24)\"",
                        auto_fixable=True,
                    )
                )
    except Exception:
        pass

    return drifts


def apply_fix(drift: Drift) -> tuple[bool, str]:
    """应用可安全自动修复的漂移. 返回 (success, output)."""
    if not drift.auto_fixable:
        return False, "需人工 (不自动应用)"
    try:
        if drift.kind == "DERIVED-STALE":
            r = subprocess.run(
                ["make", "sync-all-docs"],
                cwd=WORKSPACE,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            return r.returncode == 0, (r.stdout or r.stderr)[-300:]
        if drift.kind in ("ORPHAN-SCRIPT", "FRONTMATTER-MISSING"):
            cmd = drift.fix_cmd.split()
            r = subprocess.run(cmd, cwd=WORKSPACE, capture_output=True, text=True, timeout=60, check=False)
            return r.returncode == 0, (r.stdout or r.stderr)[-300:]
        if drift.kind == "CELL-STALE":
            # 清理过期 Cell 状态
            try:
                from omo.resident.cell_state import CellStateManager
                cleaned = CellStateManager().cleanup_stale(max_age_hours=24)
                return True, f"已清理 {cleaned} 个过期 Cell 状态"
            except ImportError:
                return False, "omo.resident.cell_state 不可用"
        return False, f"未知可修复类别: {drift.kind}"
    except Exception as exc:
        return False, str(exc)


def main() -> int:
    ap = argparse.ArgumentParser(description="AUTO-FIX: 漂移检测→分类→修复闭环")
    ap.add_argument("--apply", action="store_true", help="应用可安全自动修复项 (默认干跑)")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    drifts = detect_drifts()
    applied: list[dict] = []
    remaining: list[Drift] = []

    if args.apply:
        for d in drifts:
            if d.auto_fixable:
                ok, out = apply_fix(d)
                applied.append({**d.to_dict(), "applied": ok, "output": out})
                if ok:
                    continue
            remaining.append(d)
    else:
        remaining = drifts

    if args.json:
        print(
            json.dumps(
                {
                    "drifts": [d.to_dict() for d in remaining],
                    "applied": applied,
                    "count": len(remaining) + len(applied),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        if not drifts:
            print("✅ AUTO-FIX: 无漂移")
        for d in remaining:
            marker = "🟡" if d.auto_fixable else "🔴"
            print(f"{marker} [{d.kind}:{d.severity}] {d.message}")
            if d.fix_cmd:
                print(f"    修复: {d.fix_cmd}")
        for a in applied:
            status = "已修复" if a["applied"] else "失败"
            print(f"🟢 [{a['kind']}] {status}: {a['message']}")
        if not args.apply and drifts:
            print("\n提示: 加 --apply 应用可安全自动修复项 (DERIVED-STALE/ORPHAN-SCRIPT)")

    # 退出: 存在 error 级 (PATH-DRIFT) 需人工 → 1; 其余 0
    has_error = any(d.severity == "error" for d in remaining)
    return 1 if has_error else 0


if __name__ == "__main__":
    sys.exit(main())
