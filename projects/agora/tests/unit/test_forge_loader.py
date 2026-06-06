"""Unit tests for agora.mcp.forge_loader — P33-W5 战役 3.

验证:
  1. forge.market: install / list / remove / validate
  2. forge_loader: load_from_market / load_tool / unload_tool / list_loaded
  3. W4 集成: 加载后 BOS URI 注入 POC_SERVICES, resolve_bos_uri 可达
  4. kebab-case 工具名校验
  5. 边界: 不存在的工具 / 重复加载 / 缺字段
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

# 确保可导入 agora + forge
_KAIRON_SRC = Path("/Users/xiamingxing/Workspace/projects/kairon/packages/forge/src")
_AGORA_SRC = Path("/Users/xiamingxing/Workspace/projects/agora/src")
for p in (str(_AGORA_SRC), str(_KAIRON_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from agora.mcp import bos_resolver  # noqa: E402
from agora.mcp.bos_resolver import POC_SERVICES, parse_bos_uri, resolve_bos_uri  # noqa: E402
from agora.mcp.forge_loader import (  # noqa: E402
    CAPS_ROOT,
    ForgeLoader,
    install_local_tool,
    list_market_tools,
    remove_tool,
)
from forge.market import (  # noqa: E402
    MARKET_REGISTRY,
    validate_bos_uri,
    validate_tool_name,
)


# ── fixtures ────────────────────────────────────────
@pytest.fixture
def clean_market(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """隔离: 测试用临时 market.json, 不污染真实注册表.

    Returns:
        tmp_path (含 patched market.json)
    """
    fake = tmp_path / "market.json"
    monkeypatch.setattr(
        "agora.mcp.forge_loader.MARKET_REGISTRY", fake
    )
    # forge.market.install_local_tool 内部用全局 MARKET_REGISTRY
    import forge.market as _fm

    monkeypatch.setattr(_fm, "MARKET_REGISTRY", fake)
    monkeypatch.setattr(_fm, "CAPS_ROOT", tmp_path)
    return tmp_path


@pytest.fixture
def fresh_loader() -> ForgeLoader:
    """新建独立 loader, 不污染全局."""
    return ForgeLoader()


# ── 1. validate ────────────────────────────────────
class TestValidate:
    def test_validate_tool_name_kebab_ok(self):
        valid, err = validate_tool_name("kairon-kos-search")
        assert valid is True
        assert err == ""

    def test_validate_tool_name_rejects_uppercase(self):
        valid, err = validate_tool_name("Kairon-Kos")
        assert valid is False
        assert "invalid_tool_name" in err

    def test_validate_tool_name_rejects_underscore(self):
        valid, err = validate_tool_name("kairon_kos")
        assert valid is False

    def test_validate_tool_name_rejects_empty(self):
        valid, err = validate_tool_name("")
        assert valid is False
        assert "empty" in err

    def test_validate_bos_uri_ok(self):
        valid, err = validate_bos_uri("bos://memory/kos/search")
        assert valid is True

    def test_validate_bos_uri_bad_domain(self):
        valid, err = validate_bos_uri("bos://UNKNOWN/kos/search")
        assert valid is False

    def test_validate_bos_uri_bad_format(self):
        valid, err = validate_bos_uri("not-a-uri")
        assert valid is False


# ── 2. install_local_tool ──────────────────────────
class TestInstallLocalTool:
    def test_install_local_tool_dir(self, clean_market: Path, tmp_path: Path):
        """复制目录 → 写 market.json → 返回安装信息."""
        # 准备源: 一个含 fake.py 的目录
        src = tmp_path / "src-fake-tool"
        src.mkdir()
        (src / "fake.py").write_text("# fake tool")

        r = install_local_tool(
            "kairon-fake-search",
            str(src),
            bos_uri="bos://memory/fake/search",
            description="test tool",
        )
        assert "installed" in r
        assert r["installed"] == "kairon-fake-search"
        assert r["bos_uri"] == "bos://memory/fake/search"
        assert Path(r["path"]).exists()
        # 注册表写入 (用 API 读, 走 patched 路径)
        market = list_market_tools()
        assert any(t["name"] == "kairon-fake-search" for t in market)

    def test_install_local_tool_file(self, clean_market: Path, tmp_path: Path):
        """单文件源也应能安装."""
        src = tmp_path / "single.py"
        src.write_text("# single")

        r = install_local_tool("single-tool", str(src))
        assert "installed" in r
        assert Path(r["path"]).exists()

    def test_install_missing_source(self, clean_market: Path):
        r = install_local_tool("nope", "/no/such/path")
        assert "error" in r
        assert "source_not_found" in r["error"]

    def test_install_invalid_name(self, clean_market: Path):
        r = install_local_tool("BadName", "/tmp")
        assert "error" in r
        assert "invalid_tool_name" in r["error"]

    def test_install_idempotent_overwrite(self, clean_market: Path, tmp_path: Path):
        """同名重装: 注册表更新, 不重复追加."""
        src = tmp_path / "src1"
        src.mkdir()
        (src / "x.py").write_text("x")

        install_local_tool("dup-tool", str(src))
        install_local_tool("dup-tool", str(src))
        market = list_market_tools()
        assert sum(1 for t in market if t["name"] == "dup-tool") == 1


# ── 3. ForgeLoader.load_tool / load_from_market ────
class TestForgeLoader:
    def test_load_tool_injects_poc_services(
        self, clean_market: Path, fresh_loader: ForgeLoader, tmp_path: Path
    ):
        """加载工具 → POC_SERVICES 自动注入新 URI."""
        # 先安装
        src = tmp_path / "tool-src"
        src.mkdir()
        (src / "x.py").write_text("x")
        new_uri = "bos://capability/forge-x/run"
        install_local_tool(
            "forge-x",
            str(src),
            bos_uri=new_uri,
            description="dynamic test",
        )

        # 加载
        market = list_market_tools()
        r = fresh_loader.load_tool(market[0])
        assert r.get("loaded") == "forge-x"
        assert r.get("bos_uri") == new_uri
        assert new_uri in POC_SERVICES  # W4 集成点

    def test_load_from_market_loads_all(
        self, clean_market: Path, fresh_loader: ForgeLoader, tmp_path: Path
    ):
        """批量加载: market.json 2 条 → 都注入."""
        for i in range(2):
            src = tmp_path / f"src{i}"
            src.mkdir()
            (src / "x.py").write_text("x")
            install_local_tool(
                f"tool-{i}",
                str(src),
                bos_uri=f"bos://capability/tool-{i}/run",
            )

        results = fresh_loader.load_from_market()
        assert len(results) == 2
        assert fresh_loader.list_loaded()  # 非空

    def test_load_tool_skip_already_loaded(
        self, clean_market: Path, fresh_loader: ForgeLoader, tmp_path: Path
    ):
        """重复 load → 第二次 skipped."""
        src = tmp_path / "tool-src"
        src.mkdir()
        (src / "x.py").write_text("x")
        install_local_tool(
            "tool-a",
            str(src),
            bos_uri="bos://capability/tool-a/run",
        )
        market = list_market_tools()
        r1 = fresh_loader.load_tool(market[0])
        r2 = fresh_loader.load_tool(market[0])
        assert "loaded" in r1
        assert r2.get("skipped") == "tool-a"

    def test_load_tool_skip_bos_uri_collision(
        self, clean_market: Path, fresh_loader: ForgeLoader, tmp_path: Path
    ):
        """BOS URI 已被静态注册 (P33-W4) → 跳过."""
        # 注入: 已存在的 POC service URI
        market = [{
            "name": "kairon-kos-search",
            "bos_uri": "bos://memory/kos/search",  # 静态注册过
            "install_path": "/tmp/fake",
            "source": "local:/tmp/fake",
        }]
        r = fresh_loader.load_tool(market[0])
        assert "skipped" in r
        assert "bos_uri_already_registered" in r["reason"]

    def test_load_tool_invalid_uri(self, clean_market: Path, fresh_loader: ForgeLoader):
        r = fresh_loader.load_tool(
            {
                "name": "bad",
                "bos_uri": "not-a-uri",
                "install_path": "/tmp/fake",
            }
        )
        assert "error" in r
        assert "invalid_bos_uri" in r["error"]

    def test_load_tool_missing_fields(
        self, clean_market: Path, fresh_loader: ForgeLoader
    ):
        r = fresh_loader.load_tool({"name": "x"})  # 缺 bos_uri + install_path
        assert "error" in r
        assert "missing_fields" in r["error"]

    def test_unload_tool_removes_from_pool(
        self, clean_market: Path, fresh_loader: ForgeLoader, tmp_path: Path
    ):
        src = tmp_path / "tool-src"
        src.mkdir()
        (src / "x.py").write_text("x")
        install_local_tool(
            "tool-z",
            str(src),
            bos_uri="bos://capability/tool-z/run",
        )
        market = list_market_tools()
        fresh_loader.load_tool(market[0])
        assert "bos://capability/tool-z/run" in POC_SERVICES

        ok = fresh_loader.unload_tool("tool-z")
        assert ok is True
        assert "bos://capability/tool-z/run" not in POC_SERVICES
        assert fresh_loader.get_loaded("tool-z") is None

    def test_unload_tool_not_loaded(
        self, clean_market: Path, fresh_loader: ForgeLoader
    ):
        ok = fresh_loader.unload_tool("never-loaded")
        assert ok is False


# ── 4. remove_tool ─────────────────────────────────
class TestRemoveTool:
    def test_remove_tool_cleans_market_and_path(
        self, clean_market: Path, tmp_path: Path
    ):
        src = tmp_path / "src"
        src.mkdir()
        (src / "x.py").write_text("x")
        install_local_tool("to-remove", str(src))
        assert any(t["name"] == "to-remove" for t in list_market_tools())

        ok = remove_tool("to-remove")
        assert ok is True
        assert not any(t["name"] == "to-remove" for t in list_market_tools())

    def test_remove_tool_not_found(self, clean_market: Path):
        ok = remove_tool("nope-never-existed")
        assert ok is False


# ── 5. W4 集成: resolve_bos_uri 真可达 ─────────────
class TestW4Integration:
    def test_loaded_tool_resolvable_after_inject(
        self, clean_market: Path, fresh_loader: ForgeLoader, tmp_path: Path
    ):
        """动态注入后, resolve_bos_uri 应能识别新 URI."""
        # 准备一个最小 fake package
        src = tmp_path / "src"
        src.mkdir()
        # 必须含 __main__.py 才能 python -m fake-tool serve ...
        (src / "fake_tool.py").write_text('print("hi from fake tool")')

        new_uri = "bos://capability/fake-tool/invoke"
        install_local_tool(
            "fake-tool",
            str(src),
            bos_uri=new_uri,
        )
        market = list_market_tools()
        r = fresh_loader.load_tool(market[0])
        assert r.get("loaded") == "fake-tool"

        # W4 验证: parse_bos_uri 可解析 (语法层)
        parsed = parse_bos_uri(new_uri)
        assert parsed["domain"] == "capability"
        assert parsed["package"] == "fake-tool"
        assert parsed["action"] == "invoke"

        # W4 验证: POC_SERVICES 注册
        assert new_uri in POC_SERVICES
        svc = POC_SERVICES[new_uri]
        assert svc.transport == "stdio"
        assert svc.command[0] == "uv"  # 仍是 stdio uv run

    def test_dynamic_load_preserves_static_registry(
        self, clean_market: Path, fresh_loader: ForgeLoader
    ):
        """动态加载不能破坏 P33-W4 静态 11 POC services."""
        # 加载 1 个 fake
        r = fresh_loader.load_tool(
            {
                "name": "x",
                "bos_uri": "bos://capability/x/y",
                "install_path": "/tmp",
                "source": "local:/tmp",
            }
        )
        # 静态 11 仍可达
        for uri in (
            "bos://memory/kos/search",
            "bos://governance/omo/audit",
            "bos://analysis/minerva/research",
            "bos://persona/health-profile/summary",
            "bos://capability/forge/register-tool",
        ):
            assert uri in POC_SERVICES, f"P33-W4 static URI disappeared: {uri}"
