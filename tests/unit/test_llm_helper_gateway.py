"""llm_ask 必须经 aetherforge 门面按别名调用 (2026-09-29 邮件闭环实测).

此前进程内加载网关库, 请求不存在的 qwen-3.8-27b 被静默换成 mythos-fast。
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(params=["bin/ssot", "runtime/ssot-stable"])
def modules(request, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / request.param))
    for name in ("_llm_helper", "llm_provider", "mail_agent"):
        sys.modules.pop(name, None)
    import _llm_helper
    import mail_agent

    sent: list[dict] = []

    def fake_urlopen(req, timeout=None):
        sent.append({"url": req.full_url, **json.loads(req.data)})
        return io.BytesIO(json.dumps({"model": "x", "choices": [{"message": {"content": '{"category":"任务"}'}}]}).encode())

    monkeypatch.setattr(_llm_helper.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(_llm_helper, "_gateway_key", lambda: "k")
    monkeypatch.setattr(mail_agent, "HISTORY", Path(request.getfixturevalue("tmp_path")) / "h.jsonl")
    return _llm_helper, mail_agent, sent


def test_llm_ask_routes_through_gateway_with_default_alias(modules):
    helper, _, sent = modules
    assert helper.llm_ask("hi") == '{"category":"任务"}'
    assert sent[0]["url"].endswith("/v1/chat/completions")
    assert sent[0]["model"] == "fast"


def test_mail_classification_uses_triage_alias(modules):
    _, mail_agent, sent = modules
    from mail_reader import Mail

    cls = mail_agent.classify_mail(Mail(subject="关于报送数据的通知", sender="a@b", body="请于10月10日前报送"))
    assert cls["category"] == "任务"
    assert sent[0]["model"] == "triage"
    assert "收件方是否被要求做事" in sent[0]["messages"][0]["content"]


@pytest.mark.parametrize("src_dir", ["bin/ssot", "runtime/ssot-stable"])
def test_admin_inbox_processes_the_triggering_mail(src_dir, monkeypatch):
    """journey 由某封邮件触发时处理它本身, 不去重读邮箱。"""
    monkeypatch.syspath_prepend(str(ROOT / src_dir))
    for name in ("admin_scenes", "mail_reader", "mail_agent"):
        sys.modules.pop(name, None)
    import admin_scenes
    import mail_reader

    monkeypatch.setattr(mail_reader, "read_netease_mail", lambda *a, **k: pytest.fail("不应重读邮箱"))
    out = admin_scenes.dispatch_admin_inbox({"subject": "关于报送数据的通知", "category": "任务"}, {})
    assert out["has_task"] is True
    assert out["latest_subject"] == "关于报送数据的通知"


@pytest.mark.parametrize("src_dir", ["bin/ssot", "runtime/ssot-stable"])
@pytest.mark.parametrize(("steps", "ok"), [(1, False), (4, True)])
def test_journey_counts_as_triggered_only_past_entry_step(src_dir, steps, ok, monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(ROOT / src_dir))
    sys.modules.pop("mail_daemon", None)
    import mail_daemon
    from mail_reader import Mail

    monkeypatch.setattr(mail_daemon, "JOURNEY_TRIGGERED", tmp_path / "seen.json")
    stdout = f'{{"status": "completed", "steps": {steps}}}'
    monkeypatch.setattr(
        mail_daemon.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 0, "stdout": stdout})()
    )
    res = mail_daemon._trigger_journey_live(Mail(subject="s", sender="x", body="b"), {"category": "任务"})
    assert res["ok"] is ok
