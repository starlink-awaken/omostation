"""omo audit-rollout — 跨仓 baseline 聚合工具 (Round 27 P0).

§12.5.1 步骤 1 实质化 (§12.8 候选 3):
  读各仓 `<repo>/.omo/_knowledge/_audit_baseline.json`,
  聚合到 `workspace/.omo/_delivery/audit-rollout/<date>.json` + 终端汇总表.

用法:
  uv run --no-sync python -m omo.cli audit-rollout \\
    --repos omostation:.,kairon:projects/kairon,metaos:projects/metaos \\
    --output .omo/_delivery/audit-rollout/2026-07-01.json

输出 schema (JSON):
  {
    "generated_at": "2026-07-01T00:00:00Z",
    "repos": {
      "<name>": {
        "drift_by_consumer": {"<consumer>": <int>, ...},
        "total_drift": <int>,
        "total_records": <int>
      }
    },
    "summary": {
      "total_repos": <int>,
      "total_drift": <int>,
      "total_records": <int>,
      "repos_with_drift": <int>
    }
  }

退出码:
  0 = success (含 0 漂移, 完美)
  1 = some drift detected (但报告成功生成)
  2 = error (file not found / parse error)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_baseline(repo_path: Path) -> dict[str, Any]:
    """读单仓 baseline 文件, 返回结构化 dict.

    Raises:
        FileNotFoundError: baseline 文件不存在
        json.JSONDecodeError: baseline 文件损坏
    """
    baseline_path = repo_path / ".omo" / "_knowledge" / "_audit_baseline.json"
    if not baseline_path.exists():
        raise FileNotFoundError(f"baseline not found: {baseline_path}")
    payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    return {
        "drift_by_consumer": payload.get("drift_by_consumer", {}),
        "total_drift": payload.get("total_drift", 0),
        "total_records": payload.get("total_records", 0),
    }


def aggregate_baselines(repos: list[tuple[str, Path]]) -> dict[str, Any]:
    """聚合多仓 baseline 到统一 rollout 结构.

    Args:
        repos: [(name, repo_path), ...] 列表

    Returns:
        rollout dict 含 generated_at / repos / summary
    """
    repos_data: dict[str, dict[str, Any]] = {}
    total_drift = 0
    total_records = 0
    repos_with_drift = 0

    for name, repo_path in repos:
        try:
            data = _read_baseline(repo_path)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            # 单仓失败: 记为 "missing", 不阻塞其他仓
            repos_data[name] = {"error": str(exc), "total_drift": -1, "total_records": 0}
            continue
        repos_data[name] = data
        total_drift += data["total_drift"]
        total_records += data["total_records"]
        if data["total_drift"] > 0:
            repos_with_drift += 1

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repos": repos_data,
        "summary": {
            "total_repos": len(repos),
            "total_drift": total_drift,
            "total_records": total_records,
            "repos_with_drift": repos_with_drift,
        },
    }


def render_rollout_table(rollout: dict[str, Any]) -> str:
    """生成终端汇总表 (纯文本, 不依赖 rich)."""
    lines = []
    lines.append(f"📊 audit-rollout {rollout['generated_at']} ({rollout['summary']['total_repos']} repos):")
    for name, data in rollout["repos"].items():
        if "error" in data:
            lines.append(f"  ❌ {name:20s}: ERROR ({data['error']})")
            continue
        n_consumers = len(data["drift_by_consumer"])
        lines.append(
            f"  {name:20s}: {data['total_drift']:>6d} drift / "
            f"{data['total_records']:>6d} records ({n_consumers} consumers)"
        )
    s = rollout["summary"]
    lines.append("  " + "─" * 50)
    lines.append(
        f"  {'TOTAL':20s}: {s['total_drift']:>6d} drift / "
        f"{s['total_records']:>6d} records "
        f"({s['repos_with_drift']}/{s['total_repos']} with drift)"
    )
    return "\n".join(lines)


def parse_repos_arg(repos_arg: list[str]) -> list[tuple[str, Path]]:
    """解析 --repos 参数: 'name:path' 格式, 多次出现 → list.

    Example: --repos omostation:. --repos kairon:projects/kairon
    """
    out: list[tuple[str, Path]] = []
    for spec in repos_arg:
        if ":" not in spec:
            raise ValueError(f"--repos 格式错误 (期望 name:path): {spec!r}")
        name, raw_path = spec.split(":", 1)
        out.append((name, Path(raw_path).resolve()))
    return out


def cmd_audit_rollout(args: argparse.Namespace) -> int:
    """CLI: omo audit-rollout --repos N:P --output PATH."""
    repos = parse_repos_arg(args.repos)

    rollout = aggregate_baselines(repos)

    # 1. 终端汇总表
    print(render_rollout_table(rollout))
    print()

    # 2. 写 JSON 文件 (Round 26 §12.5.1 设计)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(rollout, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"✅ 写 rollout 报告: {out_path}")
        print(f"   {rollout['summary']['total_repos']} repos / "
              f"{rollout['summary']['total_drift']} drift / "
              f"{rollout['summary']['total_records']} records")

    # 退出码: 有 drift → 1, 否则 0
    return 1 if rollout["summary"]["total_drift"] > 0 else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="omo audit-rollout",
        description="跨仓 baseline 聚合 (§12.5.1 — Round 27 P0 实质化)",
    )
    parser.add_argument(
        "--repos",
        action="append",
        required=True,
        help="仓映射, 格式 name:path (可多次指定, e.g. omostation:. kairon:projects/kairon)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="rollout 报告输出路径 (默认仅打印终端表)",
    )
    args = parser.parse_args(argv)

    try:
        return cmd_audit_rollout(args)
    except (ValueError, FileNotFoundError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
