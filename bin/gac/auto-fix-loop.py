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

Closeout-branch skip (A3, FORWARD-PLAN §A3):
  - 当前分支匹配 closeout 模式 (含 closeout/retro/ledger/Ax-/bet-execution/t10-*)
    时, 跳过 FRONTMATTER-MISSING 对 .omo/_knowledge/retros/*.md 的修复
  - 强制启用: SKIP_FIX_LOOP_BRANCH=1 环境变量
  - 原因: closeout PR 携带 retro 文件时, auto-fix 修改 last-reviewed 会产生
    与本地 ledger 不同步的额外 diff (复盘实证 2026-09, batch 31 教训 PITFALL-COO-005)

Retro field expansion (B1.1, 2026-09-20):
  - 新增 2 类 drift: FRONTMATTER-MISSING-FIELD (字段缺失),
    INVALID-METADATA (字段值不在 allowed set)
  - 对偶 RETRO-SKIPPED 变体: closeout 模式同样跳过 retro 路径
  - 修复入口: fix-frontmatter.py --batch .  (单次扫全仓修字段映射)

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
import os
import re
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

# A3: closeout-branch skip 配置.
# 分支名含以下任一模式 → 跳过 FRONTMATTER-MISSING 对 retro 路径的修复.
CLOSEOUT_BRANCH_PATTERNS = (
    r"-closeout\b",
    r"-retro\b",
    r"-ledger\b",
    r"-a[1-9]-",
    r"^agent/governance-agent/a[1-9]-",
    r"bet-execution-",
)

# retro 路径前缀 (FRONTMATTER-MISSING drift 跳过范围).
RETRO_PATH_PREFIXES = (
    ".omo/_knowledge/retros/",
    ".omo/_knowledge/retrospectives/retros/",
)


def _git_current_branch() -> str:
    """读取当前分支名 (空字符串 = 失败, 不抛)."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def is_closeout_branch(branch: str | None = None) -> bool:
    """判断当前分支是否为 closeout 类 (应跳过 retro frontmatter 修复).

    Returns True if:
      - SKIP_FIX_LOOP_BRANCH=1 env var set, OR
      - branch matches one of CLOSEOUT_BRANCH_PATTERNS
    """
    if os.environ.get("SKIP_FIX_LOOP_BRANCH", "").strip() in ("1", "true", "yes"):
        return True
    if branch is None:
        branch = _git_current_branch()
    if not branch or branch == "HEAD":
        return False
    for pat in CLOSEOUT_BRANCH_PATTERNS:
        if re.search(pat, branch):
            return True
    return False


def is_retro_path(path: str) -> bool:
    """判断文件路径是否属于 retro 类 (受 A3 skip 保护)."""
    for prefix in RETRO_PATH_PREFIXES:
        if path.startswith(prefix) or f"/{prefix}" in path:
            return True
    return False


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
            missing_field_files = set()
            invalid_meta_files = set()
            for line in r.stdout.splitlines():
                if "missing_frontmatter" in line and "does not start with YAML" in line:
                    missing_files.add(line.split(":")[0])
                elif "missing_frontmatter" in line and "missing required frontmatter fields" in line:
                    # B1.1: 收集字段缺失类 (frontmatter 存在但缺键)
                    missing_field_files.add(line.split(":")[0])
                elif "invalid_metadata" in line and (
                    "status must be one of" in line or "lifecycle must be one of" in line
                ):
                    # B1.1: 收集 invalid_metadata 类 (字段值不在 allowed set)
                    invalid_meta_files.add(line.split(":")[0])
            # A3: closeout branch 上跳过 retro 路径的 auto-fix
            closeout_mode = is_closeout_branch()
            if closeout_mode:
                retro_invalid = {f for f in invalid_meta_files if is_retro_path(f)}
                if retro_invalid:
                    drifts.append(
                        Drift(
                            "INVALID-METADATA-RETRO-SKIPPED",
                            "info",
                            f"closeout-branch 跳过 {len(retro_invalid)} 个 retro "
                            f"文件的 invalid_metadata 修复: "
                            f"{', '.join(sorted(retro_invalid)[:3])}",
                            "manual: 合并后跑 fix-frontmatter.py --batch",
                            auto_fixable=False,
                        )
                    )
                invalid_meta_files -= retro_invalid
                retro_missing_field = {f for f in missing_field_files if is_retro_path(f)}
                if retro_missing_field:
                    drifts.append(
                        Drift(
                            "FRONTMATTER-MISSING-FIELD-RETRO-SKIPPED",
                            "info",
                            f"closeout-branch 跳过 {len(retro_missing_field)} 个 retro "
                            f"文件的 field 补全: "
                            f"{', '.join(sorted(retro_missing_field)[:3])}",
                            "manual: 合并后跑 fix-frontmatter.py --batch",
                            auto_fixable=False,
                        )
                    )
                missing_field_files -= retro_missing_field
                retro_skipped = {f for f in missing_files if is_retro_path(f)}
                non_retro = missing_files - retro_skipped
                if retro_skipped:
                    drifts.append(
                        Drift(
                            "FRONTMATTER-MISSING-RETRO-SKIPPED",
                            "info",
                            f"closeout-branch 跳过 {len(retro_skipped)} 个 retro "
                            f"文件的 auto-fix (避免与 ledger 同步冲突): "
                            f"{', '.join(sorted(retro_skipped)[:3])}",
                            "manual: 合并后再统一 batch 处理",
                            auto_fixable=False,
                        )
                    )
                missing_files = non_retro
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
            # B1.1: missing required fields drift
            if missing_field_files:
                sample = list(missing_field_files)[:10]
                drifts.append(
                    Drift(
                        "FRONTMATTER-MISSING-FIELD",
                        "warning",
                        f"检测到 {len(missing_field_files)} 个文档 frontmatter 缺字段 "
                        f"(如: {sample[0]})",
                        "python3 bin/gac/fix-frontmatter.py --batch .",
                        auto_fixable=True,
                    )
                )
            # B1.1: invalid metadata drift (status/lifecycle 不在 allowed set)
            if invalid_meta_files:
                sample = list(invalid_meta_files)[:10]
                drifts.append(
                    Drift(
                        "INVALID-METADATA",
                        "warning",
                        f"检测到 {len(invalid_meta_files)} 个文档 metadata 不合规 "
                        f"(如: {sample[0]})",
                        "python3 bin/gac/fix-frontmatter.py --batch .",
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
        if drift.kind in (
            "ORPHAN-SCRIPT",
            "FRONTMATTER-MISSING",
            "FRONTMATTER-MISSING-FIELD",
            "INVALID-METADATA",
        ):
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
        if is_closeout_branch():
            print(
                f"ℹ️  closeout-branch mode (A3): FRONTMATTER-MISSING on retro paths 跳过"
            )
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
