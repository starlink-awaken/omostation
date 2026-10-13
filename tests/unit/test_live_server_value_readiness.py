"""Live server value readiness must count only Ledger-truth Episodes (v3).

2026-10-13 v3: 业务价值唯一真源 = OMO causal Event Ledger 的 value-truth 快照
(personal_value_truth.value_truth, schema=value-truth-snapshot/v1);
legacy validation 快照 / panel_value 只作 advisory。测试断言随之迁移。
"""

from __future__ import annotations

from importlib.machinery import SourceFileLoader
from pathlib import Path
import importlib.util
import shutil
import sys
import tempfile

HOST_DIR = Path(__file__).resolve().parents[2] / "bin/panorama/assets/host"


def _module():
    from panorama_host_stubs import deploy_collectors, install_host_stubs

    with tempfile.TemporaryDirectory(prefix="live-server-value-readiness-") as directory:
        deployed = Path(directory)
        shutil.copy2(HOST_DIR / "observatory_query.py.asset", deployed / "observatory_query.py")
        server_path = deployed / "live_server_under_test.py"
        shutil.copy2(HOST_DIR / "live_server.py.asset", server_path)
        # live_server 2026-10-13 起模块级 import collectors — 部署包 + stub 宿主符号
        deploy_collectors(HOST_DIR, deployed)
        install_host_stubs(deployed)
        query_loader = SourceFileLoader(
            "zhixing_observatory_query_value_readiness_test",
            str(deployed / "observatory_query.py"),
        )
        query_spec = importlib.util.spec_from_loader(query_loader.name, query_loader)
        assert query_spec is not None and query_spec.loader is not None
        query_module = importlib.util.module_from_spec(query_spec)
        sys.modules[query_spec.name] = query_module
        query_loader.exec_module(query_module)
        sys.modules["observatory_query"] = query_module
        loader = SourceFileLoader("zhixing_live_server_value_readiness_test", str(server_path))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module


# legacy v2 validation 快照 — v3 只透传到 advisory, 不进任何计数
_LEGACY_VALIDATION = {
    "schema": "value-evidence-validation/v2",
    "ok": True,
    "available": True,
    "records": 20,
    "v2_records": 0,
    "legacy_records": 20,
    "legacy_qualifying": 1,
    "qualifying": 0,
    "target": 30,
}


def _snapshot(
    *,
    qualifying_weeks,
    total_episodes,
    truth_available=True,
    truth_schema="value-truth-snapshot/v1",
    status="not_proven",
    personal_value="pending",
    gate_gaps=None,
):
    weeks = [
        {"week": f"2026-W{idx}", "qualifying_episodes": n, "gate_met": n >= 4,
         "summed_saved_seconds": 45 * n}
        for idx, n in enumerate(qualifying_weeks, start=1)
    ]
    qualifying = sum(qualifying_weeks)
    return {
        "generated_at": "2026-10-13T00:00:00Z",
        "generation_id": "generation",
        # legacy 面板 (v3 只当 advisory 读取, 不参与计数)
        "panel_value": {
            "schema": "panel-value/v1",
            "state": "not_proven",
            "samples": {"records": 28, "qualifying": 1, "accepted": 24, "adjudicated": 28,
                        "net_saved_seconds": 90},
        },
        "personal_value_truth": {
            "available": truth_available,
            "value_truth": {
                "schema": truth_schema,
                "status": status,
                "reason": None,
                "truth_axes": {"personal_value": personal_value},
                "metrics": {
                    "total_episodes": total_episodes,
                    "weekly_samples": weeks,
                    "verdict_distribution": {"accept": total_episodes, "reject": 0},
                    "gate_gaps": gate_gaps
                    if gate_gaps is not None
                    else [f"样本 {qualifying}/30 不足"],
                },
            },
        },
        "value_evidence_validation": dict(_LEGACY_VALIDATION),
    }


def test_legacy_qualifying_is_not_counted_as_business_value():
    module = _module()
    # legacy 快照宣称 legacy_qualifying=1 / panel_value.qualifying=1,
    # 但 Ledger truth 里 qualifying=0 → 计数必须是 0 (legacy 只进 advisory)
    payload = module.value_proof_readiness_payload(
        _snapshot(qualifying_weeks=[0], total_episodes=20)
    )

    assert payload["schema_version"] == "agent-value-proof-readiness/v3"
    assert payload["samples"]["qualifying"] == 0
    assert payload["samples"]["remaining"] == 30
    assert payload["samples"]["records"] == 20
    assert payload["thresholds"][0]["current"] == 0
    assert payload["thresholds"][0]["gate"] == "Ledger-bound Episodes 0/30"
    # legacy 快照原样落在 advisory, 不参与任何样本口径
    assert payload["advisory"]["validation"]["legacy_qualifying"] == 1
    assert "advisory only" in payload["evidence_rule"]


def test_ledger_qualifying_episodes_count_toward_target():
    module = _module()
    payload = module.value_proof_readiness_payload(
        _snapshot(qualifying_weeks=[1, 1], total_episodes=3)
    )

    assert payload["samples"]["qualifying"] == 2
    assert payload["samples"]["remaining"] == 28
    assert payload["samples"]["records"] == 3
    assert payload["thresholds"][0]["current"] == 2


def test_invalid_or_unavailable_truth_fails_closed_to_zero():
    module = _module()
    # truth envelope 不可用, 即便 value_truth 里塞了 qualifying=99 也必须 fail-closed
    payload = module.value_proof_readiness_payload(
        _snapshot(
            qualifying_weeks=[99],
            total_episodes=99,
            truth_available=False,
        )
    )

    assert payload["state"] == "UNPROVABLE"
    assert payload["state_reason"] == ["ledger_value_truth_unavailable"]
    assert payload["samples"]["qualifying"] == 0
    assert payload["samples"]["remaining"] == 30
    assert payload["samples"]["records"] == 0
