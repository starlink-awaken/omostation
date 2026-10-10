#!/usr/bin/env python3
"""SSOT Write-back 写侧 —— CR-C2G-V3-01 的执行端.

读侧门禁 bin/gac/check-l0-constraints.py::check_c2g_v3_01 要求 done 且含
context_uri 的任务必须 ssot_written_back=true。本脚本是唯一的主动写侧:

  * 扫描 <root>/.omo/tasks/done/*.yaml —— 与门禁读**同一棵树**(repo root).
    旧实现默认 parents[2]/projects/omo → projects/omo/.omo/tasks/done,
    该目录不存在, 于是静默早退(2026-10-10 实证 0 个任务被回写)。
  * 对 done + context_uri + source_docs 的任务, 把回写段追到 source_docs[0]
    的 Markdown 文档底部, 并在任务文件上标记 ssot_written_back。
  * 跳过: 已标记回写; 已显式历史豁免(ssot_writeback_hist, 见门禁 HIST 桶);
    回写目标不是存在的 Markdown(避免损坏 .py/.yaml, 见 5 条历史豁免注解)。

根解析 (ADR-0456 / AGENTS.md §7「根目录是参数, 不是事实」): 跟随当前检出
code_root() —— 与读侧门禁 `Path(__file__).resolve().parents[2]` 同一语义。
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml


def _resolve_target_path(source_docs: list, root: Path) -> Path | None:
    """把 source_docs[0] 解析为绝对路径; 非 Markdown 或不存在 → None(不可回写)."""
    if not source_docs:
        return None
    raw = str(source_docs[0])
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root / candidate
    name = candidate.name.lower()
    if not name.endswith((".md", ".markdown")):
        return None
    if not candidate.is_file():
        return None
    return candidate


def extract_ssot_writeback(omo_dir: Path) -> int:
    """对 <omo_dir>/tasks/done 下可回写的 done+context_uri 任务执行 SSOT 回写.

    返回实际回写(标记 ssot_written_back)的任务数。幂等: 已标记或已历史豁免的
    任务均跳过。不会修改入仓 .py/.yaml 文件 —— 非 Markdown 目标直接跳过。
    """
    done_dir = omo_dir / "tasks" / "done"
    if not done_dir.is_dir():
        return 0

    written = 0
    for task_file in sorted(done_dir.glob("*.yaml")):
        try:
            with open(task_file, encoding="utf-8") as f:
                task = yaml.safe_load(f)
        except Exception:
            continue

        if not isinstance(task, dict):
            continue

        # 门禁要求 done + context_uri. status 缺省视为非 done, 跳过.
        if str(task.get("status", "")).lower() != "done":
            continue
        context_uri = task.get("context_uri")
        if not context_uri:
            continue

        # 幂等 / 历史豁免(HIST 桶已满足门禁, 回写目标是坏目标或不存在).
        if task.get("ssot_written_back") is True:
            continue
        hist = task.get("ssot_writeback_hist")
        if isinstance(hist, dict) and hist.get("annotated_at") and hist.get("reason"):
            continue

        # context_uri 的原始文档 (source_docs[0]) 必须是存在的 Markdown,
        # 否则跳过 —— 不会为了置 flag 而损坏 .py/.yaml(门禁注解逐条记录过).
        source_file = _resolve_target_path(task.get("source_docs", []), omo_dir.parent)
        if source_file is None:
            print(
                f"⚠️ skip {task.get('id', task_file.name)}: "
                f"source_docs[0] 非存在的 Markdown, 不可回写"
            )
            continue

        try:
            # 追加回写段到原始 Markdown 文档底部(不重写全文).
            with open(source_file, "a", encoding="utf-8") as f:
                f.write(f"\n\n### OMO SSOT Write-back: {task.get('id', '?')}\n")
                f.write(f"> 任务 `{task.get('title', '')}` 已在 OMO 稳态区被标记为 Done。\n")
                f.write(f"> 变更详情见卡片 {task.get('id', '?')} 或其对应的交付记录。\n")
                f.write(f"> 原始 context_uri: `{context_uri}`\n")

            # 标记任务已回写 —— 读侧门禁据此放行.
            task["ssot_written_back"] = True
            with open(task_file, "w", encoding="utf-8") as f:
                yaml.dump(task, f, allow_unicode=True, sort_keys=False)
            written += 1
            print(f"✅ SSOT Write-back applied for {task.get('id')} -> {source_file.name}")
        except Exception as e:
            print(f"⚠️ Failed to write back SSOT for {task.get('id')}: {e}")

    return written


def main() -> int:
    # 根解析: 跟随当前检出 (与门禁同一棵树). bin/lib/repo_root 的 sys.path
    # 引导与 bin/ssot/current-state-coherence.py 等脚本一致.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
    from repo_root import code_root  # noqa: E402

    root = code_root()
    print(f"=== SSOT Write-back @ {root} ===")
    written = extract_ssot_writeback(root / ".omo")
    print(f"---\n回写完成: {written} 个任务")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
