"""Unit tests for B.D.S.K. Virtual Board Consensus Engine & Persona Router."""

from runtime.board_engine import (
    BoardConsensusEngine,
    BoardMode,
    PersonaRole,
    PersonaRouter,
    dispatch_board_command,
)


def test_persona_router_explicit_mention():
    role, cleaned = PersonaRouter.parse_at_mention(
        "@Devil 我们是否要重构底层的控制面通信索引？"
    )
    assert role == PersonaRole.DEVIL
    assert cleaned == "我们是否要重构底层的控制面通信索引？"


def test_persona_router_no_mention():
    role, cleaned = PersonaRouter.parse_at_mention("简单修改一下按钮的颜色")
    assert role is None
    assert cleaned == "简单修改一下按钮的颜色"


def test_auto_route_mode_a():
    mode = PersonaRouter.auto_route("分析整体架构升级与战略重构方案")
    assert mode == BoardMode.MODE_A


def test_auto_route_mode_b():
    mode = PersonaRouter.auto_route("修复登录表单提示错别字")
    assert mode == BoardMode.MODE_B


def test_execute_mode_a_full_debate():
    engine = BoardConsensusEngine(session_id="test-mode-a")
    res = engine.execute(
        "@Sage 进行全栈控制面系统重构与架构评审", mode=BoardMode.MODE_A
    )
    assert res.mode == BoardMode.MODE_A.value
    assert res.status == "CONSENSUS_REACHED"
    assert len(res.transcript) == 4
    assert res.transcript[0].persona == PersonaRole.BUILDER
    assert res.transcript[1].persona == PersonaRole.DEVIL
    assert res.transcript[2].persona == PersonaRole.SAGE
    assert res.transcript[3].persona == PersonaRole.KEEPER
    assert res.adr_draft is not None
    assert "ADR-BDSK" in res.adr_draft["title"]
    assert len(res.action_items) == 4


def test_execute_mode_b_agile_path():
    engine = BoardConsensusEngine(session_id="test-mode-b")
    res = engine.execute("优化首页加载性能", mode=BoardMode.MODE_B)
    assert res.mode == BoardMode.MODE_B.value
    assert res.status == "APPROVED"
    assert len(res.transcript) == 2
    assert res.transcript[0].persona == PersonaRole.BUILDER
    assert res.transcript[1].persona == PersonaRole.KEEPER
    assert res.adr_draft is None
    assert len(res.action_items) == 2


def test_dispatch_board_command():
    payload = {
        "proposal": "@Builder 落地系统架构的最小可行性版本",
        "mode": "auto",
        "session_id": "rpc-test-01",
    }
    out = dispatch_board_command(payload)
    assert out["ok"] is True
    res_dict = out["result"]
    assert res_dict["mode"] == "Mode-A"
    assert res_dict["status"] == "CONSENSUS_REACHED"
    assert len(res_dict["transcript"]) == 4
