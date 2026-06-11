"""omo audit-rollout — 跨仓 baseline 聚合 + §17 metrics 聚合 (Round 27 P0 + R46 P0).

§12.5.1 步骤 1 实质化 (§12.8 候选 3):
  读各仓 `<repo>/.omo/_knowledge/_audit_baseline.json`,
  聚合到 `workspace/.omo/_delivery/audit-rollout/<date>.json` + 终端汇总表.

R46 P0 (§19.3):
  加 --include-metrics flag,跨仓跑 `omo logs audit --metrics`,
  聚合 §17 health_grade + debt_density 到报告 JSON.

用法:
  uv run --no-sync python -m omo.cli audit-rollout \\
    --repos omostation:. --repos kairon:projects/kairon \\
    --include-metrics \\
    --output .omo/_delivery/audit-rollout/2026-07-01.json

输出 schema (JSON):
  {
    "generated_at": "2026-07-01T00:00:00Z",
    "repos": {
      "<name>": {
        "drift_by_consumer": {"<consumer>": <int>, ...},
        "total_drift": <int>,
        "total_records": <int>,
        "health_grade": "R0",        // R46 P0: --include-metrics 时有
        "debt_density": 0.0          // R46 P0: --include-metrics 时有
      }
    },
    "summary": {
      "total_repos": <int>,
      "total_drift": <int>,
      "total_records": <int>,
      "repos_with_drift": <int>,
      "worst_health_grade": "R0"     // R46 P0: --include-metrics 时有
    }
  }

退出码:
  0 = success (含 0 漂移且 R0)
  1 = some drift detected (但报告成功生成)
  2 = error (file not found / parse error)
 3 = R3+ health grade (健康度危急, 但报告仍生成)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _run_logs_metrics(repo_path: Path) -> dict[str, Any]:
    """跑单仓 `omo logs audit --metrics`, 返回 §17 metrics dict.

    失败时返回含 "error" 的 dict, 不阻塞其他仓.

    Args:
        repo_path: 仓根路径 (含 .omo/_knowledge/*.jsonl)
    """
    import subprocess

    # 找 omo 仓路径 (可能是 omostation/projects/omo 或独立仓)
    omo_project = repo_path / "projects" / "omo"
    if not omo_project.exists():
        omo_project = repo_path / "omo"
    if not omo_project.exists():
        return {"error": f"omo project not found in {repo_path}", "health_grade": "?", "debt_density": -1.0}

    #优先用 venv python (omostation 本仓) →兜底 uv run (跨仓独立仓)
    venv_python = omo_project / ".venv" / "bin" / "python"
    if venv_python.exists():
        cmd = [str(venv_python), "-m", "omo.cli", "logs", "audit", "--metrics", "--exclude-locked"]
    else:
        cmd = ["uv", "run", "--no-sync", "python", "-m", "omo.cli", "logs", "audit", "--metrics", "--exclude-locked"]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(omo_project),
            capture_output=True,
            text=True,
            timeout=60,
        )
        # metrics JSON 是 json.dumps(indent=2) 多行格式，直接用 slice 截
        stdout = result.stdout
        start = stdout.find("{\n")
        end = stdout.rfind("\n}")
        if start != -1 and end != -1 and end > start:
            try:
                payload = json.loads(stdout[start : end + 2])
                if "health_grade" in payload:
                    return {
                        "health_grade": payload["health_grade"],
                        "debt_density": payload["debt_density"],
                        "drift_count": payload["drift_count"],
                        "drift_count_excluding_locked": payload["drift_count_excluding_locked"],
                        "locked_drift": payload["locked_drift"],
                        "total_records": payload["total_records"],
                    }
            except json.JSONDecodeError:
                pass
        return {
            "error": f"no metrics JSON (exit {result.returncode}): {result.stderr[:120]}",
            "health_grade": "?",
            "debt_density": -1.0,
        }
    except subprocess.TimeoutExpired:
        return {"error": "timeout (>60s)", "health_grade": "?", "debt_density": -1.0}
    except Exception as exc:
        return {"error": str(exc), "health_grade": "?", "debt_density": -1.0}


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


def _health_grade_rank(grade: str) -> int:
    """R0最好 (rank 0), R5 最差 (rank 5). 用于 max() 比较."""
    rank_map = {"R0": 0, "R1": 1, "R2": 2, "R3": 3, "R4": 4, "R5": 5, "?": 99}
    return rank_map.get(grade, 99)


def aggregate_baselines(repos: list[tuple[str, Path]], *, include_metrics: bool = False) -> dict[str, Any]:
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
    worst_grade_rank = 0
    worst_grade = "R0"

    for name, repo_path in repos:
        try:
            data = _read_baseline(repo_path)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            repos_data[name] = {"error": str(exc), "total_drift": -1, "total_records": 0}
            if include_metrics:
                repos_data[name]["health_grade"] = "?"
                repos_data[name]["debt_density"] = -1.0
            continue
        repos_data[name] = data
        total_drift += data["total_drift"]
        total_records += data["total_records"]
        if data["total_drift"] > 0:
            repos_with_drift += 1

        # R46 P0: --include-metrics 时跑 §17 metrics
        if include_metrics:
            m = _run_logs_metrics(repo_path)
            repos_data[name]["health_grade"] = m.get("health_grade", "?")
            repos_data[name]["debt_density"] = m.get("debt_density", -1.0)
            if "error" not in m:
                rank = _health_grade_rank(m["health_grade"])
                if rank > worst_grade_rank:
                    worst_grade_rank = rank
                    worst_grade = m["health_grade"]

    summary: dict[str, Any] = {
        "total_repos": len(repos),
        "total_drift": total_drift,
        "total_records": total_records,
        "repos_with_drift": repos_with_drift,
    }
    if include_metrics:
        summary["worst_health_grade"] = worst_grade

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repos": repos_data,
        "summary": summary,
    }


def render_rollout_table(rollout: dict[str, Any], include_metrics: bool = False) -> str:
    """生成终端汇总表 (纯文本, 不依赖 rich)."""
    lines = []
    lines.append(f"📊 audit-rollout {rollout['generated_at']} ({rollout['summary']['total_repos']} repos):")
    for name, data in rollout["repos"].items():
        if "error" in data:
            lines.append(f"  ❌ {name:20s}: ERROR ({data['error']})")
            continue
        n_consumers = len(data["drift_by_consumer"])
        base = f"  {name:20s}: {data['total_drift']:>6d} drift / {data['total_records']:>6d} records ({n_consumers} consumers)"
        if include_metrics:
            grade = data.get("health_grade", "?")
            density = data.get("debt_density", -1.0)
            grade_icon = "✅" if grade == "R0" else ("⚠️" if grade in ("R1", "R2") else "❌")
            lines.append(f"{base}  {grade_icon} {grade} (density={density:.4f})")
        else:
            lines.append(base)
    s = rollout["summary"]
    total_line = f"  {'TOTAL':20s}: {s['total_drift']:>6d} drift / {s['total_records']:>6d} records ({s['repos_with_drift']}/{s['total_repos']} with drift)"
    if include_metrics:
        worst = s.get("worst_health_grade", "?")
        total_line += f"  ⚠️ worst={worst}"
    lines.append("  " + "─" * 50)
    lines.append(total_line)
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
    """CLI: omo audit-rollout --repos N:P [--include-metrics] [--output PATH]."""
    repos = parse_repos_arg(args.repos)
    include_metrics = getattr(args, "include_metrics", False)

    rollout = aggregate_baselines(repos, include_metrics=include_metrics)

    # 1. 终端汇总表
    print(render_rollout_table(rollout, include_metrics=include_metrics))
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

    # 退出码: R46 P0 扩展
    # R3+ health grade → 3 (危急, 报告仍生成)
    #   有 drift → 1
    #   无 drift 且 R0 → 0
    if include_metrics:
        worst = rollout["summary"].get("worst_health_grade", "R0")
        if _health_grade_rank(worst) >= 3:
            return 3
    if rollout["summary"]["total_drift"] > 0:
        return 1
    return 0


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
    # R46 P0: --include-metrics 跨仓跑 omo logs audit --metrics 并聚合 §17 health grade
    parser.add_argument(
        "--include-metrics",
        action="store_true",
        default=False,
        help="跑各仓 omo logs audit --metrics, 聚合 §17 health_grade + debt_density (R46 P0)",
    )
    args = parser.parse_args(argv)

    try:
        return cmd_audit_rollout(args)
    except (ValueError, FileNotFoundError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
