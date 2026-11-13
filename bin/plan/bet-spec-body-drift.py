#!/usr/bin/env python3
"""BET 正文漂移探测 —— 对 done BET 的 spec 绑定做「只报不改」的观察。

用法:
  python3 bin/plan/bet-spec-body-drift.py                 # 报告, exit 0
  python3 bin/plan/bet-spec-body-drift.py --json
  python3 bin/plan/bet-spec-body-drift.py --fail-on drift  # 有 body_drift 才 exit 1

## 为什么需要它

`bin/plan/bet-ledger.py` 的 spec 摘要校验写在 `if bet.get("status") != "done"`
分支里 —— done BET 被刻意豁免，于是 329/451 条 `content_digest` 陈旧从不报错
（BET-DONE-SPEC-DIGEST-MASS-STALENESS）。本工具不改变那个语义，只把「done BET
的 spec 从绑定之后有没有被改过」这件事**看见**。

## 判据

对每条 done BET 的 `accepted_specifications[0]`：

1. 沿 `git log --format=%H -- <spec>` 逐提交取内容算 sha256，
   找到与 `content_digest` 相等的那一版 —— 即「绑定时的内容」。
2. **找不到** ⇒ `unverifiable`：声明摘要在该 spec 的历史里从未出现
   （16 条实测，见 BET-DONE-SPEC-DIGEST-UNVERIFIABLE-ON-MAIN）。
3. 找到 ⇒ 比较**正文**（剥掉 frontmatter、丢弃空行、行尾去空白）：
   - 相同 ⇒ `mechanical_only`：漂移全在 frontmatter / 空行上，正文没动
     （309/313 实测 —— #4328 那类批量 frontmatter 补丁）。
   - 不同 ⇒ `body_drift`：正文真的改了，**应当被抓**（4 条实测）。

「正文」的定义是三条归一化口径（`body_lines_only` / `fm_semantic+body_lines` /
`body_collapsed_ws`）在同一次实测里读数完全一致，所以取最简单的那条。

**不写任何东西**：不改台账、不改 spec、不改 digest。观察结果落 JSON 或 stdout。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
LEDGER = WORKSPACE / "docs/plans/3y-bet-ledger.yaml"
SPEC_REF_PREFIX = "repo://"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(WORKSPACE), *args], capture_output=True, text=True, check=False
    ).stdout


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _split_frontmatter(text: str) -> str:
    """返回正文（剥掉 frontmatter）。没有 frontmatter 就原样返回。"""
    m = re.match(r"^---\n.*?\n---\n", text, re.DOTALL)
    return text[m.end():] if m else text


def _normalize_body(text: str) -> str:
    """正文归一化：剥 frontmatter、丢空行、行尾去空白。"""
    lines = [ln.rstrip() for ln in _split_frontmatter(text).splitlines() if ln.strip()]
    return "\n".join(lines)


def find_attestation_commit(spec_rel: str, declared: str) -> tuple[str, bytes] | None:
    """找到 spec 内容 sha256 == declared 的最近一个提交。"""
    log = _git("log", "--format=%H", "--", spec_rel).split()
    for commit in log:
        proc = subprocess.run(
            ["git", "-C", str(WORKSPACE), "show", f"{commit}:{spec_rel}"],
            capture_output=True,
            check=False,
        )
        if proc.returncode == 0 and _sha256(proc.stdout) == declared:
            return commit, proc.stdout
    return None


def collect() -> dict:
    ledger = yaml.safe_load(LEDGER.read_text(encoding="utf-8"))
    bets = ledger["bets"] if isinstance(ledger, dict) else ledger
    if isinstance(bets, dict):
        bets = list(bets.values())

    rows: list[dict] = []
    for bet in bets:
        if bet.get("status") != "done":
            continue
        specs = bet.get("accepted_specifications") or []
        if not isinstance(specs, list) or len(specs) != 1:
            continue
        binding = specs[0]
        if not isinstance(binding, dict):
            continue
        bet_id = bet.get("id")
        declared = binding.get("content_digest")
        ref = binding.get("spec_ref") or ""
        if not isinstance(declared, str) or not declared.startswith("sha256:"):
            rows.append({"bet_id": bet_id, "state": "binding_invalid", "spec_ref": ref})
            continue
        if not ref.startswith(SPEC_REF_PREFIX):
            rows.append({"bet_id": bet_id, "state": "spec_ref_invalid", "spec_ref": ref})
            continue
        rel = ref.removeprefix(SPEC_REF_PREFIX)
        path = WORKSPACE / rel
        if not path.is_file():
            rows.append({"bet_id": bet_id, "state": "spec_missing", "spec_ref": rel})
            continue

        found = find_attestation_commit(rel, declared)
        if found is None:
            rows.append({"bet_id": bet_id, "state": "unverifiable", "spec_ref": rel})
            continue
        commit, old_bytes = found
        new_bytes = path.read_bytes()
        if _normalize_body(old_bytes.decode("utf-8", "replace")) == _normalize_body(
            new_bytes.decode("utf-8", "replace")
        ):
            rows.append(
                {"bet_id": bet_id, "state": "mechanical_only", "spec_ref": rel, "attested_at": commit}
            )
        else:
            rows.append(
                {
                    "bet_id": bet_id,
                    "state": "body_drift",
                    "spec_ref": rel,
                    "attested_at": commit,
                }
            )
    return {"total": len(rows), "rows": rows}


def summarize(result: dict) -> dict:
    counts: dict[str, int] = {}
    for row in result["rows"]:
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    return {"total": result["total"], "counts": dict(sorted(counts.items()))}


def main() -> int:
    parser = argparse.ArgumentParser(description="BET 正文漂移探测 (只报不改)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--fail-on",
        choices=["drift", "any"],
        default=None,
        help="drift=有 body_drift 才 exit 1; any=有任何非 mechanical_only 就 exit 1。缺省只报不改",
    )
    args = parser.parse_args()

    result = collect()
    summary = summarize(result)

    if args.json:
        print(json.dumps({"summary": summary, "rows": result["rows"]}, ensure_ascii=False, indent=2))
    else:
        print(f" BET 正文漂移探测：{summary['total']} 条 done BET spec 绑定")
        for state, count in summary["counts"].items():
            print(f"   {state:>16}: {count}")
        for row in result["rows"]:
            if row["state"] in ("body_drift", "unverifiable", "spec_missing", "binding_invalid", "spec_ref_invalid"):
                extra = f"  @{row['attested_at'][:9]}" if row.get("attested_at") else ""
                print(f"     [{row['state']}] {row['bet_id']}  {row.get('spec_ref', '')}{extra}")

    if args.fail_on == "drift" and summary["counts"].get("body_drift"):
        return 1
    if args.fail_on == "any" and any(
        k != "mechanical_only" for k in summary["counts"]
    ):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
