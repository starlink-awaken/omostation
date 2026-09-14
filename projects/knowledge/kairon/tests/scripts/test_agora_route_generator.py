"""agora_route_generator 单元测试。

覆盖:
  - AST 解析 (@mcp.tool / @fastmcp.tool)
  - 黑名单过滤
  - 扫描包
  - 保留现有条目
  - 去重
  - 备份
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# ── 让脚本可被 import ───────────────────────────────────
SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "agora_route_generator.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))

import agora_route_generator as arg  # type: ignore[reportMissingImports]

# ── 1. AST 提取 ─────────────────────────────────────────


def test_extract_tools_from_mock_file(tmp_path: Path) -> None:
    """mock 一个含 @mcp.tool() / @fastmcp.tool() 的 Python 文件，验证提取。"""
    mock_file = tmp_path / "server.py"
    mock_file.write_text(
        '''
from fastmcp import FastMCP

mcp = FastMCP("test")
fastmcp = FastMCP("other")

@mcp.tool()
def alpha(x: int) -> int:
    """Alpha tool."""
    return x

@mcp.tool(name="beta_named")
def beta(y: str) -> str:
    return y

@fastmcp.tool()
async def gamma() -> dict:
    """Async tool."""
    return {}

def not_a_tool():
    """Should NOT be picked up."""
    return 1
''',
        encoding="utf-8",
    )

    tools = list(arg.extract_tools_from_file(mock_file))
    names = [t[0] for t in tools]
    assert "alpha" in names
    assert "beta" in names  # 函数名仍是 beta（@mcp.tool(name="beta_named") 改的是外部注册名）
    assert "gamma" in names
    assert "not_a_tool" not in names
    # 三个工具，docstring 至少 alpha 有
    assert len(tools) == 3
    # 行号是正整数
    for name, line_no, docstring in tools:
        assert line_no > 0
        assert isinstance(docstring, str)


def test_extract_tools_ignores_docstring_decorators(tmp_path: Path) -> None:
    """shared-lib operation_level.py docstring 中有 @mcp.tool() — AST 不会误识别。"""
    mock_file = tmp_path / "with_docstring_decorator.py"
    mock_file.write_text(
        '''
def real_tool():
    """This tool uses:

    Usage:
        @mcp.tool()
        @operation_level(...)
        def some_other():
            ...
    """
    return 1
''',
        encoding="utf-8",
    )

    tools = list(arg.extract_tools_from_file(mock_file))
    assert tools == []  # 没有任何 @mcp.tool() 装饰的真实函数


def test_extract_tools_syntax_error_returns_empty(tmp_path: Path) -> None:
    """语法错误的文件不应让生成器崩溃。"""
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def broken(:\n", encoding="utf-8")
    tools = list(arg.extract_tools_from_file(bad_file))
    assert tools == []


# ── 2. 黑名单 ──────────────────────────────────────────


def test_is_blacklisted_private() -> None:
    """以下划线开头的工具名应被黑名单。"""
    assert arg.is_blacklisted("_health_check") is True
    assert arg.is_blacklisted("_internal_helper") is True
    assert arg.is_blacklisted("health_check") is False


def test_is_blacklisted_test_prefix() -> None:
    """test_ 开头的工具名应被黑名单。"""
    assert arg.is_blacklisted("test_something") is True
    assert arg.is_blacklisted("test_") is True
    assert arg.is_blacklisted("production_tool") is False


def test_is_blacklisted_sample_and_internal() -> None:
    """模板示例和 _internal 后缀应被黑名单。"""
    assert arg.is_blacklisted("sample_list_connectors") is True
    assert arg.is_blacklisted("foo_internal") is True
    assert arg.is_blacklisted("alpha") is False


# ── 3. 扫描包 ──────────────────────────────────────────


def test_scan_package_finds_decorated_functions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """扫描一个 mock 包，验证能找出装饰过的函数。"""
    fake_pkg_root = tmp_path / "packages" / "fakepkg" / "src" / "fakepkg"
    fake_pkg_root.mkdir(parents=True)
    (fake_pkg_root / "server.py").write_text(
        """
from fastmcp import FastMCP
mcp = FastMCP("fake")

