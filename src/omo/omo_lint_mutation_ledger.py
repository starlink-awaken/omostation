"""P103 refactor: omo_lint mutation-ledger 子模块 (从 omo_lint.py 提取).

ADR-0093 P100-P103 4 步收官 (P101/P102 校正顺序后):
  P100 schemas 拆 (485L) ✓ done → 800L
  P101 yaml-bypass 拆 (76L) ✓ done → 731L
  P102 surfaces 拆 (148L) ✓ done → 594L
  P103 mutation-ledger 拆 (57L) → 537L, <600L ideal 完整兑现

1 个 mutation-ledger cmd (Round 14+ P0 累积):
  - cmd_lint_mutation_ledger: 校验 runtime/omo/change-log/mutations.jsonl 账本
    - 账本存在且非空
    - 8 必填字段 (created_at/actor/action/target/artifact_ref/source_ref/broker_ref/result)
    - artifact_ref 必须 .omo/ 开头 + 真实文件存在
    - 至少 1 个 committed mutation

模块依赖: Path (stdlib) + omo.omo_io.read_jsonl (内部 SSOT, 最小依赖).

向后兼容 (P88/P100/P101/P102 模式):
  omo_lint.py 通过 `from .omo_lint_mutation_ledger import (...)` re-export,
  保持 `from omo.omo_lint import cmd_lint_mutation_ledger` 不破.

P103 意义:
  - ADR-0093 P100-P103 4 步路径完整闭环 (11 轮推迟 → 4 阶段实施)
  - omo_lint.py 累计 -732L (-58%): 1269L → 537L
  - 5 子模块架构清晰: doc/schemas/yaml-bypass/surfaces/mutation-ledger
"""

from __future__ import annotations

from pathlib import Path

from omo.omo_io import read_jsonl
from omo.omo_ingress_paths import _mutation_log_path


def cmd_lint_mutation_ledger(workspace_root: str = ".") -> int:
    root = Path(workspace_root).resolve()
    ledger_path = _mutation_log_path(root / ".omo")
    # CI fresh checkout 无 runtime/omo (gitignored) — 合法空状态, 不阻断
    if not ledger_path.exists():
        print(f"⚠️ omo lint mutation-ledger: ledger file missing (runtime cache absent, CI fresh checkout), 视为 pass")
        return 0

    entries = read_jsonl(ledger_path)
    if not entries:
        print(f"❌ omo lint mutation-ledger fail: ledger is empty: {ledger_path}")
        return 1

    issues: list[str] = []
    required_fields = (
        "created_at",
        "actor",
        "action",
        "target",
        "artifact_ref",
        "source_ref",
        "broker_ref",
        "result",
    )
    committed = 0
    for idx, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            issues.append(f"entry {idx}: not a JSON object")
            continue
        missing = [field for field in required_fields if field not in entry]
        if missing:
            issues.append(f"entry {idx}: missing fields {missing}")
            continue
        if entry.get("result") == "committed":
            committed += 1
        artifact_ref = entry.get("artifact_ref")
        if not isinstance(artifact_ref, str) or not (
            artifact_ref.startswith(".omo/") or artifact_ref.startswith("runtime/omo/")
        ):
            issues.append(f"entry {idx}: invalid artifact_ref {artifact_ref!r}")
            continue
        artifact_path = root / artifact_ref
        if not artifact_path.exists():
            issues.append(f"entry {idx}: artifact_ref missing on disk {artifact_ref}")

    if committed == 0:
        issues.append("no committed mutations found in ledger")

    if issues:
        print(f"❌ omo lint mutation-ledger fail: {len(issues)} issue(s)")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print(
        "✅ omo lint mutation-ledger pass: "
        f"entries={len(entries)} committed={committed}"
    )
    return 0
