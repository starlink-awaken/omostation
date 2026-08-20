"""The BDSK shadow sandbox is a static scanner, never an authorization source."""

from importlib import util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "bin" / "gac" / "bdsk-shadow-sandbox.py"
SPEC = util.spec_from_file_location("bdsk_shadow_sandbox", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_static_clear_never_authorizes_commit(monkeypatch, capsys, tmp_path):
    sandbox = MODULE.BDSKShadowSandbox(tmp_path)
    monkeypatch.setattr(sandbox, "get_diff_text", lambda: "+++ b/README.md\n+safe")

    result = sandbox.simulate()

    assert result["status"] == "STATIC_CLEAR"
    assert result["proof_state"] == "static_findings_only"
    assert result["commit_authorized"] is False
    assert result["runtime_evaluated"] is False

    monkeypatch.setattr(MODULE, "BDSKShadowSandbox", lambda: sandbox)
    assert MODULE.main() == 0
    output = capsys.readouterr().out
    assert "不构成 Commit/Push/Merge 授权" in output
    assert "允许 Commit" not in output
    assert "PASS" not in output


def test_static_finding_is_reported_without_claiming_runtime_proof(monkeypatch, tmp_path):
    sandbox = MODULE.BDSKShadowSandbox(tmp_path)
    monkeypatch.setattr(
        sandbox,
        "get_diff_text",
        lambda: "+++ b/danger.sh\n+rm -rf /tmp/example",
    )

    result = sandbox.simulate()

    assert result["status"] == "STATIC_FINDINGS"
    assert result["proof_state"] == "static_findings_only"
    assert result["commit_authorized"] is False
    assert result["runtime_evaluated"] is False
    assert result["findings"]


def test_unchanged_context_does_not_create_a_false_static_finding(
    monkeypatch, tmp_path
):
    sandbox = MODULE.BDSKShadowSandbox(tmp_path)
    monkeypatch.setattr(
        sandbox,
        "get_diff_text",
        lambda: "+++ b/safe.sh\n rm -rf appears only in unchanged context\n+safe",
    )

    assert sandbox.simulate()["status"] == "STATIC_CLEAR"
