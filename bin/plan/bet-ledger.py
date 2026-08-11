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
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

try:
    import yaml
except ImportError:  # pragma: no cover
    print("需要 pyyaml: uv run --with pyyaml python bin/plan/bet-ledger.py ...", file=sys.stderr)
    raise SystemExit(2)

WS = Path(__file__).resolve().parents[2]
LEDGER = WS / "docs" / "plans" / "3y-bet-ledger.yaml"
RETRO_DIR = WS / ".omo" / "_knowledge" / "retros"

# 2026-08-06 实测基线 — git tracked 口径（含子模块）
#
# ⚠ 口径变更历史（重要，别再用旧数）：
#   v1 (作废): 文件系统扫描 projects/*/, 得 982,000 行。两个缺陷——
#     ① 不区分 src / test：测试占 33%，删测试是达标最便宜路径 → 指标可被有害优化
#     ② 含 gitignore 掉的 PASW 残留：projects/Workspace/.subtrees/{cockpit,ecos,kairon}
#        三份重复检出共 32.2 万行，占旧基线 33%。建/删 worktree 就能让指标大幅波动
#   v2 (当前): git ls-files --recurse-submodules，只测受版本控制的真实代码，src/test 分列
BASELINE = {
    "src_loc": 726_412,
    "test_loc": 350_854,
    "src_files": 3_204,
    "test_files": 1_827,
    "adr_total": 344,
    "gac_rules": 136,        # 实测 gac.rules；其中 advisory 105 / required 24 / error 2
    "gac_required": 26,      # required + error —— 会拦人的那部分，才是真成本
    "bin_scripts": 310,
    "standards": 53,
    "collab_scenarios": 221,
}

# Y1 收口目标
#
# 设计原则（2026-08-06 复盘修正）：不设总量百分比，改设「已识别冗余清零」。
#   理由：百分比目标不指向具体冗余，会诱导执行者找最便宜的达标路径（删测试）。
#   src_loc 只作观察量记账；test_loc 是【保护量】，下降即判定为有害减法。
Y1_TARGET = {
    "src_loc": None,          # 不设百分比目标，由具体归并 bet 的去重量累计
    "test_loc": "不得下降",    # 保护量：低于基线即 D2 违规
    "gac_required": 0,        # required 规则中「无违规历史」的清零（不是总数降到 80）
    "bin_scripts": "零调用归档",  # 实测低引用候选约 43 个，含 lib/pytest 假阳性，不设数量
    "adr_total": "只分层不裁剪",  # active/historical 分层即可降低检索面，无需删除
}


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