@mcp.tool()
def public_tool() -> dict:
    return {}

@mcp.tool()
def _private_tool() -> dict:
    return {}
""",
        encoding="utf-8",
    )
    (fake_pkg_root / "_hidden.py").write_text(
        """
@mcp.tool()
def sample_ignored() -> dict:
    return {}
""",
        encoding="utf-8",
    )
    (fake_pkg_root / "tools_template.py").write_text(
        '''
@mcp.tool()
def sample_send_message() -> dict:
    """Template — should be skipped by path filter."""
    return {}
''',
        encoding="utf-8",
    )

    # 临时把 PACKAGES_DIR 指向 tmp
    monkeypatch.setattr(arg, "PACKAGES_DIR", tmp_path / "packages")

    routes = arg.scan_package("fakepkg")
    names = {r.tool_name for r in routes}

    assert "public_tool" in names
    assert "_private_tool" not in names  # 黑名单过滤
    assert "sample_ignored" not in names  # 黑名单过滤
    # tools_template.py 路径含 "tools_template" 应被跳过
    assert "sample_send_message" not in names
    # 路径格式 packages/fakepkg/src/fakepkg/server.py
    assert all(r.file_path.startswith("packages/fakepkg/") for r in routes)


# ── 4. 保留现有 ─────────────────────────────────────────


def test_generate_routes_preserves_existing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """现有 routes（含手工注册条目）应被完整保留。"""
    fake_agora = tmp_path / "agora"
    fake_agora.mkdir()
    existing = {"routes": {"test.tool": "test-svc", "eidos": "eidos"}}
    (fake_agora / "agora-routes.json").write_text(json.dumps(existing), encoding="utf-8")

    monkeypatch.setattr(arg, "AGORA_ROUTES", fake_agora / "agora-routes.json")
    monkeypatch.setattr(arg, "PACKAGES_DIR", tmp_path / "packages")
    (tmp_path / "packages").mkdir()

    new_routes = arg.generate_routes(only=[])
    assert new_routes["test.tool"] == "test-svc"
    assert new_routes["eidos"] == "eidos"


# ── 5. 去重 ────────────────────────────────────────────


def test_generate_routes_deduplicates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """同一 tool_name 在不同包出现，第二次应被忽略（保留旧 service）。"""
    fake_agora = tmp_path / "agora"
    fake_agora.mkdir()
    (fake_agora / "agora-routes.json").write_text(
        json.dumps({"routes": {"shared_tool": "first-svc"}}),
        encoding="utf-8",
    )

    # 创建一个含 shared_tool 的包
    pkg = tmp_path / "packages" / "p1" / "src" / "p1"
    pkg.mkdir(parents=True)
    (pkg / "s.py").write_text(
        """
from fastmcp import FastMCP
mcp = FastMCP("p1")
@mcp.tool()
def shared_tool() -> dict:
    return {}
@mcp.tool()
def new_tool() -> dict:
    return {}
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(arg, "AGORA_ROUTES", fake_agora / "agora-routes.json")
    monkeypatch.setattr(arg, "PACKAGES_DIR", tmp_path / "packages")

    new_routes = arg.generate_routes(only=["p1"])
    assert new_routes["shared_tool"] == "first-svc"  # 旧值优先
    assert new_routes["new_tool"] == "p1-mcp"
    # 总数 = 2
    assert len(new_routes) == 2


# ── 6. 备份 ─────────────────────────────────────────────


def test_backup_creates_timestamped_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """备份文件应带 UTC 时间戳后缀，文件名格式 .json.bak-YYYYMMDDTHHMMSSZ。"""
    fake_agora = tmp_path / "agora"
    fake_agora.mkdir()
    target = fake_agora / "agora-routes.json"
    target.write_text('{"routes": {"x": "y"}}', encoding="utf-8")

    monkeypatch.setattr(arg, "AGORA_ROUTES", target)

    bak = arg.backup_existing_routes()
    assert bak is not None
    assert bak.exists()
    assert bak.name.startswith("agora-routes.json.bak-")
    assert bak.name.endswith("Z")
    # 备份内容与原文件一致
    assert json.loads(bak.read_text(encoding="utf-8")) == {"routes": {"x": "y"}}
