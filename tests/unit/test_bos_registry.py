"""Tests for agora.mcp.resolver.bos_registry — Phase 42 声明式注册表。"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
import yaml

# 用一个有效的 YAML 做测试数据
SAMPLE_YAML = """services:
  - uri: "bos://memory/kos/search"
    domain: memory
    package: kos
    action: search
    transport: stdio
    command: ["uv", "run", "--directory", "projects/kairon", "python", "-m", "kos.cli", "search"]
    description: "KOS 知识图谱检索入口"
  - uri: "bos://governance/omo/state"
    domain: governance
    package: omo
    action: state
    transport: internal
    description: "OMO 状态查询 (internal)"
  - uri: "bos://analysis/minerva/research"
    domain: analysis
    package: minerva
    action: research
    transport: stdio
    command: ["uv", "run", "--directory", "projects/kairon", "python", "-m", "minerva.cli", "research"]
    description: "Minerva 深度研究"
  - uri: "bos://capability/forge/exec-tool"
    domain: capability
    package: forge
    action: exec-tool
    transport: mcp_stdio
    command: ["uv", "run", "--directory", "projects/kairon", "python", "-m", "forge", "serve", "--action", "exec-tool"]
    description: "[UNIMPLEMENTED] Forge 工具执行"
  - uri: "bos://persona/core-models/schema"
    domain: persona
    package: core-models
    action: schema
    transport: stdio
    command: ["uv", "run", "--directory", "projects/kairon", "python", "-m", "core_models.cli", "schema"]
    description: "核心模型 Schema"
"""


@pytest.fixture
def sample_yaml_path():
    """创建一个临时的 YAML 文件用于测试。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(SAMPLE_YAML)
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def invalid_yaml_path():
    """创建一个非 YAML 文件。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("not: valid: yaml: [[[")
        path = f.name
    yield path
    os.unlink(path)


class TestBosRegistryLoader:
    """BOS YAML 注册表加载器测试。"""

    def test_load_from_yaml(self, sample_yaml_path):
        """正常加载 5 条路由。"""
        from agora.mcp.resolver.bos_registry import load_from_yaml

        services = load_from_yaml(sample_yaml_path)
        assert len(services) == 5

    def test_load_from_yaml_fields(self, sample_yaml_path):
        """验证 BosService 字段正确映射。"""
        from agora.mcp.resolver.bos_registry import load_from_yaml

        services = load_from_yaml(sample_yaml_path)
        svc = services[0]
        assert svc.uri == "bos://memory/kos/search"
        assert svc.domain == "memory"
        assert svc.package == "kos"
        assert svc.action == "search"
        assert svc.transport == "stdio"
        assert len(svc.command) > 0

    def test_load_internal_transport(self, sample_yaml_path):
        """internal transport 可以没有 command。"""
        from agora.mcp.resolver.bos_registry import load_from_yaml

        services = load_from_yaml(sample_yaml_path)
        svc = services[1]  # bos://governance/omo/state
        assert svc.transport == "internal"
        assert svc.command == []

    def test_load_nonexistent_file(self):
        """不存在的文件抛 FileNotFoundError。"""
        from agora.mcp.resolver.bos_registry import load_from_yaml

        with pytest.raises(FileNotFoundError):
            load_from_yaml("/tmp/nonexistent-bos-services.yaml")

    def test_load_invalid_yaml(self, invalid_yaml_path):
        """非 YAML 格式抛异常。"""
        from agora.mcp.resolver.bos_registry import load_from_yaml

        with pytest.raises(yaml.YAMLError):
            load_from_yaml(invalid_yaml_path)


class TestBosRegistryInfo:
    """注册表统计信息测试。"""

    def test_registry_info(self, sample_yaml_path):
        from agora.mcp.resolver.bos_registry import registry_info

        info = registry_info(sample_yaml_path)
        assert info["total"] == 5
        assert "memory" in info["domains"]
        assert info["transports"]["stdio"] >= 2
        assert len(info["unimplemented"]) == 1
        assert "forge" in info["unimplemented"][0]

    def test_registry_info_json_serializable(self, sample_yaml_path):
        """统计信息应是 JSON 可序列化的。"""
        from agora.mcp.resolver.bos_registry import registry_info

        info = registry_info(sample_yaml_path)
        dumped = json.dumps(info)
        assert isinstance(dumped, str)


class TestBosRegistryValidate:
    """注册表校验测试。"""

    def test_validate_ok(self, sample_yaml_path):
        from agora.mcp.resolver.bos_registry import validate_registry

        errors = validate_registry(sample_yaml_path)
        # 5 条路由中 4 条标准格式，1 条 forge 是 mcp_stdio 但也是合法 transport
        assert any("✅" in e for e in errors)

    def test_validate_detect_duplicate(self):
        """检测重复 URI。"""
        duplicate_yaml = """services:
  - uri: "bos://memory/kos/search"
    domain: memory
    package: kos
    action: search
    transport: stdio
    command: ["echo", "test"]
    description: "dup1"
  - uri: "bos://memory/kos/search"
    domain: memory
    package: kos
    action: search
    transport: stdio
    command: ["echo", "test2"]
    description: "dup2"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(duplicate_yaml)
            path = f.name
        try:
            from agora.mcp.resolver.bos_registry import validate_registry

            errors = validate_registry(path)
            assert any("重复 URI" in e for e in errors)
        finally:
            os.unlink(path)

    def test_validate_detect_missing_uri(self):
        """检测缺少 uri 字段（加载时 KeyError）。"""
        bad_yaml = """services:
  - domain: memory
    action: test
    transport: stdio
    command: ["echo"]
    description: "no uri"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(bad_yaml)
            path = f.name
        try:
            from agora.mcp.resolver.bos_registry import validate_registry

            errors = validate_registry(path)
            assert any("加载失败" in e for e in errors)
        finally:
            os.unlink(path)

    def test_validate_missing_file(self):
        """文件不存在时返回错误列表。"""
        from agora.mcp.resolver.bos_registry import validate_registry

        errors = validate_registry("/tmp/definitely-not-exist.yaml")
        assert any("加载失败" in e for e in errors)


class TestDefaultPath:
    """默认路径解析测试。"""

    def test_default_path_is_yaml(self):
        from agora.mcp.resolver.bos_registry import DEFAULT_REGISTRY_PATH

        assert str(DEFAULT_REGISTRY_PATH).endswith("bos-services.yaml")
        assert "etc" in str(DEFAULT_REGISTRY_PATH)

    def test_default_path_env_override(self, monkeypatch):
        from agora.mcp.resolver.bos_registry import load_from_yaml

        monkeypatch.setenv("AGORA_BOS_REGISTRY", "/tmp/custom-path.yaml")
        with pytest.raises(FileNotFoundError):
            load_from_yaml()
        monkeypatch.delenv("AGORA_BOS_REGISTRY", raising=False)
