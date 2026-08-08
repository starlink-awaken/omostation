"""P3: 能力目录写闭环测试.

覆盖:
- add(): 新增能力 (内存 + 写回 YAML)
- retire(): 标记 deprecated (写回 YAML)
- save(): 持久化到 bos-services.yaml, 保留原有条目
- 生命周期端到端: add → 内存可读 → retire → 状态 deprecated
"""

from __future__ import annotations

import pathlib

import pytest

from agora.mcp.capability_catalog import CapabilityCatalog


def _mk_catalog(tmp_path, services=None):
    """构造带临时 bos-services.yaml 的 catalog."""
    svcs = services or [
        {
            "uri": "bos://memory/kos/search",
            "domain": "memory",
            "package": "kos",
            "action": "search",
            "description": "KOS 搜索",
            "status": "active",
            "transport": "stdio",
        }
    ]
    yaml_path = tmp_path / "bos-services.yaml"
    import yaml

    yaml_path.write_text(
        yaml.safe_dump({"services": svcs}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return CapabilityCatalog(bos_yaml=str(yaml_path))


def test_load_reads_services(tmp_path):
    """load() 从 YAML 构建能力目录."""
    cat = _mk_catalog(tmp_path)
    caps = cat.load()
    assert "bos://memory/kos/search" in caps
    assert caps["bos://memory/kos/search"]["status"] == "active"


def test_add_writes_to_yaml(tmp_path):
    """add() 新增能力并写回 YAML (P3 写闭环)."""
    cat = _mk_catalog(tmp_path)
    cat.load()
    cat.add("bos://capability/omo/task/create", description="创建任务")
    # 内存可读
    assert cat.get("bos://capability/omo/task/create")["status"] == "active"
    # YAML 已持久化
    import yaml

    data = yaml.safe_load((tmp_path / "bos-services.yaml").read_text())
    uris = [s["uri"] for s in data["services"]]
    assert "bos://capability/omo/task/create" in uris
    # 原条目保留
    assert "bos://memory/kos/search" in uris


def test_retire_marks_deprecated(tmp_path):
    """retire() 标记 deprecated 并持久化."""
    cat = _mk_catalog(tmp_path)
    cat.load()
    ok = cat.retire("bos://memory/kos/search", reason="governance cleanup")
    assert ok is True
    assert cat.get("bos://memory/kos/search")["status"] == "deprecated"
    import yaml

    data = yaml.safe_load((tmp_path / "bos-services.yaml").read_text())
    entry = next(s for s in data["services"] if s["uri"] == "bos://memory/kos/search")
    assert entry["status"] == "deprecated"


def test_retire_unknown_returns_false(tmp_path):
    """retire 未知能力返回 False."""
    cat = _mk_catalog(tmp_path)
    cat.load()
    assert cat.retire("bos://nonexistent/foo") is False


def test_admit_retire_lifecycle_end_to_end(tmp_path):
    """add → get active → retire → get deprecated (端到端)."""
    cat = _mk_catalog(tmp_path)
    cat.load()
    uri = "bos://p3test/unique/newcap"  # 用独特 uri 避免 metrics 历史干扰僵尸判定
    cat.add(uri, description="P3 test capability")
    assert cat.get(uri)["status"] == "active"
    cat.retire(uri, reason="replaced by quota")
    assert cat.get(uri)["status"] == "deprecated"
    # 重新 load 验证持久化 (复用同一 YAML 文件, 不重建)
    cat2 = CapabilityCatalog(bos_yaml=str(tmp_path / "bos-services.yaml"))
    cat2.load()
    assert cat2.get(uri)["status"] == "deprecated"
