"""BET-Y1Q4-T2-02 IM triage: whitelist gate, directives, cards, red lines."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location("im", ROOT / "projects/agora/src/agora/server/tools_bos/im.py")
assert spec and spec.loader
IM = importlib.util.module_from_spec(spec)
sys.modules["im"] = IM
spec.loader.exec_module(IM)


def _msg(text, chat="wecom:work-core", mentions=False, mid="m1"):
    return IM.ImMessage(id=mid, platform="wecom", chat_id=chat, sender="同事A", text=text, mentions_me=mentions)


def test_whitelist_blocks_unknown_chat():
    assert IM.whitelist_gate(_msg("查一下医保目录", chat="wechat:random")) is False
    assert IM.whitelist_gate(_msg("查一下医保目录")) is True  # keyword hit


def test_whitelist_mention_passes_without_keyword():
    assert IM.whitelist_gate(_msg("你看这个方案怎么样", mentions=True)) is True
    assert IM.whitelist_gate(_msg("今天天气不错啊")) is False  # no keyword/directive
    assert IM.whitelist_gate(_msg("你看这个方案怎么样")) is True  # 方案 keyword


def test_parse_directive_routes():
    cases = {
        "帮我查一下医保目录": "query",
        "起草一份复函": "draft",
        "这份申请我同意了": "approve",
        "催一下运维工单": "urge",
        "今天天气不错": "none",
    }
    for text, expected in cases.items():
        assert IM.parse_directive(text).action == expected, text


def test_directive_payload_strips_phrase():
    d = IM.parse_directive("帮我查一下医保目录的最新版本")
    assert d.action == "query" and "医保目录" in d.payload
    assert "查一下" not in d.payload


def test_task_card_priority_and_deadline():
    card = IM.to_task_card(_msg("催一下回函，明天截止"), IM.parse_directive("催一下回函，明天截止"))
    assert card.priority == "high"  # urge action
    assert card.deadline_hint_days == 1.0
    assert card.status == "pending_approval"  # red line


def test_triage_noise_dropped_and_cards_pending():
    result = IM.triage_session(
        [
            _msg("催一下回函", mid="a"),
            _msg("广告", chat="wechat:stranger", mid="b"),
            _msg("早上好", mid="c"),  # whitelisted, no directive → passive
        ]
    )
    assert result["dropped"] == ["b", "c"]  # b: 非白名单群; c: 白名单群无信号(零噪音)
    assert len(result["cards"]) == 1 and result["cards"][0]["message_id"] == "a"
    assert result["passive"] == []
    assert all(c["status"] == "pending_approval" for c in result["cards"])
    assert result["gateway"] == "bos://im/session/triage"


def test_verify_contract():
    report = IM.test_session_ingress()
    assert report["accuracy"] >= 0.95
    assert all(report["checks"].values())