def _d0_surface_tracked(surface: str, *, ws: Path | None = None) -> tuple[bool, str]:
    """Check one exact write surface against the root index or a pinned gitlink.

    A superproject tracks only the mode-160000 gitlink, not paths inside the
    submodule.  For an internal path, the staged gitlink OID is therefore the
    persistence boundary: the exact child path must exist in that commit.
    """
    root = ws or WS
    normalized = PurePosixPath(surface)
    if normalized.is_absolute() or ".." in normalized.parts:
        return False, "invalid path"

    root_match = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", surface],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if root_match.returncode == 0:
        return True, "root index"

    staged = subprocess.run(
        ["git", "ls-files", "--stage"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if staged.returncode != 0:
        return False, "root index unavailable"

    gitlinks: list[tuple[str, str]] = []
    for line in staged.stdout.splitlines():
        try:
            metadata, tracked_path = line.split("\t", 1)
            mode, oid, stage = metadata.split()
        except ValueError:
            continue
        if mode == "160000" and stage == "0":
            gitlinks.append((tracked_path, oid))

    matches = [item for item in gitlinks if surface.startswith(f"{item[0]}/")]
    if not matches:
        return False, "not tracked"
    gitlink_path, oid = max(matches, key=lambda item: len(item[0]))
    child_path = surface[len(gitlink_path) + 1 :]
    child_repo = root / gitlink_path

    commit = subprocess.run(
        ["git", "-C", str(child_repo), "cat-file", "-e", f"{oid}^{{commit}}"],
        capture_output=True,
        check=False,
    )
    if commit.returncode != 0:
        return False, f"gitlink object unavailable: {gitlink_path}@{oid[:12]}"

    tree = subprocess.run(
        [
            "git",
            "-C",
            str(child_repo),
            "ls-tree",
            "-r",
            "--name-only",
            oid,
            "--",
            child_path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if tree.returncode != 0 or child_path not in tree.stdout.splitlines():
        return False, f"absent from pinned gitlink: {gitlink_path}@{oid[:12]}"

    head = subprocess.run(
        ["git", "ls-tree", "HEAD", "--", gitlink_path],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    pin_kind = (
        "HEAD gitlink"
        if f"commit {oid}\t{gitlink_path}" in head.stdout
        else "staged gitlink"
    )
    return True, f"{pin_kind}: {gitlink_path}@{oid[:12]}"


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


# 测试文件判据：目录名 tests?/__tests__/spec，或 test_ 前缀，或 .test./.spec. 后缀
TEST_PAT = re.compile(
    r"(^|/)(tests?|__tests__|spec)/|(^|/)test_[^/]*$|\.(test|spec)\.(ts|tsx|py)$"
)
VENDOR_PAT = re.compile(r"node_modules|\.venv|site-packages|/dist/|/build/")


def _loc(paths: list[str]) -> int:
    """批量 wc -l 求和。注意 xargs 分批会产生多个 total 行，必须全加。"""
    total = 0
    for i in range(0, len(paths), 400):
        batch = [p for p in paths[i : i + 400] if (WS / p).exists()]
        if not batch:
            continue
        r = subprocess.run(
            ["wc", "-l"] + batch, cwd=WS, capture_output=True, text=True
        )
        lines = r.stdout.splitlines()
        if len(batch) == 1:
            try:
                total += int(lines[0].split()[0])
            except Exception:
                pass
        else:
            for line in lines:
                p = line.split()
                if len(p) >= 2 and p[1] == "total":
                    total += _int(p[0])
    return total


def measure_surface() -> dict:
    """只测 git tracked 文件（含子模块）。

    为什么不扫文件系统：会把 gitignore 掉的 PASW worktree
    （projects/Workspace/.subtrees/*，32.2 万行重复检出）算进来，
    建/删 worktree 就能让指标大幅波动 —— 这是可被无意义优化的指标。
    """
    r = subprocess.run(
        ["git", "ls-files", "--recurse-submodules"],
        cwd=WS, capture_output=True, text=True,
    )
    files = [
        f for f in r.stdout.split("\n")
        if f.endswith((".py", ".ts", ".tsx")) and not VENDOR_PAT.search(f)
    ]
    src = [f for f in files if not TEST_PAT.search(f)]
    test = [f for f in files if TEST_PAT.search(f)]

    # GaC：区分 advisory（不阻断，成本≈0）与 required/error（会拦人，才是真成本）
    gac_total = gac_required = 0
    gac_path = WS / ".omo/_truth/registry/governance-checks.yaml"
    if gac_path.exists():
        try:
            for doc in yaml.safe_load_all(gac_path.read_text(encoding="utf-8")):
                if isinstance(doc, dict) and isinstance(doc.get("gac"), dict):
                    rules = doc["gac"].get("rules") or []
                    gac_total = len(rules)
                    gac_required = sum(
                        1 for x in rules
                        if isinstance(x, dict)
                        and str(x.get("enforcement")) in ("required", "error")
                    )
        except Exception:
            pass

    return {
        "src_loc": _loc(src),
        "test_loc": _loc(test),
        "src_files": len(src),
        "test_files": len(test),
        "adr_total": _int(_sh("ls .omo/_knowledge/decisions/*.md 2>/dev/null | wc -l")),
        "gac_rules": gac_total,
        "gac_required": gac_required,
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
        tracked, detail = _d0_surface_tracked(p)
        if tracked:
            print(f"  [OK]   {p} ({detail})")
        else:
            print(f"  [未入库] {p} ({detail})")
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
    if getattr(args, "json", False):
        report = {
            "ok": not due,
            "count": len(due),
            "due": [{"id": b["id"], "title": b.get("title", "")} for b in due],
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1
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
    print("=== 表面积实测（git tracked 口径，含子模块）===")
    print(f"{'指标':<18}{'当前':>10}{'基线(2026-08)':>16}{'变化':>16}   Y1 判据")
    print("-" * 88)
    for k, base in BASELINE.items():
        c = cur.get(k, 0)
        delta = c - base
        pct = (delta / base * 100) if base else 0
        tgt = Y1_TARGET.get(k, "—")
        tgt = "—" if tgt is None else str(tgt)
        print(f"{k:<18}{c:>10,}{base:>16,}{delta:>+10,}({pct:+.0f}%)   {tgt}")

    rc = 0
    print()
    # 保护量：测试行数下降 = 有害减法
    dt = cur.get("test_loc", 0) - BASELINE["test_loc"]
    if dt < 0:
        print(f"🔴 test_loc 下降 {-dt:,} 行 —— 有害减法。")
        print("   测试是保护量不是削减对象。删测试能让任何总量指标好看，但直接损害可维护性。")
        rc = 1
    else:
        print(f"✅ test_loc 未下降（{dt:+,}）")

    ds = cur.get("src_loc", 0) - BASELINE["src_loc"]
    print(f"   src_loc 变化 {ds:+,} 行  ← 观察量，由具体归并 bet 的去重量累计，不设百分比目标")

    dq = cur.get("gac_required", 0) - BASELINE["gac_required"]
    print(f"   gac_required 变化 {dq:+,}  ← 会拦人的规则才是真成本；advisory 删了没收益")

    print("\nD2 记账：把上面这几行贴进复盘 Q4。")
    return rc


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


def cmd_complete(data: dict, args) -> int:
    """台账完成: 校验 verify D0 入库 + retro 后置 status=done.

    P1 (方案 4): closeout 后自动回写台账, 防 done 状态滞后
    (记忆/台账脱节, 实际 done 远超记忆). 带 guard:
    - bet 存在且非 done
    - verify D0 检查通过 (write_surfaces 入库)
    - 可选 --force 跳过 guard (人工确认)
    """
    b = bet_by_id(data, args.bet_id)
    if b.get("status") == "done":
        print(f"[complete] {b['id']} 已是 done, 无需操作")
        return 0

    if not args.force:
        # D0 guard: write_surfaces 入库检查
        rc = 0
        for p in b.get("write_surfaces", []):
            if "*" in p:
                continue
            tracked, detail = _d0_surface_tracked(p)
            if not tracked:
                print(f"[complete] ❌ 未入库: {p} ({detail}; D0 铁律)")
                rc = 1
        if rc:
            print("[complete] 请先完成 D0 (write_surfaces 全部入库) 或 --force")
            return 1

    # 置 done (写 3y-bet-ledger.yaml, 非 .omo 状态)
    try:
        import datetime
        path = LEDGER
        text = path.read_text(encoding="utf-8")
        marker = f"id: {args.bet_id}"
        idx = text.find(marker)
        if idx < 0:
            print(f"[complete] ❌ 未找到 {args.bet_id}")
            return 1
        # 在该 bet 块内找 status: X → status: done
        block_end = text.find("\n- id:", idx + len(marker))
        if block_end < 0:
            block_end = len(text)
        block = text[idx:block_end]
        if "status: done" not in block:
            block_new = block.replace("status: ", "status: done\n  done_at: ",
                                      1) if "status:" in block else block
            # 用更精确替换: status: <old> → status: done (保留 done_at)
            import re
            block_new = re.sub(r"status: (\w+)", "status: done", block, count=1)
            block_new = block_new.replace(
                "status: done",
                f"status: done\n  done_at: {datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d')}",
                1,
            )
            text = text[:idx] + block_new + text[block_end:]
            path.write_text(text, encoding="utf-8")
        print(f"[complete] ✅ {b['id']} → done")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[complete] ❌ 写台账失败: {exc}")
        return 1


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
    pr = sub.add_parser("retro-due")
    pr.add_argument("--json", action="store_true")
    sub.add_parser("surface")
    sub.add_parser("gate").add_argument("window")
    sub.add_parser("lint")
    pc = sub.add_parser("complete")
    pc.add_argument("bet_id")
    pc.add_argument("--force", action="store_true")

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
        "complete": cmd_complete,
    }[args.cmd](data, args)


if __name__ == "__main__":
    raise SystemExit(main())
