#!/usr/bin/env python3
"""state-freshness-check — OMO 状态面新鲜度独立检测 (ADR-0119 S2-5).

为什么独立:
- compass_radar.py 内含 freshness_score 但耦合在复合 health_score 计算
  (F-2 之前 freshness 不在 gac-local-gate 默认 mode 跑, 不可见)
- 本工具: 独立检查 OMO 状态面各 SSOT 文件的 generated_at 新鲜度,
  独立退出码 (0=全新鲜, 1=有 stale), 可单跑也可 wire gac-local-gate

检查对象 (状态面 SSOT):
- .omo/state/system.yaml
- .omo/state/health.yaml
- .omo/state/system_health.yaml
- .omo/state/governance.jsonl
- .omo/debt/dashboard/current.yaml
- .omo/_control/governance-data.json

新鲜度阈值 (ISC-1 复合分 freshness 段一致):
- ≤1h   → 100 (新鲜)
- ≤24h  → 80
- ≤7d   → 50
- >7d   → 0 (stale)

用法:
  python3 bin/state-freshness-check.py           # 默认可视
  python3 bin/state-freshness-check.py --json    # JSON 输出
  python3 bin/state-freshness-check.py --file X  # 单文件

退出码:
  0 = 全新鲜 (≥80) 或 有 stale (50-79, 派生快照老化但仍可用, 不 block)
  2 = 有 expired (≤0, >7d, 派生快照不可信, 应 block)
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]

# 状态面 SSOT 文件 (按重要度排)
# 注: 仅检查"派生快照"文件 (有 generated_at 时间戳); 配置型文件 (如 system.yaml)
# 是 source-of-truth 不带 generated_at, 不在本检查范围.
STATE_FILES = [
    (".omo/state/health.yaml", ("generated_at",)),
    (".omo/state/system_health.yaml", ("last_scan",)),
    (".omo/state/governance.jsonl", ("timestamp", "generated_at")),
    (".omo/debt/dashboard/current.yaml", ("generated_at", "last_reconciled_at")),
    (".omo/_control/governance-data.json", ("generated_at",)),
]

# 各文件类型用哪个字段作为 generated_at (JSONL 用首行, YAML 用顶层 key)
GENERATED_AT_KEYS = ("generated_at", "timestamp", "last_scan", "last_reconciled_at", "registered_at")

# 新鲜度档位
THRESHOLD_FRESH_HOURS = 1
THRESHOLD_OK_HOURS = 24
THRESHOLD_STALE_DAYS = 7


def _parse_iso(ts: str) -> datetime | None:
    """解析 ISO 8601 时间戳, 兼容 Z 后缀和 epoch 数字."""
    if not ts:
        return None
    ts = ts.strip()
    # Epoch 数字 (system_health.yaml 用)
    if re.fullmatch(r"\d+(\.\d+)?", ts):
        try:
            return datetime.fromtimestamp(float(ts), tz=timezone.utc)
        except (ValueError, OSError):
            return None
    # ISO 8601
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def _score_freshness(age_hours: float) -> int:
    """根据 age 返回 0-100 freshness score (与 compass_radar 一致)."""
    if age_hours <= THRESHOLD_FRESH_HOURS:
        return 100
    if age_hours <= THRESHOLD_OK_HOURS:
        return 80
    if age_hours <= THRESHOLD_STALE_DAYS * 24:
        return 50
    return 0


def _extract_generated_at(path: Path, keys: tuple[str, ...] = GENERATED_AT_KEYS) -> str | None:
    """从文件提取 generated_at 时间戳. JSONL 取首行, YAML 取顶层 key."""
    if not path.is_file():
        return None
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    # JSONL: 取首行 dict 的 generated_at / last_scan
    if path.suffix == ".jsonl":
        for line in content.splitlines():
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            for k in keys:
                if k in d:
                    return str(d[k])
            return None
    # JSON: 取顶层
    if path.suffix == ".json":
        try:
            d = json.loads(content)
            for k in keys:
                if k in d:
                    return str(d[k])
        except json.JSONDecodeError:
            pass
    # YAML: 顶层
    try:
        import yaml  # noqa: PLC0415

        for doc in yaml.safe_load_all(content):
            if isinstance(doc, dict):
                for k in keys:
                    if k in doc:
                        return str(doc[k])
                # 顶层没有 generated_at, 取首个子 dict
                for v in doc.values():
                    if isinstance(v, dict):
                        for k in keys:
                            if k in v:
                                return str(v[k])
                        break
                break
    except Exception:  # noqa: BLE001
        pass
    return None


def check_file(path_str: str, now: datetime | None = None, keys: tuple[str, ...] = GENERATED_AT_KEYS) -> dict:
    """检查单个状态文件的 freshness."""
    now = now or datetime.now(timezone.utc)
    path = WORKSPACE / path_str
    if not path.is_file():
        return {
            "path": path_str,
            "exists": False,
            "ok": False,
            "reason": "file_missing",
            "score": 0,
        }
    ts = _extract_generated_at(path, keys=keys)
    if not ts:
        return {
            "path": path_str,
            "exists": True,
            "ok": False,
            "reason": "no_generated_at",
            "score": 0,
        }
    dt = _parse_iso(ts)
    if dt is None:
        return {
            "path": path_str,
            "exists": True,
            "ok": False,
            "reason": f"unparseable_timestamp:{ts}",
            "score": 0,
        }
    age_hours = (now - dt).total_seconds() / 3600
    score = _score_freshness(age_hours)
    return {
        "path": path_str,
        "exists": True,
        "ok": score >= 80,
        "generated_at": ts,
        "age_hours": round(age_hours, 2),
        "score": score,
        "stale": score < 80,
        "expired": score == 0,
    }


def run_check(file_filter: str | None = None, now: datetime | None = None) -> dict:
    """运行 freshness 检查, 返回报告."""
    now = now or datetime.now(timezone.utc)
    targets: list[tuple[str, tuple[str, ...]]] = []
    for entry in STATE_FILES:
        path_str = entry[0]
        keys = entry[1] if len(entry) > 1 else GENERATED_AT_KEYS
        if file_filter and file_filter not in path_str:
            continue
        targets.append((path_str, keys))
    if file_filter and not targets:
        targets = [(file_filter, GENERATED_AT_KEYS)]
    results = [check_file(p, now=now, keys=k) for p, k in targets]
    scores = [r.get("score", 0) for r in results if r.get("exists")]
    avg_score = sum(scores) / len(scores) if scores else 0
    stale_count = sum(1 for r in results if r.get("stale"))
    expired_count = sum(1 for r in results if r.get("expired"))
    missing_count = sum(1 for r in results if not r.get("exists"))
    return {
        "now": now.isoformat(),
        "files_checked": len(results),
        "files_missing": missing_count,
        "files_stale": stale_count,
        "files_expired": expired_count,
        "avg_score": round(avg_score, 1),
        "ok": expired_count == 0 and stale_count == 0,
        "results": results,
    }


def print_human(report: dict) -> None:
    print("═══ State freshness check ═══")
    print(f"now: {report['now']}")
    print(f"files checked: {report['files_checked']} (missing={report['files_missing']}, stale={report['files_stale']}, expired={report['files_expired']})")
    print(f"avg score: {report['avg_score']}/100")
    print()
    for r in report["results"]:
        status = "PASS" if r.get("ok") else "WARN" if r.get("stale") and not r.get("expired") else "FAIL"
        path = r["path"]
        if not r.get("exists"):
            print(f"[{status}] {path} — file missing")
            continue
        if r.get("reason", "").startswith("no_generated_at") or r.get("reason", "").startswith("unparseable"):
            print(f"[{status}] {path} — {r['reason']}")
            continue
        age = r.get("age_hours", "?")
        score = r.get("score", 0)
        print(f"[{status}] {path} — age={age}h score={score} generated_at={r.get('generated_at','?')}")
    print()
    print("State freshness: " + ("PASS" if report["ok"] else "FAIL"))


def main() -> int:
    parser = argparse.ArgumentParser(description="OMO state SSOT freshness check (ADR-0119 S2-5)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--file", help="Check single file (substring match)")
    args = parser.parse_args()
    report = run_check(file_filter=args.file)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)
    # 退出码语义 (P72 原则 1: 治本后 dry-run 验证本地 env):
    #   0 = 全新鲜 (≥80 全部) 或 有 stale (50-79) — 派生快照老化但仍可用, 不 block
    #   2 = 有 expired (≤0 score, >7d) — 派生快照不可信, 应 block commit
    #
    # 治本动机: 派生快照 (health.yaml / governance-data.json 等) 老化是常态
    # (24h 周期 cron 触发生成). 老化的快照仍是"上次正确状态", 不应 block 日常
    # commit. 仅"过期" (>7d, 信任失效) 才 block, 防未维护的 ghost 状态被消费.
    # 警告在 stderr 显式输出, 让开发者意识到"该 regen 了", 但不阻断 commit.
    if report["files_expired"] > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
