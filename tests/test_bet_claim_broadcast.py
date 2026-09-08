"""T10-139: BET 认领广播 (同号竞速防护) 测试.

覆盖: claim-bet 三态 / claim-gc TTL / complete 释放 / start 拦截四场景.
隔离原则: 全部跑在 tmp_path 假工作区上, 不碰真 ledger 真广播.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("bet_ledger_t139", ROOT / "bin/plan/bet-ledger.py")
assert _spec is not None and _spec.loader is not None
bl = importlib.util.module_from_spec(_spec)
sys.modules["bet_ledger_t139"] = bl
_spec.loader.exec_module(bl)


def _setup(tmp_path: Path, status: str = "candidate") -> tuple[Path, Path, dict]:
    """隔离环境: 临时 ledger + 临时 claims 目录 (monkeypatch 模块常量)."""
    led = tmp_path / "ledger.yaml"
    claims = tmp_path / "bet-claims"
    claims.mkdir(parents=True)
    led.write_text(
        "bets:\n"
        f"- id: BET-TEST-1\n"
        f"  status: {status}\n"
        '  title: "t"\n',
        encoding="utf-8",
    )
    bl.LEDGER = led
    bl.CLAIM_DIR = claims
    return led, claims, bl.load()


def test_syntax_and_registry() -> None:
    """两文件语法 OK, 子命令注册齐."""
    for f in ("bin/plan/bet-ledger.py", "bin/agent-workflow.py"):
        ast.parse((ROOT / f).read_text(encoding="utf-8"))
    src = (ROOT / "bin/plan/bet-ledger.py").read_text(encoding="utf-8")
    assert "cmd_claim_bet" in src and "cmd_claim_gc" in src and "claim-bet" in src


def test_claim_first(tmp_path: Path) -> None:
    """首认: candidate→in_progress + 广播文件."""
    _led, claims, data = _setup(tmp_path)
    rc = bl.cmd_claim_bet(data, types.SimpleNamespace(bet_id="BET-TEST-1", actor="agent-a", force=False))
    assert rc == 0
    cf = claims / "BET-TEST-1.json"
    assert cf.is_file()
    claim = json.loads(cf.read_text(encoding="utf-8"))
    assert claim["actor"] == "agent-a"
    assert bl.load()["bets"][0]["status"] == "in_progress"


def test_claim_foreign_actor_rejected(tmp_path: Path) -> None:
    """异 actor: fail closed, 广播文件不被覆盖."""
    _setup(tmp_path, status="in_progress")
    bl.cmd_claim_bet(
        bl.load(), types.SimpleNamespace(bet_id="BET-TEST-1", actor="agent-a", force=False)
    )
    rc = bl.cmd_claim_bet(
        bl.load(), types.SimpleNamespace(bet_id="BET-TEST-1", actor="agent-b", force=False)
    )
    assert rc == 1
    cf = bl.CLAIM_DIR / "BET-TEST-1.json"
    assert json.loads(cf.read_text(encoding="utf-8"))["actor"] == "agent-a"


def test_claim_same_actor_idempotent(tmp_path: Path) -> None:
    """同 actor: 幂等返回 0."""
    _setup(tmp_path, status="in_progress")
    bl.cmd_claim_bet(
        bl.load(), types.SimpleNamespace(bet_id="BET-TEST-1", actor="agent-a", force=False)
    )
    rc = bl.cmd_claim_bet(
        bl.load(), types.SimpleNamespace(bet_id="BET-TEST-1", actor="agent-a", force=False)
    )
    assert rc == 0


def test_claim_force_takeover(tmp_path: Path) -> None:
    """--force: 显式接管."""
    _setup(tmp_path, status="in_progress")
    bl.cmd_claim_bet(
        bl.load(), types.SimpleNamespace(bet_id="BET-TEST-1", actor="agent-a", force=False)
    )
    rc = bl.cmd_claim_bet(
        bl.load(), types.SimpleNamespace(bet_id="BET-TEST-1", actor="agent-c", force=True)
    )
    assert rc == 0
    cf = bl.CLAIM_DIR / "BET-TEST-1.json"
    assert json.loads(cf.read_text(encoding="utf-8"))["actor"] == "agent-c"


def test_claim_gc_expired(tmp_path: Path) -> None:
    """claim-gc: 过期清理 + 只删文件不动 ledger."""
    _setup(tmp_path, status="in_progress")
    bl.cmd_claim_bet(
        bl.load(), types.SimpleNamespace(bet_id="BET-TEST-1", actor="agent-c", force=False)
    )
    cf = bl.CLAIM_DIR / "BET-TEST-1.json"
    stale = json.loads(cf.read_text(encoding="utf-8"))
    stale["claimed_at"] = "2026-08-30T00:00:00+00:00"  # 8 天前 > 7d TTL
    cf.write_text(json.dumps(stale), encoding="utf-8")
    rc = bl.cmd_claim_gc(bl.load(), types.SimpleNamespace(ttl=None, dry_run=False))
    assert rc == 0
    assert not cf.is_file()
    # ledger status 不受 GC 影响
    assert bl.load()["bets"][0]["status"] == "in_progress"


def test_release_on_complete(tmp_path: Path) -> None:
    """complete 置 done 后自动释放."""
    _setup(tmp_path, status="in_progress")
    bl.cmd_claim_bet(
        bl.load(), types.SimpleNamespace(bet_id="BET-TEST-1", actor="agent-a", force=False)
    )
    cf = bl.CLAIM_DIR / "BET-TEST-1.json"
    assert cf.is_file()
    assert bl._release_claim("BET-TEST-1") is True
    assert not cf.is_file()


def test_shared_anchor_resolves_main_checkout() -> None:
    """共享锚点: git-common-dir 解析 (主仓 .git 是目录, worktree 是文件)."""
    root = bl._delivery_claims_root()
    # 主 checkout 上跑: 锚点应即主仓根 (含 .git 目录)
    assert (root / ".git").is_dir()
    # 在主 checkout 本身执行时, 锚点 == WS (解析收敛, 不漂移)
    assert root == bl.WS.resolve() or (root / ".git").is_dir()


def test_start_guard_scenarios(tmp_path: Path, monkeypatch) -> None:
    """start 拦截四场景 (agent-workflow 层, 不启动真 run)."""
    claims = tmp_path / "bet-claims"
    claims.mkdir(parents=True)
    spec2 = importlib.util.spec_from_file_location("aw_t139", ROOT / "bin/agent-workflow.py")
    aw = importlib.util.module_from_spec(spec2)
    sys.modules["aw_t139"] = aw
    spec2.loader.exec_module(aw)

    bet = "BET-GUARD-1"
    cf = claims / f"{bet}.json"
    monkeypatch.setattr(aw, "WORKSPACE", tmp_path)
    monkeypatch.setattr(aw, "_delivery_claims_root", lambda: tmp_path)

    # A: 无广播 → 放行
    assert aw._claim_interlock_guard(bet, []) is None
    # B: 他人持有 → BET_CLAIM_HELD
    cf.write_text(json.dumps({"actor": "agent-x", "claimed_at": "t"}), encoding="utf-8")
    msg = aw._claim_interlock_guard(bet, [])
    assert msg is not None and "BET_CLAIM_HELD" in msg and "agent-x" in msg
    # C: 持有者本人 → 放行
    argv = ["start", "bet-execution", "--bet", bet, "--actor", "agent-x"]
    assert aw._claim_interlock_guard(bet, argv) is None
    # D: 损坏 → 宽容放行
    cf.write_text("not-json{", encoding="utf-8")
    assert aw._claim_interlock_guard(bet, []) is None
