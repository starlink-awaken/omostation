#!/usr/bin/env python3
"""bet-ledger.py — 三年规划执行台账 CLI.

SSOT: docs/plans/3y-bet-ledger.yaml
人类视图: docs/plans/3Y-BET-LEDGER.md

只读 + 校验工具。本工具不写 .omo/ 治理状态（守 CLAUDE.md §3 边界），
状态变更走 OMO CLI / agent-workflow.py。

Usage:
    python3 bin/plan/bet-ledger.py list [--track T3-COGNI] [--window Y1Q1] [--claimable]
    python3 bin/plan/bet-ledger.py show BET-Y1Q1-T1-01
    python3 bin/plan/bet-ledger.py claim-check BET-Y1Q1-T3-01
    python3 bin/plan/bet-ledger.py verify BET-Y1Q1-T1-01 [--execute]
    python3 bin/plan/bet-ledger.py status
    python3 bin/plan/bet-ledger.py retro-due
    python3 bin/plan/bet-ledger.py surface
    python3 bin/plan/bet-ledger.py gate Y1Q1
    python3 bin/plan/bet-ledger.py lint
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("需要 pyyaml: uv run --with pyyaml python bin/plan/bet-ledger.py ...", file=sys.stderr)
    raise SystemExit(2)

WS = Path(__file__).resolve().parents[2]
LEDGER = WS / "docs" / "plans" / "3y-bet-ledger.yaml"
RETRO_DIR = WS / ".omo" / "_knowledge" / "retros"

# 2026-08-06 实测基线（表面积对比锚点）
BASELINE = {
    "code_loc": 982_000,
    "src_files": 4_537,
    "adr_total": 344,
    "gac_rules": 134,
    "bin_scripts": 309,
    "standards": 53,
    "collab_scenarios": 221,
}

# Y1 收口目标
Y1_TARGET = {"code_loc": 690_000, "adr_total": 120, "gac_rules": 80, "bin_scripts": 180}


# ── 载入 ──────────────────────────────────────────────────────
def load() -> dict:
    if not LEDGER.exists():
        sys.exit(f"台账不存在: {LEDGER}")
    data: dict = {}
    for d in yaml.safe_load_all(LEDGER.read_text(encoding="utf-8")):
        if isinstance(d, dict):
            data.update(d)
    if "bets" not in data:
        sys.exit("台账缺少 bets 段")
    return data


def bet_by_id(data: dict, bet_id: str) -> dict:
    for b in data["bets"]:
        if b["id"] == bet_id:
            return b
    sys.exit(f"未找到 bet: {bet_id}")


# ── 表面积实测 ────────────────────────────────────────────────
def _sh(cmd: str) -> str:
    try:
        return subprocess.run(
            cmd, shell=True, cwd=WS, capture_output=True, text=True, timeout=300
        ).stdout.strip()
    except Exception:
        return ""


def _int(s) -> int:
    try:
        return int(str(s).strip().split()[0])
    except Exception:
        return 0


def measure_surface() -> dict:
    exclude = r"node_modules|\.venv|site-packages|/dist/|/build/|__pycache__"
    find = (
        rf'find projects/*/ \( -name "*.py" -o -name "*.ts" -o -name "*.tsx" \) '
        rf'| grep -vE "{exclude}"'
    )
    # 注意: xargs 分批调用 wc 会产生多个 "total" 行, 必须全部求和 (不能 tail -1)
    raw = _sh(f"{find} | xargs wc -l 2>/dev/null | grep -w total")
    loc = 0
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "total":
            loc += _int(parts[0])
    return {
        "code_loc": loc,
        "src_files": _int(_sh(f"{find} | wc -l")),
        "adr_total": _int(_sh("ls .omo/_knowledge/decisions/*.md 2>/dev/null | wc -l")),
        "gac_rules": _int(
            _sh(r"""grep -c '^  - id:\|^- id:' .omo/_truth/registry/governance-checks.yaml 2>/dev/null""")
        ),
        "bin_scripts": _int(
            _sh(r'find bin -type f \( -name "*.py" -o -name "*.sh" \) | wc -l')
        ),
        "standards": _int(_sh("ls .omo/standards/ 2>/dev/null | wc -l")),
        "collab_scenarios": _int(
            _sh("ls .omo/_delivery/collab-scenarios/ 2>/dev/null | wc -l")
        ),
    }


# ── 认领判定 ──────────────────────────────────────────────────
def _claimable(data: dict, b: dict) -> tuple[bool, list[str]]:
    """依赖已 done + 状态可启动 + 无冲突轨道在跑 + 未超并行上限。"""
    reasons: list[str] = []
    ok = True
    if b.get("status") not in ("candidate", "pending", "blocked"):
        ok = False
        reasons.append(f"状态 {b.get('status')} 不可认领")
    index = {x["id"]: x for x in data["bets"]}
    for dep in b.get("depends_on") or []:
        d = index.get(dep)
        if d is None:
            ok = False
            reasons.append(f"依赖不存在: {dep}")
        elif d.get("status") != "done":
            ok = False
            reasons.append(f"依赖未完成: {dep} ({d.get('status')})")
    running = {x["track"] for x in data["bets"] if x.get("status") == "in_progress"}
    conc = data.get("concurrency", {})
    for pair in conc.get("conflict_pairs", []):
        if b["track"] in pair:
            for o in [t for t in pair if t != b["track"]]:
                if o in running:
                    ok = False
                    reasons.append(f"冲突轨道运行中: {o}（共享写面）")
    for excl in conc.get("exclusive_tracks", []):
        if excl in running and b["track"] != excl:
            ok = False
            reasons.append(f"独占轨道 {excl} 运行中，其余轨道只读")
    cap = conc.get("max_parallel_bets", 4)
    if len(running) >= cap and b["track"] not in running:
        ok = False
        reasons.append(f"已达并行上限 {cap}")
    if b.get("human_gate"):
        reasons.append("★ 需 operator/human 到场，认领前先确认可用")
    if ok and not reasons:
        reasons.append("依赖与并发检查通过")
    return ok, reasons


# ── 命令 ──────────────────────────────────────────────────────
def cmd_list(data: dict, args) -> int:
    rows = data["bets"]
    if args.track:
        rows = [b for b in rows if b["track"] == args.track]
    if args.window:
        rows = [b for b in rows if b["window"] == args.window]
    if args.status:
        rows = [b for b in rows if b.get("status") == args.status]
    if args.claimable:
        rows = [b for b in rows if _claimable(data, b)[0]]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    print(f"{'ID':24} {'W':6} {'TRACK':12} {'APPETITE':10} {'ST':11} H  TITLE")
    print("-" * 120)
    for b in rows:
        h = "★" if b.get("human_gate") else " "
        print(
            f"{b['id']:24} {b['window']:6} {b['track']:12} "
            f"{b.get('appetite',''):10} {b.get('status',''):11} {h}  {b['title']}"
        )
    print(f"\n共 {len(rows)} 个 bet（★ = 需 operator/human 到场）")
    return 0


def cmd_show(data: dict, args) -> int:
    b = bet_by_id(data, args.bet_id)
    print(yaml.safe_dump(b, allow_unicode=True, sort_keys=False))
    ok, reasons = _claimable(data, b)
    print(f"可认领: {'YES' if ok else 'NO'}")
    for r in reasons:
        print(f"  - {r}")
    return 0


def cmd_claim_check(data: dict, args) -> int:
    b = bet_by_id(data, args.bet_id)
    ok, reasons = _claimable(data, b)
    print(f"[{b['id']}] {b['title']}")
    for r in reasons:
        print(f"  - {r}")
    if ok:
        tr = data["tracks"][b["track"]]
        wf = b.get("workflow") or tr.get("default_workflow")
        sess = b["id"].lower()
        print("\n认领命令：")
        print(f"  bash bin/gac/gac-worktree.sh claim {sess}")
        print(
            f"  uv run --with pyyaml python bin/agent-workflow.py start {wf} "
            f"--profile {tr.get('agent_profile_hint','engineering-agent')} "
            f'--objective "{b["id"]} {b["title"]}"'
        )
        globs = []
        for p in b.get("write_surfaces", []):
            if "*" in p:
                globs.append(p)
                continue
            print(f"  uv run --with pyyaml python bin/agent-workflow.py claim <run-id> --path {p}")
        if globs:
            print("\n  # ⚠ claim 不做 glob 展开（lifecycle.py 只对锁目录 glob，--path 按字面量存）")
            print("  #   下列写面必须逐个真实文件 claim，否则锁名是字面量、D3 匹配不上：")
            for g in globs:
                base = g.split("*")[0].rstrip("/")
                print(f"  #   {g}  →  先看有哪些: git ls-files '{g}'  或  ls {base}/")
        if b.get("pasw_required"):
            print("  # ⚠ PASW: 子模块改动必须在 .subtrees/<sub>/ 内完成（ADR-0371）")
        if b.get("underlying_workflow"):
            print(f"  # 原挂载 workflow（phases/lock_scopes 可参考）: {b['underlying_workflow']}")
        print("\n收尾命令：")
        print("  git add <所有 deliverable>        # D0 铁律, 先于 verify")
        print("  uv run --with pyyaml python bin/agent-workflow.py verify <run-id> --from-diff --execute")
        print("  make agent-workflow-closeout RUN_ID=<run-id>")
        print(f"  # 写复盘: {RETRO_DIR.relative_to(WS)}/{b['id']}.md")
    return 0 if ok else 1


def cmd_verify(data: dict, args) -> int:
    b = bet_by_id(data, args.bet_id)
    print(f"[{b['id']}] {b['title']}\n")
    print("done_when:")
    for d in b.get("done_when", []):
        print(f"  [ ] {d}")
    print("\nverify:")
    for v in b.get("verify", []):
        cmd, exp = v.get("cmd", ""), v.get("expect", "")
        print(f"  $ {cmd}")
        if args.execute:
            print(f"    → {_sh(cmd) or '(空)'}")
        print(f"    期望: {exp}")
    rc = 0
    print("\nD0 (入库才算交付):")
    for p in b.get("write_surfaces", []):
        if "*" in p:
            print(f"  [跳过] {p} (通配, 需人工核对)")
            continue
        r = subprocess.run(
            ["git", "ls-files", "--error-unmatch", p], cwd=WS, capture_output=True
        )
        if r.returncode == 0:
            print(f"  [OK]   {p}")
        else:
            print(f"  [未入库] {p}")
            rc = 1
    print("\nD2 (表面积记账): 见 `bet-ledger.py surface`")
    if not args.execute:
        print("(加 --execute 实际运行 verify 命令)")
    return rc


def cmd_status(data: dict, args) -> int:
    bets = data["bets"]
    by_status: dict[str, int] = {}
    by_window: dict[str, dict[str, int]] = {}
    for b in bets:
        s = b.get("status", "candidate")
        by_status[s] = by_status.get(s, 0) + 1
        by_window.setdefault(b["window"], {})[s] = (
            by_window.setdefault(b["window"], {}).get(s, 0) + 1
        )
    print("=== 台账总览 ===")
    print(f"总 bet: {len(bets)}")
    for s, n in sorted(by_status.items()):
        print(f"  {s:12} {n}")
    print("\n=== 按窗口 ===")
    for w in data["meta"]["windows"]:
        if w in by_window:
            done = by_window[w].get("done", 0)
            total = sum(by_window[w].values())
            filled = int(20 * done / total) if total else 0
            print(f"  {w:6} {'█'*filled}{'░'*(20-filled)} {done}/{total}")
    print("\n=== 当前可认领（按窗口排序，优先做靠前窗口）===")
    order = {w: i for i, w in enumerate(data["meta"]["windows"])}
    claimable = [b for b in bets if _claimable(data, b)[0]]
    claimable.sort(key=lambda b: (order.get(b["window"], 99), b["id"]))
    for b in claimable:
        h = "★" if b.get("human_gate") else " "
        print(f"  {h} {b['window']:6} {b['id']:24} {b.get('appetite',''):<9} {b['title']}")
    if not claimable:
        print("  （无。检查 depends_on 或并发上限）")
    else:
        print(f"\n  共 {len(claimable)} 个可认领；★ = 需 operator/human 到场")
    return 0


def cmd_retro_due(data: dict, args) -> int:
    due = [
        b
        for b in data["bets"]
        if b.get("status") == "done"
        and b.get("retro") in ("required", "light")
        and not (RETRO_DIR / f"{b['id']}.md").exists()
    ]
    if not due:
        print("无待补复盘。")
        return 0
    print("以下 bet 已 done 但缺复盘（违反 D5）：")
    for b in due:
        print(f"  {b['id']:24} {b['title']}")
    print(f"\n模板路径：{RETRO_DIR.relative_to(WS)}/<bet-id>.md")
    for q in data["retro"]["bet_level"]["questions"]:
        print(f"  - {q}")
    return 1


def cmd_surface(data: dict, args) -> int:
    cur = measure_surface()
    print("=== 表面积实测 ===")
    print(f"{'指标':<20}{'当前':>10}{'基线(2026-08)':>16}{'变化':>18}{'Y1目标':>10}")
    print("-" * 76)
    for k, base in BASELINE.items():
        c = cur.get(k, 0)
        delta = c - base
        pct = (delta / base * 100) if base else 0
        tgt = Y1_TARGET.get(k, "—")
        print(f"{k:<20}{c:>10,}{base:>16,}{delta:>+11,}({pct:+.0f}%){str(tgt):>10}")
    ratio = cur["code_loc"] / BASELINE["code_loc"] if BASELINE["code_loc"] else 0
    print(f"\n代码表面积占基线: {ratio:.0%}   (Y1 目标 ≤ 70%)")
    print(f"判定: {'达标' if ratio <= 0.70 else '未达标'}")
    return 0 if ratio <= 0.70 else 1


def cmd_gate(data: dict, args) -> int:
    g = data.get("gates", {}).get(args.window)
    if not g:
        sys.exit(f"无此门: {args.window}（可用: {', '.join(data.get('gates', {}))}）")
    print(f"=== 门 {args.window} ===")
    print(f"问题:     {g['question']}")
    print(f"通过条件: {g['pass']}")
    print(f"不通过时: {g.get('on_fail','—')}")
    print(f"\n本门为人工判定，结论须写入：{RETRO_DIR.relative_to(WS)}/gates/{args.window}.md")
    return 0


def cmd_lint(data: dict, args) -> int:
    """台账自检：ID 唯一、依赖存在、轨道/窗口/状态合法、必填字段。"""
    errs: list[str] = []
    ids = [b["id"] for b in data["bets"]]
    for i in sorted(set(ids)):
        if ids.count(i) > 1:
            errs.append(f"重复 ID: {i}")
    tracks = set(data["tracks"])
    windows = set(data["meta"]["windows"])
    required = [
        "track", "window", "title", "appetite", "status", "goal",
        "done_when", "verify", "workflow", "write_surfaces",
    ]
    for b in data["bets"]:
        for f in required:
            if not b.get(f):
                errs.append(f"{b['id']}: 缺字段 {f}")
        if b.get("track") not in tracks:
            errs.append(f"{b['id']}: 未知 track {b.get('track')}")
        if b.get("window") not in windows:
            errs.append(f"{b['id']}: 未知 window {b.get('window')}")
        if b.get("status") not in data["meta"]["status_enum"]:
            errs.append(f"{b['id']}: 非法 status {b.get('status')}")
        for d in b.get("depends_on") or []:
            if d not in ids:
                errs.append(f"{b['id']}: 依赖不存在 {d}")
        # 未加引号的冒号会让 YAML 把列表项解析成 dict，静默丢失语义
        for key in ("done_when", "non_goals"):
            for i, item in enumerate(b.get(key) or []):
                if not isinstance(item, str):
                    errs.append(
                        f"{b['id']}.{key}[{i}]: 应为字符串却是 {type(item).__name__} "
                        f"— 多半是未加引号的冒号，请写成 \"...: ...\""
                    )
    if errs:
        for e in errs:
            print(f"ERROR {e}")
        print(f"\n{len(errs)} 个问题")
        return 1
    print(f"OK — {len(data['bets'])} 个 bet，{len(tracks)} 条轨道，无问题")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="三年规划执行台账")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--track")
    pl.add_argument("--window")
    pl.add_argument("--status")
    pl.add_argument("--claimable", action="store_true")
    pl.add_argument("--json", action="store_true")

    sub.add_parser("show").add_argument("bet_id")
    sub.add_parser("claim-check").add_argument("bet_id")

    pv = sub.add_parser("verify")
    pv.add_argument("bet_id")
    pv.add_argument("--execute", action="store_true")

    sub.add_parser("status")
    sub.add_parser("retro-due")
    sub.add_parser("surface")
    sub.add_parser("gate").add_argument("window")
    sub.add_parser("lint")

    args = p.parse_args()
    data = load()
    return {
        "list": cmd_list,
        "show": cmd_show,
        "claim-check": cmd_claim_check,
        "verify": cmd_verify,
        "status": cmd_status,
        "retro-due": cmd_retro_due,
        "surface": cmd_surface,
        "gate": cmd_gate,
        "lint": cmd_lint,
    }[args.cmd](data, args)


if __name__ == "__main__":
    raise SystemExit(main())
