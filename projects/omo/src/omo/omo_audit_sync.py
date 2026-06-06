"""OMO system.yaml 同步器 — 从 kairon_governance.sync_state 迁移.

读源 (SSOT):
  - .omo/tasks/planned/*.yaml (任务状态与 ID)
  - .omo/_knowledge/decisions/*.md (ADR 计数)
  - .omo/_delivery/*.md (交付物计数)
  - .omo/debt/items/*.yaml (debt 状态)
  - .omo/_delivery/phase*-governance-audit-*.md (健康分)
  - projects/kairon/packages/ (包数)

写目标:
  - .omo/state/system.yaml 的特定字段(白名单)

安全机制:
  - 默认 dry-run 模式
  - --apply 才会真写
  - 写前备份 .bak-{timestamp}
  - 只改白名单字段, 不动 goals / debt_weight_items / next_active_tasks

迁移自: kairon_governance.sync_state (P30-W1 GOV-MERGE 落地)
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from omo.omo_paths import (
    DECISIONS_DIR,
    DEBT_ITEMS_DIR,
    DELIVERY_DIR,
    KAIRON_PACKAGES,
    STATE_SYSTEM_YAML,
    TASKS_PLANNED_DIR,
    WORKSPACE_ROOT,
)

# ── 白名单字段 ────────────────────────────────────────────
ALLOWED_FIELDS: frozenset[str] = frozenset(
    {
        "current_phase",
        "current_wave",
        "next_milestone",
        "health_score",
        "health_score_raw",
        "completed_tasks",
        "total_tasks",
        "active_tasks",
        "blocked_tasks",
        "planned_tasks",
        "debt_watchlist_count",
        "debt_gate_count",
        "updated_at",
        "phase28_status",
    }
)

FIELD_TYPES: dict[str, type] = {
    "current_phase": int,
    "current_wave": str,
    "next_milestone": str,
    "health_score": float,
    "health_score_raw": float,
    "completed_tasks": int,
    "total_tasks": int,
    "active_tasks": int,
    "blocked_tasks": int,
    "planned_tasks": int,
    "debt_watchlist_count": int,
    "debt_gate_count": int,
    "updated_at": str,
    "phase28_status": str,
}


@dataclass
class FieldDiff:
    """单个字段的差异."""

    field: str
    old_value: Any
    new_value: Any
    reason: str

    def __str__(self) -> str:
        return f"  {self.field}: {self.old_value!r} -> {self.new_value!r}  ({self.reason})"


# ── 真实状态收集 ─────────────────────────────────────────────


def _parse_task_yaml(path: Path) -> dict[str, str]:
    """极简 YAML 解析(只取顶层 key: value 与 id/status/phase/wave)."""
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*?)\s*$", line)
        if m and m.group(1) in {"id", "status", "phase", "wave"}:
            out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return out


def _collect_task_state() -> dict[str, Any]:
    """从 .omo/tasks/planned/ 收集真实任务统计."""
    if not TASKS_PLANNED_DIR.exists():
        return {
            "total": 0,
            "completed": 0,
            "in_progress": 0,
            "pending": 0,
            "max_phase": 0,
            "current_wave": "W0",
            "tasks": [],
        }
    tasks: list[dict[str, str]] = []
    for f in sorted(TASKS_PLANNED_DIR.glob("*.yaml")):
        info = _parse_task_yaml(f)
        if "id" in info:
            tasks.append(info)
    statuses = [t.get("status", "unknown") for t in tasks]
    completed = sum(1 for s in statuses if s == "completed")
    in_progress = sum(1 for s in statuses if s == "in_progress")
    pending = sum(1 for s in statuses if s in {"pending", "blocked"})
    phases = [int(t["phase"]) for t in tasks if t.get("phase", "").isdigit()]
    max_phase = max(phases) if phases else 0
    current_wave = "W0"
    if tasks:
        phase_tasks = [
            t for t in tasks
            if t.get("phase", "").isdigit() and int(t["phase"]) == max_phase
        ]
        waves = [t.get("wave", "W0") for t in phase_tasks]
        if waves:
            def wave_key(w: str) -> tuple[int, str]:
                m = re.match(r"W(\d+)", w)
                return (int(m.group(1)) if m else 0, w)
            current_wave = sorted(waves, key=wave_key)[-1]
    return {
        "total": len(tasks),
        "completed": completed,
        "in_progress": in_progress,
        "pending": pending,
        "max_phase": max_phase,
        "current_wave": current_wave,
        "tasks": tasks,
    }


def _collect_debt_state() -> dict[str, int]:
    """从 .omo/debt/items/ 收集 debt 状态."""
    if not DEBT_ITEMS_DIR.exists():
        return {"total": 0, "open": 0, "resolved": 0, "closed": 0}
    open_n = resolved_n = closed_n = 0
    total = 0
    for f in DEBT_ITEMS_DIR.glob("*.yaml"):
        total += 1
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        m = re.search(r"^lifecycle_state:\s*(\S+)", text, re.MULTILINE)
        if m:
            state = m.group(1)
            if state == "open":
                open_n += 1
            elif state == "resolved":
                resolved_n += 1
            elif state == "closed":
                closed_n += 1
    return {
        "total": total,
        "open": open_n,
        "resolved": resolved_n,
        "closed": closed_n,
    }


def _collect_audit_data() -> dict[str, Any]:
    """从最新 audit markdown 读出 (score, watchlist_count)."""
    if not DELIVERY_DIR.exists():
        return {"score": None, "watchlist_count": 0}

    def _audit_sort_key(p: Path) -> tuple[int, str]:
        m = re.search(r"-v(\d+)\.md$", p.name)
        version = int(m.group(1)) if m else 0
        return (version, p.name)

    candidates = sorted(
        DELIVERY_DIR.glob("phase*-governance-audit-*.md"),
        key=_audit_sort_key,
        reverse=True,
    )
    for c in candidates:
        try:
            text = c.read_text(encoding="utf-8")
        except OSError:
            continue
        score: float | None = None
        m = re.search(r"\*\*总分[:\s]*([0-9.]+)", text)
        if m:
            try:
                score = float(m.group(1))
            except ValueError:
                pass
        watchlist_count = 0
        watch_section = re.search(
            r"## 3\.\s*新发现潜在债务.*?(?=\n##\s|\Z)",
            text,
            re.DOTALL,
        )
        if watch_section:
            for line in watch_section.group(0).splitlines():
                if re.match(r"^\s*-\s+", line) and "无" not in line and "_(" not in line:
                    watchlist_count += 1
        return {"score": score, "watchlist_count": watchlist_count}
    return {"score": None, "watchlist_count": 0}


def _count_adrs() -> int:
    """ADR 文件数(不含 README/INDEX)."""
    if not DECISIONS_DIR.exists():
        return 0
    return sum(1 for f in DECISIONS_DIR.glob("*.md") if f.stem not in {"README", "INDEX"})


def _count_packages() -> int:
    """kairon 活跃包数."""
    if not KAIRON_PACKAGES.exists():
        return 0
    return sum(
        1 for p in KAIRON_PACKAGES.iterdir() if p.is_dir() and not p.name.startswith(".")
    )


def _find_next_pending_task() -> str | None:
    """找下一个 pending/in_progress 任务(用作 next_milestone 提示)."""
    if not TASKS_PLANNED_DIR.exists():
        return None
    candidates: list[tuple[tuple[int, int, int], str]] = []
    for f in TASKS_PLANNED_DIR.glob("*.yaml"):
        info = _parse_task_yaml(f)
        if info.get("status") not in {"pending", "in_progress", "blocked"}:
            continue
        try:
            phase = int(info.get("phase", "0"))
            m = re.match(r"W(\d+)", info.get("wave", "W0"))
            wave = int(m.group(1)) if m else 0
        except ValueError:
            phase, wave = 0, 0
        candidates.append(((phase, wave, 0), info.get("id", f.stem)))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][1]


def _derive_phase_status() -> dict[str, str]:
    """根据任务完成情况推导 phaseN_status."""
    out: dict[str, str] = {}
    if not TASKS_PLANNED_DIR.exists():
        return out
    phases: set[int] = set()
    for f in TASKS_PLANNED_DIR.glob("*.yaml"):
        info = _parse_task_yaml(f)
        p = info.get("phase", "")
        if p.isdigit():
            phases.add(int(p))
    for phase in sorted(phases):
        statuses: list[str] = []
        for f in TASKS_PLANNED_DIR.glob(f"P{phase}-*.yaml"):
            info = _parse_task_yaml(f)
            statuses.append(info.get("status", "unknown"))
        if not statuses:
            continue
        if all(s == "completed" for s in statuses):
            out[f"phase{phase}_status"] = "completed"
        elif any(s == "in_progress" for s in statuses):
            out[f"phase{phase}_status"] = "active"
        else:
            out[f"phase{phase}_status"] = "active"
    return out


def collect_actual_state() -> dict[str, Any]:
    """从所有 SSOT 源收集真实状态."""
    tasks = _collect_task_state()
    debt = _collect_debt_state()
    audit = _collect_audit_data()
    audit_score = audit["score"]
    next_pending = _find_next_pending_task()
    phase_statuses = _derive_phase_status()
    actual: dict[str, Any] = {
        "current_phase": tasks["max_phase"],
        "current_wave": tasks["current_wave"],
        "next_milestone": (
            f"Phase {tasks['max_phase']} {tasks['current_wave']} — 待启动({next_pending})"
            if next_pending
            else f"Phase {tasks['max_phase']} {tasks['current_wave']} — 全部完成"
        ),
        "health_score": audit_score if audit_score is not None else 0.0,
        "health_score_raw": audit_score if audit_score is not None else 0.0,
        "completed_tasks": tasks["completed"],
        "total_tasks": tasks["total"],
        "active_tasks": tasks["in_progress"] + tasks["pending"],
        "blocked_tasks": sum(
            1 for t in tasks["tasks"] if t.get("status") in {"blocked", "pending"}
        ),
        "planned_tasks": tasks["total"],
        "debt_watchlist_count": audit["watchlist_count"],
        "debt_gate_count": audit["watchlist_count"],
        "updated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    for k, v in phase_statuses.items():
        if k in ALLOWED_FIELDS:
            actual[k] = v
    actual["_meta"] = {
        "audit_score_source": "latest audit MD",
        "adrs": _count_adrs(),
        "packages": _count_packages(),
        "debt_open": debt["open"],
        "debt_resolved": debt["resolved"],
        "debt_closed": debt["closed"],
        "phase_statuses": phase_statuses,
    }
    return actual


# ── system.yaml 读写 ───────────────


def read_system_yaml(path: Path) -> str:
    """读 system.yaml 全文."""
    return path.read_text(encoding="utf-8")


def _get_top_level_value(text: str, key: str) -> str | None:
    """从 system.yaml 文本提取某个顶层 key 的原始 value 行."""
    pattern = rf"^{re.escape(key)}:\s*(.*)$"
    m = re.search(pattern, text, re.MULTILINE)
    return m.group(0) if m else None


def _detect_duplicate_key(text: str, key: str) -> int:
    """检测 system.yaml 中 key 出现次数(>1 = 重复)."""
    pattern = rf"^{re.escape(key)}:"
    return len(re.findall(pattern, text, re.MULTILINE))


def _replace_top_level_key(text: str, key: str, new_value: str) -> str:
    """替换 system.yaml 中某个顶层 key 的 value(保留注释行)."""
    new_line = f"{key}: {new_value}"
    pattern = rf"^{re.escape(key)}:\s*.*$"
    new_text, n = re.subn(pattern, new_line, text, count=1, flags=re.MULTILINE)
    if n == 0:
        if not new_text.endswith("\n"):
            new_text += "\n"
        new_text = new_text + f"{new_line}\n"
    return new_text


def _remove_duplicate_keys(text: str, key: str, keep_last: bool = True) -> str:
    """删除重复 key, 只保留一行."""
    pattern = rf"^{re.escape(key)}:\s*.*$"
    matches = list(re.finditer(pattern, text, re.MULTILINE))
    if len(matches) <= 1:
        return text
    keep_idx = -1 if keep_last else 0
    keep_line = matches[keep_idx].group(0)
    new_text = re.sub(pattern, "", text, flags=re.MULTILINE)
    last = matches[-1]
    new_text = new_text[: last.start()] + keep_line + "\n" + new_text[last.start():]
    return new_text


def diff_with_system_yaml(actual: dict[str, Any], system_text: str) -> list[FieldDiff]:
    """对比 actual 状态与 system.yaml, 产生 FieldDiff 列表."""
    diffs: list[FieldDiff] = []
    for fld in ALLOWED_FIELDS:
        if fld not in actual:
            continue
        new_value = actual[fld]
        existing_line = _get_top_level_value(system_text, fld)
        dup_count = _detect_duplicate_key(system_text, fld)
        if dup_count > 1:
            diffs.append(
                FieldDiff(
                    field=fld,
                    old_value=f"<{dup_count} duplicates>",
                    new_value=new_value,
                    reason=f"detect {dup_count} duplicate keys; will dedupe to last",
                )
            )
            continue
        if existing_line is None:
            diffs.append(
                FieldDiff(
                    field=fld,
                    old_value=None,
                    new_value=new_value,
                    reason="missing in system.yaml; will add",
                )
            )
            continue
        m = re.match(rf"^{re.escape(fld)}:\s*(.*?)\s*$", existing_line)
        old_str = m.group(1) if m else ""
        old_str_clean = old_str.strip().strip('"').strip("'")
        if _values_equal(fld, old_str_clean, new_value):
            continue
        diffs.append(
            FieldDiff(
                field=fld,
                old_value=old_str_clean,
                new_value=new_value,
                reason="actual state differs",
            )
        )
    return diffs


def _values_equal(field: str, old: str, new: Any) -> bool:
    """判断 old (str) 与 new 是否相等, 容忍类型差异."""
    if old == "" or old is None:
        return new in (None, "", 0, 0.0)
    if field in {"health_score", "health_score_raw"}:
        try:
            return abs(float(old) - float(new)) < 0.05
        except (TypeError, ValueError):
            return False
    if field in {
        "current_phase",
        "completed_tasks",
        "total_tasks",
        "active_tasks",
        "blocked_tasks",
        "planned_tasks",
        "debt_watchlist_count",
        "debt_gate_count",
    }:
        try:
            return int(old) == int(new)
        except (TypeError, ValueError):
            return False
    return str(old) == str(new)


# ── 应用修复 ────────────


def apply_diff(
    diffs: list[FieldDiff],
    system_path: Path,
    *,
    apply: bool = False,
) -> str:
    """应用差异. 返回新文本(apply=False 时只返回原文本)."""
    if not diffs:
        return read_system_yaml(system_path)
    text = read_system_yaml(system_path)
    for d in diffs:
        if d.field not in ALLOWED_FIELDS:
            raise PermissionError(f"refused to write non-whitelisted field: {d.field}")
        text = _remove_duplicate_keys(text, d.field, keep_last=True)
        new_value = d.new_value
        if isinstance(new_value, str):
            formatted = f'"{new_value}"'
        elif isinstance(new_value, bool):
            formatted = "true" if new_value else "false"
        else:
            formatted = str(new_value)
        text = _replace_top_level_key(text, d.field, formatted)
    if not apply:
        return text
    backup = system_path.with_suffix(
        f".yaml.bak-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    )
    shutil.copy2(system_path, backup)
    system_path.write_text(text, encoding="utf-8")
    return text


# ── 报告生成 ────────────


def render_report(
    actual: dict[str, Any],
    diffs: list[FieldDiff],
    system_path: Path,
) -> str:
    """生成 Markdown 一致性报告."""
    lines: list[str] = [
        "# system.yaml 同步器报告",
        "",
        f"生成时间: {actual['updated_at']}",
        f"目标文件: `{system_path.relative_to(WORKSPACE_ROOT)}`",
        "",
        "## 1. 真实状态 (SSOT)",
        "",
        "| 字段 | 值 | 源 |",
        "|------|----|----|",
        f"| current_phase | {actual['current_phase']} | .omo/tasks/planned/ 最大 phase |",
        f"| current_wave | {actual['current_wave']} | .omo/tasks/planned/ 最大 phase 内最大 wave |",
        f"| completed_tasks | {actual['completed_tasks']} | tasks/planned/ 状态=completed |",
        f"| total_tasks | {actual['total_tasks']} | tasks/planned/ 文件数 |",
        f"| active_tasks | {actual['active_tasks']} | tasks/planned/ in_progress + pending |",
        f"| planned_tasks | {actual['planned_tasks']} | tasks/planned/ 文件数 |",
        f"| debt_watchlist_count | {actual['debt_watchlist_count']} | debt/items/ lifecycle=open |",
        f"| health_score | {actual['health_score']} | 最新 audit MD **总分 |",
        f"| adrs | {actual['_meta']['adrs']} | decisions/*.md |",
        f"| packages | {actual['_meta']['packages']} | kairon/packages/ |",
    ]
    for k, v in sorted(actual.get("_meta", {}).get("phase_statuses", {}).items()):
        lines.append(f"| {k} | {v} | 任务完成度推导 |")
    lines.extend(["", "## 2. 差异清单", ""])
    if not diffs:
        lines.append("**无差异** — system.yaml 与实际状态一致.")
    else:
        lines.append("| 字段 | 旧值 | 新值 | 理由 |")
        lines.append("|------|------|------|------|")
        for d in diffs:
            lines.append(f"| {d.field} | `{d.old_value}` | `{d.new_value}` | {d.reason} |")
    lines.extend(["", "## 3. 白名单", "", "同步器**只**改以下字段:", ""])
    for f in sorted(ALLOWED_FIELDS):
        lines.append(f"- `{f}`")
    lines.extend([
        "",
        "严禁改动(被显式排除):",
        "- `goals` (人类专属)",
        "- `debt_weight_items` / `resolved_debt_items` (事实沉淀)",
        "- `next_active_tasks` (语义复杂)",
        "- `divergence_*` (其他治理通道)",
        "- 各 `phase*_status` 历史时间戳",
        "",
        "## 4. 安全机制",
        "",
        "- 默认 `--dry-run` 模式",
        "- `--apply` 才真写(写前备份 `.bak-{timestamp}`)",
        "- 非白名单字段一律拒绝(raise PermissionError)",
        "",
    ])
    return "\n".join(lines) + "\n"


# ── 主入口 ──────────


def run_sync(
    *,
    apply: bool = False,
    output: str | Path | None = None,
    system_yaml: Path | None = None,
) -> int:
    """编程式入口(CLI 走这里)."""
    target_yaml = system_yaml if system_yaml is not None else STATE_SYSTEM_YAML
    if not target_yaml.exists():
        print(f"ERROR: {target_yaml} not found")
        return 1
    actual = collect_actual_state()
    text = read_system_yaml(target_yaml)
    diffs = diff_with_system_yaml(actual, text)
    print("=" * 60)
    print("system.yaml 同步器")
    print("=" * 60)
    print(f"模式: {'APPLY' if apply else 'DRY-RUN'}")
    print(f"目标: {target_yaml}")
    print()
    print(f"发现 {len(diffs)} 处差异:")
    if diffs:
        for d in diffs:
            print(str(d))
    else:
        print("  (无差异)")
    print()
    if apply and diffs:
        apply_diff(diffs, target_yaml, apply=True)
        print(f"已应用 {len(diffs)} 处修复(备份: *.yaml.bak-*)")
    elif diffs:
        print("[dry-run] 加 --apply 真正写入")
    else:
        print("system.yaml 已是最新的")
    if output:
        out_path = Path(output)
        report = render_report(actual, diffs, target_yaml)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"报告已写入: {out_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="omo sync — 同步 system.yaml 字段与实际产出(白名单 + dry-run)",
    )
    parser.add_argument("--apply", action="store_true", help="真写(默认 dry-run)")
    parser.add_argument(
        "--system-yaml",
        type=Path,
        default=STATE_SYSTEM_YAML,
        help="system.yaml 路径(默认 .omo/state/system.yaml)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="把 diff 报告写到该路径",
    )
    args = parser.parse_args(argv)
    return run_sync(apply=args.apply, output=args.output, system_yaml=args.system_yaml)


__all__ = (
    "ALLOWED_FIELDS",
    "FIELD_TYPES",
    "FieldDiff",
    "STATE_SYSTEM_YAML",
    "apply_diff",
    "collect_actual_state",
    "diff_with_system_yaml",
    "main",
    "read_system_yaml",
    "render_report",
    "run_sync",
)


if __name__ == "__main__":
    raise SystemExit(main())
