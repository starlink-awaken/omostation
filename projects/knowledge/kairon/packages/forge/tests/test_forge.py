"""
Forge 核心模块单元测试

测试覆盖:
- forge.py CLI 入口模块的结构和函数签名
- graph_utils.py 图谱工具函数
- build_graph.py 图谱构建逻辑（dry-run 模式）
- graph_viz.py 可视化模块
- mcp_server.py 核心查询函数
- http_api.py 的搜索和查询函数
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import json
import sys
import tempfile
from pathlib import Path

import pytest

# ─── 确保 src 和 server 可导入 ─────────────────────
SRC = Path(__file__).resolve().parent.parent / "src"
SERVER = Path(__file__).resolve().parent.parent / "server"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SERVER))


# ═══════════════════════════════════════════════════
# 1. 模块导入测试
# ═══════════════════════════════════════════════════


class TestImports:
    """验证所有核心模块可正常导入。"""

    def test_import_forge(self):
        import forge

        assert hasattr(forge, "main")
        assert hasattr(forge, "COMMANDS")
        assert hasattr(forge, "VERIFY_COMMANDS")
        assert hasattr(forge, "ALIASES")

    def test_import_graph_utils(self):
        import graph_utils

        assert hasattr(graph_utils, "kebab")
        assert hasattr(graph_utils, "compute_capability_overlap")
        assert hasattr(graph_utils, "load_registry")

    def test_import_build_graph(self):
        import build_graph

        assert hasattr(build_graph, "build")

    def test_import_graph_viz(self):
        import graph_viz

        assert hasattr(graph_viz, "generate_html")
        assert hasattr(graph_viz, "generate_mermaid")

    def test_import_mcp_server(self):
        import mcp_server

        assert hasattr(mcp_server, "search_tools")
        assert hasattr(mcp_server, "get_tool_info")
        assert hasattr(mcp_server, "list_tools")
        assert hasattr(mcp_server, "get_project_status")
        assert hasattr(mcp_server, "capture_tool")

    def test_import_http_api(self):
        import http_api

        assert hasattr(http_api, "query_assets")
        assert hasattr(http_api, "query_graph")
        assert hasattr(http_api, "ForgeAPIHandler")
        assert hasattr(http_api, "build_asset_stats")
        assert hasattr(http_api, "get_categories")
        assert hasattr(http_api, "export_assets")


# ═══════════════════════════════════════════════════
# 2. forge.py 核心结构测试
# ═══════════════════════════════════════════════════


class TestForgeCLIStructure:
    """测试 forge.py 的常量定义和函数签名。"""

    def test_commands_dict_structure(self):
        import forge

        # COMMANDS 应包含关键的脚本映射
        for cmd in [
            "build-graph",
            "graph-viz",
            "sniff-local",
            "insight",
            "classify",
            "kos-bridge",
            "sync-agora",
            "sediment-capture",
        ]:
            assert cmd in forge.COMMANDS, f"COMMANDS missing: {cmd}"

    def test_commands_values(self):
        import forge

        for name, (cmd_type, path, _) in forge.COMMANDS.items():
            assert cmd_type in ("script", "python"), f"Bad type for {name}"
            assert isinstance(path, str), f"Bad path for {name}"
            assert path.endswith(".sh") or path.endswith(".py"), f"Bad extension for {name}"

    def test_verify_commands_structure(self):
        import forge

        for phase in ("phase1", "phase2", "phase3"):
            assert phase in forge.VERIFY_COMMANDS

    def test_aliases_structure(self):
        import forge

        expected = {
            "build": "build-graph",
            "capture": "sediment-capture",
            "kos": "kos-bridge",
            "agora": "sync-agora",
        }
        for alias, target in expected.items():
            assert forge.ALIASES[alias] == target, f"ALIASES[{alias!r}] != {target!r}"

    def test_main_function_exists(self):
        import forge

        assert callable(forge.main)

    def test_cmd_status_exists(self):
        import forge

        assert callable(forge.cmd_status)

    def test_cmd_health_exists(self):
        import forge

        assert callable(forge.cmd_health)

    def test_cmd_verify_exists(self):
        import forge

        assert callable(forge.cmd_verify)

    def test_cmd_sniff_exists(self):
        import forge

        assert callable(forge.cmd_sniff)

    def test_cmd_install_exists(self):
        import forge

        assert callable(forge.cmd_install)

    def test_cmd_capture_exists(self):
        import forge

        assert callable(forge.cmd_capture)

    def test_cmd_help_exists(self):
        import forge

        assert callable(forge.cmd_help)

    def test_cmd_schedule_exists(self):
        import forge

        assert callable(forge.cmd_schedule)

    def test_cmd_routine_exists(self):
        import forge

        assert callable(forge.cmd_routine)

    def test_paths_defined(self):
        import forge

        assert hasattr(forge, "TOOLBOX")
        assert hasattr(forge, "SCRIPTS")
        assert hasattr(forge, "SRC")
        assert forge.TOOLBOX.exists()
        assert forge.SCRIPTS.exists()
        assert forge.SRC.exists()


# ═══════════════════════════════════════════════════
# 3. graph_utils.py 函数测试
# ═══════════════════════════════════════════════════


class TestGraphUtils:
    """测试 graph_utils.py 的各个函数。"""

    def test_kebab_basic(self):
        from graph_utils import kebab

        assert kebab("Hello World") == "hello-world"
        assert kebab("PDF Viewer") == "pdf-viewer"
        assert kebab("  spaces  ") == "spaces"

    def test_kebab_special_chars(self):
        from graph_utils import kebab

        assert kebab("Tool: MCP Server!") == "tool-mcp-server"
        assert kebab("__UPPER__CASE__") == "upper-case"

    def test_kebab_empty(self):
        from graph_utils import kebab

        assert kebab("") == ""
        assert kebab("!!!") == ""

    def test_compute_capability_overlap_empty(self):
        from graph_utils import compute_capability_overlap

        assert compute_capability_overlap([]) == []
        assert compute_capability_overlap([{"id": "a", "capabilities": ["x"]}]) == []

    def test_compute_capability_overlap_no_match(self):
        from graph_utils import compute_capability_overlap

        tools = [
            {"id": "tool-a", "capabilities": ["code", "chat"]},
            {"id": "tool-b", "capabilities": ["vision", "image"]},
        ]
        result = compute_capability_overlap(tools, pre_filter=False)
        assert result == []

    def test_compute_capability_overlap_match(self):
        from graph_utils import compute_capability_overlap

        tools = [
            {"id": "tool-a", "capabilities": ["code", "chat", "analysis"]},
            {"id": "tool-b", "capabilities": ["code", "chat", "writing"]},
        ]
        result = compute_capability_overlap(tools, min_similarity=0.5, pre_filter=False)
        assert len(result) >= 1
        id1, id2, sim = result[0]
        assert {id1, id2} == {"tool-a", "tool-b"}
        assert sim >= 0.5

    def test_compute_capability_overlap_pre_filter(self):
        from graph_utils import compute_capability_overlap

        tools = [
            {"id": "pdf-tool", "capabilities": ["pdf", "document"]},
            {"id": "doc-tool", "capabilities": ["document", "word"]},
            {"id": "image-tool", "capabilities": ["image", "vision"]},
        ]
        result = compute_capability_overlap(tools, min_similarity=0.1, pre_filter=True)
        # pdf-tool and doc-tool share "doc" token in id
        ids = {(r[0], r[1]) for r in result}
        assert ("pdf-tool", "doc-tool") in ids or ("doc-tool", "pdf-tool") in ids

    def test_get_edge_degree(self):
        from graph_utils import get_edge_degree

        g = {
            "edges": [
                {"source": "a", "target": "b"},
                {"source": "a", "target": "c"},
                {"source": "b", "target": "d"},
            ]
        }
        degree = get_edge_degree(g)
        assert degree["a"] == 2
        assert degree["b"] == 2
        assert degree["c"] == 1
        assert degree["d"] == 1

    def test_get_related_by_type(self):
        from graph_utils import get_related_by_type

        g = {
            "nodes": [
                {"id": "tool-a", "type": "Tool", "label": "Tool A"},
                {"id": "cat-x", "type": "Category", "label": "Category X"},
                {"id": "tool-b", "type": "Tool", "label": "Tool B"},
            ],
            "edges": [
                {"source": "tool-a", "target": "cat-x", "relation": "IN_CATEGORY"},
                {"source": "tool-b", "target": "cat-x", "relation": "IN_CATEGORY"},
            ],
        }
        result = get_related_by_type(g, {"tool-a"})
        assert "Category" in result
        assert len(result["Category"]) == 1
        assert result["Category"][0]["id"] == "cat-x"

    def test_get_related_by_type_with_filter(self):
        from graph_utils import get_related_by_type

        g = {
            "nodes": [
                {"id": "tool-a", "type": "Tool", "label": "Tool A"},
                {"id": "cap-z", "type": "Capability", "label": "Cap Z"},
            ],
            "edges": [
                {"source": "tool-a", "target": "cap-z", "relation": "HAS_CAPABILITY"},
            ],
        }
        result = get_related_by_type(g, {"tool-a"}, group_types=["Capability"])
        assert "Capability" in result
        assert "Tool" not in result

    def test_load_registry_with_temp(self):
        from graph_utils import load_registry

        data = {"schema_version": "1.0", "tools": []}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            p = f.name
        try:
            loaded = load_registry(p)
            assert loaded["schema_version"] == "1.0"
            assert loaded["tools"] == []
        finally:
            Path(p).unlink(missing_ok=True)

    def test_load_graph_with_temp(self):
        from graph_utils import load_graph

        data = {"nodes": [], "edges": [], "stats": {}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            p = f.name
        try:
            loaded = load_graph(p)
            assert loaded["nodes"] == []
            assert loaded["edges"] == []
        finally:
            Path(p).unlink(missing_ok=True)


# ═══════════════════════════════════════════════════
# 4. build_graph.py 函数测试
# ═══════════════════════════════════════════════════


class TestBuildGraph:
    """测试图谱构建逻辑（dry-run 模式，不写文件）。"""

    SAMPLE_REGISTRY = {
        "schema_version": "1.2",
        "tools": [
            {
                "id": "claude-code",
                "name": "Claude Code",
                "type": "tool",
                "status": "active",
                "category": ["MCP", "AI"],
                "capabilities": ["code", "chat", "analysis"],
                "source": {"provider": "Anthropic"},
            },
            {
                "id": "ollama-local",
                "name": "Ollama",
                "type": "tool",
                "status": "active",
                "category": ["Local"],
                "capabilities": ["chat", "code"],
                "source": {"provider": "开源工具"},
            },
            {
                "id": "my-skill",
                "name": "My Custom Skill",
                "type": "skill",
                "status": "active",
                "category": ["Custom"],
                "capabilities": ["analysis"],
                "source": {},
            },
            {
                "id": "candidate-tool",
                "name": "Not Ready",
                "type": "tool",
                "status": "candidate",
                "category": [],
                "capabilities": [],
                "source": {},
            },
        ],
        "event_log": [],
        "gap_analysis": {
            "gaps": [
                {"capability": "vision"},
            ],
        },
    }

    def test_build_basic(self):
        from build_graph import build

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(self.SAMPLE_REGISTRY, f)
            reg_path = f.name
        graph_path = tempfile.mktemp(suffix=".json")  # noqa: S306

        try:
            result = build(reg_path, graph_path, dry_run=True)
            assert "nodes" in result
            assert "edges" in result
            assert "stats" in result
            # candidate tools are filtered out
            assert result["stats"]["tool_nodes"] >= 2  # claude-code + ? (non-candidate tool)
            # Skills count — build_graph adds all non-candidate tools as "Tool" type first,
            # then a duplicate "Skill" node for skill-type tools is skipped (already seen)
            assert result["stats"]["skill_nodes"] == 0
        finally:
            Path(reg_path).unlink(missing_ok=True)
            Path(graph_path).unlink(missing_ok=True)

    def test_build_nodes_and_edges(self):
        from build_graph import build

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(self.SAMPLE_REGISTRY, f)
            reg_path = f.name
        graph_path = tempfile.mktemp(suffix=".json")  # noqa: S306

        try:
            result = build(reg_path, graph_path, dry_run=True)
            # Should have tool nodes, category nodes, capability nodes
            types = {n["type"] for n in result["nodes"]}
            assert "Tool" in types
            assert "Category" in types
            assert "Capability" in types
            # Should have gap nodes
            assert "Gap" in types
            # Should have edges
            assert len(result["edges"]) > 0
        finally:
            Path(reg_path).unlink(missing_ok=True)
            Path(graph_path).unlink(missing_ok=True)

    def test_build_with_empty_tools(self):
        from build_graph import build

        empty_reg = {"schema_version": "1.0", "tools": [], "event_log": [], "gap_analysis": {}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(empty_reg, f)
            reg_path = f.name
        graph_path = tempfile.mktemp(suffix=".json")  # noqa: S306

        try:
            result = build(reg_path, graph_path, dry_run=True)
            assert result["stats"]["total_nodes"] == 0
            assert result["stats"]["total_edges"] == 0
        finally:
            Path(reg_path).unlink(missing_ok=True)
            Path(graph_path).unlink(missing_ok=True)


# ═══════════════════════════════════════════════════
# 5. graph_viz.py 函数测试
# ═══════════════════════════════════════════════════


class TestGraphViz:
    """测试可视化模块的函数。"""

    SAMPLE_GRAPH = {
        "generated": "2026-01-01T00:00:00Z",
        "nodes": [
            {"id": "tool-a", "type": "Tool", "label": "Tool A"},
            {"id": "tool-b", "type": "Tool", "label": "Tool B"},
            {"id": "cap-x", "type": "Capability", "label": "Capability X"},
        ],
        "edges": [
            {"source": "tool-a", "target": "cap-x", "relation": "HAS_CAPABILITY"},
            {"source": "tool-b", "target": "cap-x", "relation": "HAS_CAPABILITY"},
        ],
        "stats": {"total_nodes": 3, "total_edges": 2},
    }

    def test_generate_html_output(self):
        from graph_viz import generate_html

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(self.SAMPLE_GRAPH, f)
            graph_path = f.name
        output_path = tempfile.mktemp(suffix=".html")  # noqa: S306
        try:
            generate_html(graph_path, output_path)
            html = Path(output_path).read_text()
            assert "<!DOCTYPE html>" in html
            assert "Forge" in html
            assert "vis-network" in html
            assert "tool-a" in html
            assert "tool-b" in html
        finally:
            Path(graph_path).unlink(missing_ok=True)
            Path(output_path).unlink(missing_ok=True)

    def test_generate_mermaid_output(self):
        from graph_viz import generate_mermaid

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(self.SAMPLE_GRAPH, f)
            graph_path = f.name
        output_path = tempfile.mktemp(suffix=".md")  # noqa: S306
        try:
            generate_mermaid(graph_path, output_path, max_nodes=10)
            mermaid = Path(output_path).read_text()
            assert "graph LR" in mermaid
            assert "tool_a" in mermaid or "tool-a" in mermaid
            # Relation label truncated to 10 chars by graph_viz
            assert "HAS_CAPABI" in mermaid or "HAS_" in mermaid
        finally:
            Path(graph_path).unlink(missing_ok=True)
            Path(output_path).unlink(missing_ok=True)

    def test_mermaid_id(self):
        from graph_viz import mermaid_id

        assert mermaid_id("tool-a") == "tool_a"
        assert mermaid_id("cap:test") == "cap_test"
        assert mermaid_id("simple") == "simple"

    def test_color_map_defined(self):
        from graph_viz import COLOR_MAP, SIZE_MAP

        for node_type in ("Tool", "Capability", "Knowledge", "Skill", "Gap", "Provider", "Category"):
            assert node_type in COLOR_MAP, f"Missing color for {node_type}"
            assert node_type in SIZE_MAP, f"Missing size for {node_type}"


# ═══════════════════════════════════════════════════
# ═══════════════════════════════════════════════════
# 6. http_api.py 搜索/查询函数测试
# ═══════════════════════════════════════════════════


class TestHttpApiCore:
    """测试 http_api.py 的资产查询函数。"""

    def test_query_assets(self):
        import http_api

        results, total = http_api.query_assets(query="PDF", limit=5)
        assert isinstance(results, list)
        assert len(results) <= 5
        assert isinstance(total, int)
        assert total > 0

    def test_query_assets_no_query(self):
        import http_api

        results, total = http_api.query_assets(limit=3)
        assert isinstance(results, list)
        # Without query, should return top tools
        assert len(results) == 3
        assert total >= 3

    def test_query_assets_with_capability_filter(self):
        import http_api

        results, total = http_api.query_assets(capabilities=["vision"], limit=5)
        assert isinstance(results, list)
        for tool in results:
            caps = [c.lower() for c in tool.get("capabilities", [])]
            assert any("vision" in c for c in caps)

    def test_query_assets_with_facets(self):
        import http_api

        results, total = http_api.query_assets(category="CLI", status="active", limit=3)
        assert isinstance(results, list)
        assert total > 0
        for tool in results:
            assert tool.get("status") == "active"
            assert "CLI" in tool.get("category", [])

    def test_build_asset_stats(self):
        import http_api

        stats = http_api.build_asset_stats()
        assert isinstance(stats, dict)
        assert "total" in stats
        assert "by_category" in stats
        assert "by_status" in stats
        assert "by_type" in stats
        assert stats["total"] > 0

    def test_get_categories(self):
        import http_api

        cats = http_api.get_categories()
        assert isinstance(cats, list)
        assert len(cats) > 0
        assert "name" in cats[0]
        assert "count" in cats[0]

    def test_export_assets_csv(self):
        import http_api

        csv = http_api.export_assets(format="csv", category="CLI")
        assert isinstance(csv, str)
        assert csv.startswith("id,name,")

    def test_query_graph(self):
        import http_api

        result = http_api.query_graph("PDF")
        assert isinstance(result, list)

    def test_forge_api_handler_class(self):
        import http_api

        assert hasattr(http_api.ForgeAPIHandler, "do_GET")
        assert hasattr(http_api.ForgeAPIHandler, "do_POST")
        assert hasattr(http_api.ForgeAPIHandler, "do_OPTIONS")


# ═══════════════════════════════════════════════════
# 8. 集成测试：样例注册表读写
# ═══════════════════════════════════════════════════


class TestRegistryIntegration:
    """集成测试：模拟完整的注册表读取流程。"""

    def test_load_real_registry(self):
        import forge

        reg_path = forge.TOOLBOX / "tools-registry.json"
        assert reg_path.exists(), "tools-registry.json must exist"
        data = json.loads(reg_path.read_text())
        assert "schema_version" in data
        assert "tools" in data
        assert isinstance(data["tools"], list)
        assert len(data["tools"]) > 0, "At least one tool registered"

    def test_tool_structure(self):
        import forge

        reg_path = forge.TOOLBOX / "tools-registry.json"
        data = json.loads(reg_path.read_text())
        for tool in data["tools"]:
            assert "id" in tool, f"Tool missing 'id': {tool.get('name', '')}"
            assert "name" in tool, f"Tool {tool['id']} missing 'name'"
            assert "status" in tool, f"Tool {tool['id']} missing 'status'"
            assert "capabilities" in tool, f"Tool {tool['id']} missing 'capabilities'"
            assert isinstance(tool["capabilities"], list)

    def test_event_log_structure(self):
        import forge

        reg_path = forge.TOOLBOX / "tools-registry.json"
        data = json.loads(reg_path.read_text())
        for event in data.get("event_log", []):
            assert "type" in event or "event" in event, f"event_log entry missing 'type': {event}"
            assert "timestamp" in event
            assert "summary" in event


# ═══════════════════════════════════════════════════
# 9. 新 Python 模块测试
# ═══════════════════════════════════════════════════


class TestQueryGraph:
    def test_query_by_keyword(self):

        # Direct function test
        import json
        from pathlib import Path

        graph_path = Path(__file__).resolve().parent.parent / "graph" / "graph.json"
        if not graph_path.exists():
            pytest.skip("graph.json not found — run forge build-graph first")
        g = json.loads(graph_path.read_text())
        nodes = [n for n in g["nodes"] if "pdf" in n["label"].lower()]
        assert len(nodes) > 0, "Should find PDF-related nodes"

    def test_topo_analysis(self):
        import json
        from pathlib import Path

        graph_path = Path(__file__).resolve().parent.parent / "graph" / "graph.json"
        if not graph_path.exists():
            pytest.skip("graph.json not found — run forge build-graph first")
        g = json.loads(graph_path.read_text())
        assert "nodes" in g
        assert "edges" in g


class TestSyncRegistry:
    def test_generate_markdown(self):
        import sync_registry

        md = sync_registry.generate_markdown()
        assert isinstance(md, str)
        assert "工具资产注册表" in md
        assert len(md) > 100

    def test_load_registry(self):
        from sync_registry import _load

        reg = _load()
        assert "tools" in reg


class TestVerify:
    def test_phase1_checks(self):
        from pathlib import Path

        reg_path = Path(__file__).resolve().parent.parent / "tools-registry.json"
        if not reg_path.exists():
            pytest.skip("tools-registry.json not found — run forge asset export tools first")
        reg = json.loads(reg_path.read_text())
        count = len(reg.get("tools", []))
        assert count >= 60, f"Tool count {count} < 60"

    def test_module_imports(self):
        import verify

        assert hasattr(verify, "phase1")
        assert hasattr(verify, "phase2")
        assert hasattr(verify, "phase3")
        assert callable(verify.run)


class TestSediment:
    def test_module_imports(self):
        import sediment

        assert callable(sediment.run)

    def test_capture_help(self):

        import sediment

        try:
            sediment.run(["--help"])
        except SystemExit:
            pass


class TestConfig:
    def test_forge_config_paths(self):
        import forge_config

        assert forge_config.FORGE_ROOT.exists()
        assert forge_config.REGISTRY.exists()
        assert forge_config.SRC.exists()
        assert forge_config.HTTP_PORT == 8766


class TestVerifyModule:
    def test_verify_import(self):
        import verify

        assert callable(verify.run)
        assert hasattr(verify, "phase1")
