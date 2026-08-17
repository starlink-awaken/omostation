"""Tests for sophia.kems_runtime — KEMS 四平面/三链/协议运行时.

补 kems_runtime 零测试债 (功能维度优化, sophia v1.0 测试补全)."""

from sophia.kems_runtime import Chains, KemsRuntime, Planes, Protocols


def test_planes_has_four_panes():
    assert len(Planes.MAP) == 4
    for key in (Planes.KNOWLEDGE, Planes.EXPERIENCE, Planes.METHODOLOGY, Planes.SYSTEM):
        assert key in Planes.MAP
        assert isinstance(Planes.MAP[key], str)
        assert len(Planes.MAP[key]) > 0


def test_chains_has_three_chains():
    assert len(Chains.MAP) == 3
    for key in (Chains.DATA, Chains.METHOD, Chains.EVOLUTION):
        assert key in Chains.MAP
        assert "->" in Chains.MAP[key]  # 链描述含数据流


def test_protocols_has_three_protocols():
    assert len(Protocols.MAP) == 3
    for key in (Protocols.KNOWLEDGE, Protocols.PROCESS, Protocols.EVOLUTION):
        assert key in Protocols.MAP


def test_kems_runtime_describe_structure():
    rt = KemsRuntime()
    d = rt.describe()
    assert set(d.keys()) == {"planes", "chains", "protocols"}
    assert len(d["planes"]) == 4
    assert len(d["chains"]) == 3
    assert len(d["protocols"]) == 3


def test_kems_runtime_describe_returns_copies():
    """describe() 返回的 dict 改动不影响类常量 MAP."""

    rt = KemsRuntime()
    d1 = rt.describe()
    d1["planes"]["custom"] = "injected"
    d2 = rt.describe()
    assert "custom" not in d2["planes"]


def test_plane_constants_distinct():
    assert len({Planes.KNOWLEDGE, Planes.EXPERIENCE, Planes.METHODOLOGY, Planes.SYSTEM}) == 4
    assert len({Chains.DATA, Chains.METHOD, Chains.EVOLUTION}) == 3
