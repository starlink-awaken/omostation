"""集成测试 — 生态无关的核心流程"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false


def test_multi_hop_derivation():
    """多层推导链：D-F→INF-L1→INF-L2"""
    from ontoderive.theories.bayesian import BayesianNetwork

    bn = BayesianNetwork()
    bn.add_fact("D-F1", 0.95, "事实1")
    bn.add_fact("D-F2", 0.90, "事实2")
    bn.add_inference("INF-L1：供需矛盾", ["D-F1", "D-F2"], 0.85, "推论1")
    bn.add_inference("INF-L2：平台方案", ["INF-L1：供需矛盾"], 0.80, "推论2")
    bn.finalize()
    assert len(bn.detect_cycles()) == 0
    result = bn.propagate()
    conf_l1 = result["nodes"].get("INF-L1：供需矛盾", {}).get("confidence", 0)
    conf_l2 = result["nodes"].get("INF-L2：平台方案", {}).get("confidence", 0)
    assert conf_l1 > 0.8, f"L1 conf={conf_l1}"
    assert conf_l2 > 0.65, f"L2 conf={conf_l2}"
    assert conf_l2 < conf_l1, "间接推导置信度应低于直接推导"
