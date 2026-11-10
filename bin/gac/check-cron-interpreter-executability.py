#!/usr/bin/env python3
"""cron 登记面的解释器**可执行性**门禁（warn 起，限期收敛后转 fail-closed）.

债务: `.omo/debt/items/CRON-BARE-PYTHON3-PY39-IMPORT-DEATH.yaml`
裁决: 2026-11-10 principal 选「先 warn + 限期收敛」—— 门禁以非阻断形态上线，
      到 `ENFORCE_AFTER` 仍未收敛则自动翻成阻断；不给人留静默窗口。

为什么必须是可执行性判据，而不是又一遍静态扫描（决策(3) 的立足点，全部实测）:
  · 数「登记面 command 指向的文件」低报 5 倍：87 条里按入口文件名数只覆盖 8 条，
    真实死法有 45 条 —— 大头是复合命令的第二/第三个 python 调用点 (#5174 实证)。
  · 读入口文件自身的 import 也会漏：`bin/gac/execution-environment-steward.py`
    顶层 import 全是 stdlib，真死因在它 `:39-41` 用 `spec_from_file_location`
    动态拉起的 `bin/gac/gate-evidence-receipt.py:21` (`from datetime import UTC`)。
  · 补 `from datetime import UTC` 的出现集合同样会漏：`bin/gac/debt-audit.py:19`
    走 `from omo.timeutils import UTC`，任何按标准库名匹配的扫描都看不见。
  ⇒ 唯一可靠的判据是「**用那个解释器真去 import 一次**」。本门禁不自己实现判据，
    全部走 `bin/lib/cron_normalize`（与 `scheduler-compile` / `install-cron-plane`
    同一份实现）—— 门禁与安装器分叉是这项债的原始成因之一。

为什么不 import 目标脚本本体: 模块级代码有网络/写盘副作用（登记面里确实有 POST git、
递归删目录实跑、mem0 purge），编译期不能碰。判据因此是「候选解释器满足版本下限 +
满足脚本的第三方依赖集」，依赖集用 ast 静态取（含闭包）。

退出码: 0 = 无缺口 / 有缺口但仍在 warn 期；1 = 过期限仍有缺口，或 `--strict`。
只读，不写任何文件；`--json` 的产物就是本次运行的结构化记录（AGENTS.md §14.2 六字段）。
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "bin" / "lib"))

from cron_normalize import (  # noqa: E402
    closure_undetermined,
    current_host,
    installed_crontab_lines,
    installed_interpreter_gaps,
    interpreter_candidates,
    interpreter_executability_jobs,
)

DEBT_ID = "CRON-BARE-PYTHON3-PY39-IMPORT-DEATH"
# 限期 = 裁决日 (2026-11-10) + 14 天。与 governance-checks.yaml 里
# CR-X2-CRON-INTERP-EXECUTABILITY 的 review_before **必须同值**，
# 由 tests/unit/test_cron_interpreter_executability.py 钉住，不靠人记。
ENFORCE_AFTER = "2026-11-24"


def _load_jobs(registry: Path) -> list[dict]:
    import yaml

    return yaml.safe_load(registry.read_text(encoding="utf-8"))["jobs"]


def evaluate(
    jobs: list[dict],
    *,
    candidates: list[str] | None = None,
    registry: Path,
    now: datetime.date,
    strict: bool = False,
    max_depth: int = 2,
    repo_root: Path | None = None,
    installed_plane: list[str] | None | Any = ...,
) -> dict:
    """跑一遍判据，返回可直接落记录面的 dict（缺口只数发射侧口径）。

    两个面分开判，同一个退出码（决策(2) 改判 B′, principal 2026-11-10）：
      · **登记面** —— `interpreter_executability_jobs`：作业**声明**的解释器能不能跑；
      · **已装面** —— `installed_interpreter_gaps`：cron **实际执行**的那一行里的解释器
        还在不在、跑不跑得动它指向的脚本。安装侧按宿主重写解释器，两面不是同一个对象；
        只判登记面时「venv 被删 / homebrew 换了版本号」对 `--check` 完全隐形。
    """
    root = Path(repo_root) if repo_root else _ROOT
    # 只读一次已装面：既给判据当「这台机器跑不跑 cron」的闸门，也如实报状态
    plane = installed_crontab_lines() if installed_plane is ... else installed_plane
    records = interpreter_executability_jobs(
        jobs, candidates=candidates, repo_root=root, max_depth=max_depth, installed_plane=plane
    )
    # 作业声明的工作区不在本机 ⇒ 整条不进判定（CI / 非 cron 宿主）。不计入 jobs_scanned，
    # 但单独报数：全体被跳过与全体判得出结果，在汇总行上必须是两种形状。
    skipped = [r for r in records if not r["host_assessable"]]
    assessable = [r for r in records if r["host_assessable"]]
    blocking = [r for r in assessable if r["install_reason"]]
    advisory = [r for r in assessable if r["closure_reason"] and not r["install_reason"]]
    # 判不出的兄弟模块单独列出：把「静态看不见」和「跑得动」混成同一个绿，
    # 就是本项要终结的那个假绿形状。
    undetermined = []
    for r in assessable:
        for site in r["sites"]:
            script = Path(site["script"])
            if not site["exists"]:
                continue
            undetermined += [
                f"{r['name']} → {p}" for p in closure_undetermined(script, root, max_depth=max_depth)
            ]
    # 已装面：cron 真正执行的字符串。plane 没装或读不出时行集为空 ⇒ 自然不判，
    # 与登记面的宿主纪律一致（CI 上不会因为「这台机器不跑 cron」而变红）。
    plane_res = installed_interpreter_gaps(jobs, installed_lines=plane, repo_root=root)
    plane_gaps = plane_res["gaps"]
    # 自证：已装面有 python 调用点却一行都配不上登记面 ⇒ 配对口径坏了，此时「0 缺口」
    # 是空转出来的。仪器故障报成 advisory（不翻退出码 —— 那会把归属问题算成交付缺陷），
    # 但必须看得见。
    pairing_suspicious = 1 if (plane_res["python_sites"] and not plane_res["paired_lines"]) else 0
    enforce_after = datetime.date.fromisoformat(ENFORCE_AFTER)
    escalated = now >= enforce_after
    verdict = "OK"
    if blocking or plane_gaps or advisory or undetermined or pairing_suspicious:
        verdict = "FAIL" if ((blocking or plane_gaps) and (escalated or strict)) else "WARN"
    return {
        "check": Path(__file__).name,
        "debt_id": DEBT_ID,
        "verdict": verdict,
        "registry": str(registry),
        "host": current_host(),
        "plane": "unreadable" if plane is None else ("present" if plane else "absent"),
        "host_candidates": candidates if candidates is not None else interpreter_candidates(root),
        "jobs_scanned": len(assessable),
        "jobs_off_host": len(skipped),
        "blocking_gaps": len(blocking) + len(plane_gaps),
        "registry_gaps": len(blocking),
        "plane_gaps": len(plane_gaps),
        "plane_lines_scanned": plane_res["lines_scanned"],
        "plane_paired_lines": plane_res["paired_lines"],
        "plane_unregistered_broken": len(plane_res["unregistered_broken"]),
        "plane_bare_tokens": plane_res["bare_tokens"],
        "plane_python_sites": plane_res["python_sites"],
        "plane_pairing_suspicious": pairing_suspicious,
        "closure_advisories": len(advisory),
        "undetermined_edges": len(undetermined),
        "enforce_after": ENFORCE_AFTER,
        "enforcement": "blocking" if (escalated or strict) else "warn-only",
        "gaps": [
            {
                "name": r["name"],
                "schedule": r.get("schedule"),
                "owner": r.get("owner"),
                "sites": r["sites"],
                "reason": r["install_reason"],
                "closure_reason": r["closure_reason"],
            }
            for r in blocking
        ],
        "advisories": [
            {"name": r["name"], "closure_reason": r["closure_reason"], "sites": r["sites"]}
            for r in advisory
        ],
        "undetermined": sorted(set(undetermined))[:40],
        "plane_gap_details": plane_gaps[:20],
        "plane_unregistered_details": plane_res["unregistered_broken"][:20],
    }


def _six_field_record(result: dict, *, started: float, inputs: list[str], basis: list[str]) -> dict:
    """AGENTS.md §14.2：一次自动化运行一条记录，六个键，缺值写 null 不省略键。"""
    return {
        "inputs": inputs,
        "basis": basis,
        "approver": "principal (2026-11-10 裁决: 先 warn + 限期收敛)",
        "result": {
            "verdict": result["verdict"],
            "blocking_gaps": result["blocking_gaps"],
            "closure_advisories": result["closure_advisories"],
            "enforcement": result["enforcement"],
        },
        "duration_ms": int((time.monotonic() - started) * 1000),
        "model_usage": None,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--registry", default=str(_ROOT / ".omo" / "cron" / "registry.yaml"))
    ap.add_argument("--candidate", action="append", dest="candidates",
                    help="覆盖候选解释器（可重复传）；用于复现只有 3.9 的宿主")
    ap.add_argument("--enforce-after", default=ENFORCE_AFTER, help="限期 (YYYY-MM-DD)，默认取常量")
    ap.add_argument("--now", default=None, help="判定用的今天 (YYYY-MM-DD)，测试与回溯用")
    ap.add_argument("--strict", action="store_true", help="无视限期，有缺口即 FAIL")
    ap.add_argument("--max-depth", type=int, default=2, help="依赖闭包深度 (1 = 只看入口自己)")
    ap.add_argument("--json", action="store_true", help="机器可读输出（含六字段运行记录）")
    args = ap.parse_args(argv)

    started = time.monotonic()
    registry = Path(args.registry)
    if not registry.is_file():
        print(f"check_cron_registry_missing: {registry}", file=sys.stderr)
        return 2
    if args.enforce_after != ENFORCE_AFTER:
        globals()["ENFORCE_AFTER"] = args.enforce_after
    jobs = _load_jobs(registry)
    now = datetime.date.fromisoformat(args.now) if args.now else datetime.datetime.now().date()
    result = evaluate(
        jobs,
        candidates=args.candidates,
        registry=registry,
        now=now,
        strict=args.strict,
        max_depth=args.max_depth,
    )
    record = _six_field_record(
        result,
        started=started,
        inputs=[
            str(registry),
            f"jobs={len(jobs)}",
            f"candidates={result['host_candidates']}",
            f"installed_plane_lines={result['plane_lines_scanned']} 配对={result['plane_paired_lines']}",
        ],
        basis=[
            f".omo/debt/items/{DEBT_ID}.yaml (决策(3) 裁决 2026-11-10)",
            f".omo/debt/items/{DEBT_ID}.yaml (决策(2) 改判 B′ 裁决 2026-11-10: 已装面逐字比对不成立, 改判已装行解释器健康)",
            ".omo/_truth/registry/governance-checks.yaml::CR-X2-CRON-INTERP-EXECUTABILITY",
            "bin/lib/cron_normalize.py (与 scheduler-compile / install-cron-plane 同源)",
        ],
    )
    result["run_record"] = record

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            f"[cron-interpreter-executability] host={result['host']} plane={result['plane']} "
            f"verdict={result['verdict']} "
            f"扫描={result['jobs_scanned']} 非本机不判={result['jobs_off_host']} "
            f"阻断缺口={result['blocking_gaps']} "
            f"(登记面={result['registry_gaps']} 已装面={result['plane_gaps']}/"
            f"扫{result['plane_lines_scanned']}行 配对{result['plane_paired_lines']}"
            f" 未登记坏{result['plane_unregistered_broken']} 裸写法{result['plane_bare_tokens']}) "
            f"闭包提醒={result['closure_advisories']} 判不出={result['undetermined_edges']} "
            f"已装面调用点={result['plane_python_sites']}"
            + (" ⚠配对全空(仪器自证失败)" if result["plane_pairing_suspicious"] else "") + " "
            f"(enforcement={result['enforcement']}, 限期={ENFORCE_AFTER})"
        )
        for g in result["gaps"][:20]:
            print(f"  GAP  {g['name']}: {str(g['reason'])[:160]}")
        for g in result["plane_gap_details"][:20]:
            print(f"  PLANE-GAP  {g['name'] or '(未登记)'} {g['interpreter']}: {str(g['reason'])[:150]}")
        for g in result["plane_unregistered_details"][:20]:
            print(f"  PLANE-UNREG  {g['interpreter']}: {str(g['reason'])[:150]}")
        for a in result["advisories"][:20]:
            print(f"  ADV  {a['name']}: {str(a['closure_reason'])[:160]}")
        for u in result["undetermined"][:10]:
            print(f"  UNDET {u}")

    # advisory / undetermined 在 warn 期不翻转退出码：它们不是「装上去会死」的读数，
    # 但必须在输出里可见 —— 沉默的绿是本项要终结的东西。
    return 1 if result["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
