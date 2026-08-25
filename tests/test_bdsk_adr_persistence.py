from pathlib import Path

import pytest

from agora.server.tools_bos import persona_bdsk_evaluate


@pytest.mark.asyncio
async def test_bdsk_evaluate_rejects_automatic_adr_persistence(tmp_path, monkeypatch):
    target_dir = tmp_path / "decisions"

    async def must_not_call(*_args, **_kwargs):
        raise AssertionError("compute must not run for a forbidden persistence request")

    monkeypatch.setattr("agora.server.tools_bos.bdsk._invoke_compute", must_not_call)
    res = await persona_bdsk_evaluate(
        topic="Adaptive Edge Routing and Memory Probing",
        mode="deep",
        persist_adr=True,
        adr_dir=str(target_dir),
    )
    assert res["status"] == "error"
    assert res["proof_state"] == "not_proven"
    assert res["verdict"] == "NOT_PROVEN"
    assert res["error_code"] == "automatic_adr_persistence_disabled"
    assert not target_dir.exists()


@pytest.mark.asyncio
async def test_bdsk_evaluate_legacy_adr_dir_never_writes_without_flag(
    tmp_path, monkeypatch
):
    target_dir = tmp_path / "decisions-unused"

    async def fake_resolve(_uri, **_kwargs):
        return {"status": "error", "error": "offline"}

    monkeypatch.setattr("agora.server.tools_bos.bdsk._invoke_compute", fake_resolve)
    res = await persona_bdsk_evaluate(
        topic="Apple Silicon Hardware Pressure Probe",
        mode="deep",
        persist_adr=False,
        adr_dir=str(target_dir),
    )
    assert res["status"] == "error"
    assert not target_dir.exists()
