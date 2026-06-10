"""Tests for omo trail seed (Round 19 P0 — 让 trail 业务真落地).

覆盖:
  1. omo_trail_seed.SEED_STEPS 是 5 条, 含 7 字段 (ts/actor/action/target/status/duration_ms/parent_step_id)
  2. cmd_trail_seed 写 5 条到 log, 每条 Pydantic 校验通过
  3. 写入默认路径后, omo_trail.read_trail 能读回
  4. CLI `omo trail seed --log X` 退出码 0, log 出现 5 条
  5. 不污染默认路径 — 测试用 tmp_path

设计:
  - 验证 SEED_STEPS 内容 (actor=agent:laowang 模式, 反映老王工作流)
  - 验证 Pydantic 校验通过 (schema=OmoTrailRecord 写时锁)
  - 验证业务接入模式: 写完后 omo_trail.read_trail 立即可查
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

OMO_SRC = Path(__file__).resolve().parents[1] / "src"
if str(OMO_SRC) not in sys.path:
    sys.path.insert(0, str(OMO_SRC))


# ── 1. SEED_STEPS 内容契约 ────────────────────────────────


def test_seed_steps_count_and_fields():
    """SEED_STEPS 是 5 条样例, 每条含 actor/action/target/status/duration_ms 5 关键字段."""
    from omo.omo_trail_seed import SEED_STEPS

    assert len(SEED_STEPS) == 5, f"expected 5 seed steps, got {len(SEED_STEPS)}"
    for i, step in enumerate(SEED_STEPS):
        # 关键 5 字段
        assert "actor" in step, f"step {i} missing actor"
        assert "action" in step, f"step {i} missing action"
        assert "target" in step, f"step {i} missing target"
        assert "status" in step, f"step {i} missing status"
        assert "duration_ms" in step, f"step {i} missing duration_ms"
        # actor 模式
        assert step["actor"] == "agent:laowang", f"step {i} actor 应是 agent:laowang"


# ── 2. cmd_trail_seed 写 5 条 + Pydantic 校验通过 ───────────


def test_cmd_trail_seed_writes_five_records_pydantic_valid(tmp_path, capsys):
    """cmd_trail_seed 写 5 条到指定 log, 每条 OmoTrailRecord.model_validate 通过."""
    from omo.omo_io_schemas import OmoTrailRecord
    from omo.omo_trail_seed import cmd_trail_seed
    from omo.omo_trail import read_trail

    log_path = tmp_path / "trail-seed.jsonl"
    args = type("Args", (), {"log": log_path})()  # 简易 Namespace
    rc = cmd_trail_seed(args)
    assert rc == 0

    # 读出 5 条
    steps = read_trail(log_path=log_path, limit=10)
    assert len(steps) == 5

    # Pydantic 校验
    for s in steps:
        OmoTrailRecord.model_validate(s)  # 不抛 = 通过
        # ts 必须是 Z 结尾
        assert s["ts"].endswith("Z")

    # 提示语
    captured = capsys.readouterr()
    assert "✅ trail seed 写入 5 条 step" in captured.out
    assert "agent:laowang" in captured.out


# ── 3. 5 条样例 action 多样性 ─────────────────────────────


def test_seed_steps_action_diversity():
    """SEED_STEPS 涵盖 5 种 action: edit/exec/test/commit/audit (代表老王工作流)."""
    from omo.omo_trail_seed import SEED_STEPS

    actions = {step["action"] for step in SEED_STEPS}
    assert actions == {"edit", "exec", "test", "commit", "audit"}, (
        f"action 集合应覆盖老王工作流 5 种, got {actions}"
    )


# ── 4. CLI 集成: omo.cli trail seed 退出码 0 ──────────


def test_cli_trail_seed_subprocess(tmp_path):
    """`python -m omo.cli trail seed --log X` 退出码 0, log 出现 5 条."""
    log_path = tmp_path / "cli-seed.jsonl"
    r = subprocess.run(
        [sys.executable, "-m", "omo.cli", "trail", "seed", "--log", str(log_path)],
        capture_output=True, text=True, timeout=15,
        cwd=str(OMO_SRC.parent.parent),
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    assert "✅ trail seed 写入 5 条 step" in r.stdout

    # log 文件 5 条
    lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 5
    for line in lines:
        rec = json.loads(line)
        assert rec["actor"] == "agent:laowang"


# ── 5. 与既有 omo_trail 接口兼容 ────────────────────────


def test_seed_uses_append_only_log_via_omo_trail():
    """seed 走 omo.omo_trail.record_step (复用 AppendOnlyLog + Pydantic 校验), 不直接 open()."""
    from omo.omo_trail_seed import cmd_trail_seed
    from omo import omo_trail
    import inspect

    # cmd_trail_seed 内部用 record_step (走 AppendOnlyLog)
    src = inspect.getsource(cmd_trail_seed)
    assert "record_step" in src
    assert "AppendOnlyLog" not in src, "seed 不应直接 AppendOnlyLog (应走 record_step wrapper)"
