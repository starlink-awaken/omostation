"""ecos FastMCP Server — L0 协议层统一入口

合并 SSOT Kernel (7 tools) + Integration (12 tools) ≈ 19 tools.
基于 fastmcp，兼容 agora proxy stdio 连接。
"""

from __future__ import annotations

import json
import os
import subprocess as _subprocess
import sys
from collections import Counter
from pathlib import Path

from ecos.l0.ssot.mcp_server import (
    do_check,
    do_compile,
    do_derive,
    do_evolve,
    do_extract,
    do_stats,
    do_sync,
)

try:
    from fastmcp import FastMCP
except ImportError:
    raise SystemExit("fastmcp not installed. Install with: uv sync")

mcp = FastMCP("ecos", version="1.0.0")

# ── SSOT 工具 (来自 ssot/mcp_server.py) ──


@mcp.tool()
def ssot_check(domain_dir: str = "domains/guozhuan") -> str:
    """运行 SSOT 规则检查，返回每条规则的执行结果"""
    result = do_check({"domain_dir": domain_dir})
    return result.get("text", json.dumps(result, ensure_ascii=False))


@mcp.tool()
def ssot_derive(domain_dir: str = "domains/guozhuan", rounds: int = 1) -> str:
    """执行全量规则引擎推导，生成 Markdown 报告"""
    result = do_derive({"domain_dir": domain_dir, "rounds": rounds})
    return result.get("text", json.dumps(result, ensure_ascii=False))


@mcp.tool()
def ssot_compile(domain_dir: str = "domains/guozhuan") -> str:
    """编译 YAML 为 JSON，含 Schema 校验 + 跨文件引用检查"""
    result = do_compile({"domain_dir": domain_dir})
    return result.get("text", json.dumps(result, ensure_ascii=False))


@mcp.tool()
def ssot_evolve(domain_dir: str = "domains/guozhuan") -> str:
    """进化分析：从数据中挖掘新规则建议（只读，不修改文件）"""
    result = do_evolve({"domain_dir": domain_dir})
    return result.get("text", json.dumps(result, ensure_ascii=False))


@mcp.tool()
def ssot_stats(domain_dir: str = "domains/guozhuan") -> str:
    """输出知识库统计信息（实体/事实/推论分布、引用热度）"""
    result = do_stats({"domain_dir": domain_dir})
    return result.get("text", json.dumps(result, ensure_ascii=False))


@mcp.tool()
def ssot_sync(yaml_dir: str, md_dir: str) -> str:
    """同步 YAML 引擎数据到 Markdown 知识库（dry-run 模式，不改文件）"""
    result = do_sync({"yaml_dir": yaml_dir, "md_dir": md_dir})
    return result.get("text", json.dumps(result, ensure_ascii=False))


@mcp.tool()
def ssot_extract(
    file_path: str, domain_dir: str = "", use_llm: bool = False, model: str = ""
) -> str:
    """从文件中提取知识结构（实体/事实），支持模板和 LLM"""
    result = do_extract(
        {
            "file_path": file_path,
            "domain_dir": domain_dir,
            "use_llm": use_llm,
            "model": model,
        }
    )
    return result.get("text", json.dumps(result, ensure_ascii=False))


# ── 域管理工具 (来自 services/integration/mcp_server.py) ──

ECOS_SRC = Path(__file__).resolve().parent

# 复用 domain-manager 逻辑
# 用 importlib.util 正确加载为包内模块, 使 relative import (.domain_manager_cache) 可用
import importlib.util as _ilu

_DM_PATH = ECOS_SRC / "services" / "governance" / "domain_manager.py"
_spec = _ilu.spec_from_file_location(
    "ecos.services.governance.domain_manager", _DM_PATH
)
dm = _ilu.module_from_spec(_spec)  # type: ignore[reportArgumentType]
_spec.loader.exec_module(dm)  # type: ignore[reportOptionalMemberAccess]


@mcp.tool()
def domain_list(type: str = "") -> str:
    """列出所有已注册域 · 19域7类型。type 可选: document|config|engine|tool|workspace|storage|model"""
    r = dm.load_registry()
    result = []
    for d in r:
        if type and d.get("domain_type") != type:
            continue
        result.append(
            {
                "id": d["id"],
                "name": d.get("name", ""),
                "type": d.get("domain_type", "document"),
                "layer": d.get("layer", "L4"),
                "bos_uri": f"bos://{d['id']}",
            }
        )
    return json.dumps({"domains": result, "total": len(result)}, ensure_ascii=False)


@mcp.tool()
def domain_stats() -> str:
    """全域统计概览"""
    r = dm.load_registry()
    types = Counter(d.get("domain_type", "document") for d in r)
    layers = Counter(d.get("layer", "L4") for d in r)
    return json.dumps(
        {"total": len(r), "by_type": dict(types), "by_layer": dict(layers)},
        ensure_ascii=False,
    )


@mcp.tool()
def domain_validate(domain: str) -> str:
    """校验域 KEMS 六面结构完整性"""
    r = dm.load_registry()
    d = dm.find_domain(r, domain)
    if not d:
        return json.dumps({"error": f"域未注册: {domain}"})
    p = dm.resolve_path(d)
    if not p.exists():
        return json.dumps({"error": f"路径不存在: {p}"})
    results = dm.validate_domain(
        p, d.get("domain_type", "document"), d.get("governance_tier", 1)
    )
    return json.dumps(
        {
            "domain": d.get("name", d["id"]),
            "path": str(p),
            "checks": [{"name": n, "pass": ok, "detail": dt} for n, ok, dt in results],
            "passed": sum(1 for _, ok, _ in results if ok),
            "failed": sum(1 for _, ok, _ in results if not ok),
        },
        ensure_ascii=False,
    )


@mcp.tool()
def domain_resolve(uri: str) -> str:
    """BOS URI → 物理路径解析。例: bos://vault/_state → STATE.md"""
    r = dm.load_registry()
    d, s = dm.parse_bos_uri(uri, r)
    if not d:
        return json.dumps({"error": f"无法解析: {uri}"})
    p = dm.resolve_path(d)
    full = str(p / s if s else p)
    return json.dumps(
        {
            "uri": uri,
            "physical_path": full,
            "exists": os.path.exists(full),
            "domain": d.get("name", d["id"]),
            "type": d.get("domain_type", "?"),
        },
        ensure_ascii=False,
    )


@mcp.tool()
def domain_read(uri: str, max_lines: int = 50) -> str:
    """通过 BOS URI 读取资源内容 · 支持语义化快捷"""
    r = dm.load_registry()
    d, s = dm.parse_bos_uri(uri, r)
    if not d:
        return json.dumps({"error": "无法解析"})
    p = dm.resolve_path(d)
    full = p / s if s else p
    if not full.exists():
        return json.dumps({"error": f"不存在: {full}"})
    if full.is_dir():
        items = sorted(os.listdir(full))
        return json.dumps(
            {"uri": uri, "type": "directory", "items": items[:50], "total": len(items)},
            ensure_ascii=False,
        )
    content = full.read_text()
    lines = content.split("\n")
    return json.dumps(
        {
            "uri": uri,
            "type": "file",
            "size": len(content),
            "lines": len(lines),
            "content": "\n".join(lines[:max_lines]),
            "truncated": len(lines) > max_lines,
        },
        ensure_ascii=False,
    )


@mcp.tool()
def domain_search(query: str, max_results: int = 10) -> str:
    """跨域搜索 · grep 全量 CLAUDE.md + STATE.md + _knowledge"""
    r = dm.load_registry()
    results = []
    for d in r:
        did = d["id"]
        p = dm.resolve_path(d)
        if not p.exists():
            continue
        for sd in ["CLAUDE.md", "_control/STATE.md", "_knowledge"]:
            sp = p / sd
            if not sp.exists():
                continue
            try:
                cmd = [
                    "grep",
                    "-rn",
                    "--include=*.md",
                    "--include=*.yaml",
                    "-l",
                    query,
                    str(sp),
                ]
                rr = _subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                for line in rr.stdout.strip().split("\n"):
                    if line and len(results) < max_results:
                        try:
                            rel = str(Path(line).relative_to(p))
                        except Exception:  # defensive fallback
                            rel = line
                        results.append(
                            {"uri": f"bos://{did}/{rel}", "domain": did, "file": rel}
                        )
            except Exception:  # defensive fallback
                pass
    return json.dumps({"results": results, "total": len(results)}, ensure_ascii=False)


@mcp.tool()
def domain_tree(domain: str) -> str:
    """域目录树 · KEMS 着色"""
    r = dm.load_registry()
    d = dm.find_domain(r, domain)
    if not d:
        return json.dumps({"error": f"域未注册: {domain}"})
    p = dm.resolve_path(d)
    if not p.exists():
        return json.dumps({"error": f"路径不存在: {p}"})

    def _tree(dir_path, depth=0):
        if depth > 3:
            return []
        items = sorted(
            [
                i
                for i in dir_path.iterdir()
                if not i.name.startswith(".") and not i.name.startswith("__")
            ],
            key=lambda x: (not x.is_dir(), x.name),
        )
        result = []
        for item in items:
            node = {"name": item.name, "type": "dir" if item.is_dir() else "file"}
            if item.is_dir() and depth < 2:
                node["children"] = _tree(item, depth + 1)
            result.append(node)
        return result

    return json.dumps(
        {"domain": d.get("name", d["id"]), "tree": _tree(p)}, ensure_ascii=False
    )


@mcp.tool()
def ecos_health() -> str:
    """全系统健康检查 (9项)"""
    r = _subprocess.run(
        ["python3", str(ECOS_SRC / "scripts" / "ecos-health-check.py"), "--json"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    try:
        return json.dumps(json.loads(r.stdout), ensure_ascii=False)
    except Exception:  # defensive fallback
        return r.stdout[:500]


@mcp.tool()
def ecos_brief() -> str:
    """会话简报 · 当前状态快照"""
    r = _subprocess.run(
        ["python3", str(ECOS_SRC / "scripts" / "ecos-brief.py"), "--json"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    try:
        return json.dumps(json.loads(r.stdout), ensure_ascii=False)
    except Exception:  # defensive fallback
        return r.stdout[:500]


# ── 工作流工具 ──


@mcp.tool()
def workflow_list(domain: str = "", layer: str = "", status: str = "") -> str:
    """列出所有已注册工作流 · 按域/层/状态过滤。domain可选: memory|omo|analysis|persona|forge|meta|infra。layer可选: L0|L1|L2|I0|L3|L4。status可选: defined|active|deprecated|archived"""
    try:
        from ecos.workflow import list_from_m1

        nodes = list_from_m1()
        filtered = []
        for n in nodes:
            if domain and n.get("domain") != domain:
                continue
            if layer and n.get("layer") != layer:
                continue
            if status and n.get("status") != status:
                continue
            filtered.append(n)
        return json.dumps(
            {
                "workflows": filtered,
                "total": len(filtered),
                "filtered_from_total": len(nodes),
            },
            ensure_ascii=False,
        )
    except Exception as e:  # defensive fallback
        return json.dumps({"error": str(e), "workflows": [], "total": 0})


@mcp.tool()
def workflow_show(name: str) -> str:
    """查看指定工作流完整定义 · 步骤/关系/SLA/跨层映射"""
    try:
        from ecos.workflow import load_workflow

        wf = load_workflow(name)
        if not wf:
            return json.dumps({"error": f"工作流未找到: {name}"}, ensure_ascii=False)
        return json.dumps(wf, ensure_ascii=False)
    except Exception as e:  # defensive fallback
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def workflow_run(name: str, dry_run: bool = False) -> str:
    """执行 ecos L0 工作流 · 通过 workflow engine 路由到对应后端

    Args:
        name: 工作流名称 (M1 ID, e.g. WORKFLOW-ECOS-DAILY-HEALTH)
        dry_run: 干跑模式，只打印不执行
    """
    try:
        from ecos.workflow import execute_m1_workflow

        result = execute_m1_workflow(name, dry_run=dry_run)
        safe = {}
        for k, v in result.items():
            try:
                json.dumps(v)
                safe[k] = v
            except (TypeError, ValueError):
                safe[k] = str(v)
        return json.dumps(safe, ensure_ascii=False)
    except Exception as e:  # defensive fallback
        return json.dumps({"error": str(e), "workflow": name}, ensure_ascii=False)


@mcp.tool()
def workflow_validate(name: str) -> str:
    """验证工作流定义 · 运行 X1-X4 约束检查"""
    try:
        from ecos.workflow import load_workflow
        from ecos.workflow.validator import validate_workflow

        wf = load_workflow(name)
        if not wf:
            return json.dumps({"error": f"工作流不存在: {name}"}, ensure_ascii=False)
        violations = validate_workflow(wf)
        errors = [v for v in violations if v.get("severity") == "error"]
        warnings = [v for v in violations if v.get("severity") != "error"]
        return json.dumps(
            {
                "name": name,
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
                "total_violations": len(violations),
            },
            ensure_ascii=False,
        )
    except Exception as e:  # defensive fallback
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def workflow_backends() -> str:
    """列出所有已注册 workflow backend · 当前可用的执行后端"""
    try:
        from ecos.workflow import list_backends

        return json.dumps({"backends": list_backends()}, ensure_ascii=False)
    except Exception as e:  # defensive fallback
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def workflow_actions() -> str:
    """列出所有已注册 workflow action · 可用步骤动作"""
    try:
        from ecos.workflow.actions import list_actions

        return json.dumps({"actions": list_actions()}, ensure_ascii=False)
    except Exception as e:  # defensive fallback
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def workflow_logs(recent: int = 10, status: str = "") -> str:
    """查询工作流运行历史 · M0 快照

    Args:
        recent: 最近 N 条, 默认 10
        status: 过滤条件 ok/failed, 空=全部
    """
    try:
        from ecos.cli.workflow_runs import SNAPSHOT_DIR, _load_all_runs

        runs = _load_all_runs()
        if status:
            runs = [r for r in runs if r.get("status") == status]
        runs = runs[:recent]
        safe = []
        for r in runs:
            safe.append(
                {
                    k: v
                    for k, v in r.items()
                    if isinstance(v, (str, int, float, bool, list, dict)) or v is None
                }
            )
        return json.dumps(
            {
                "runs": safe,
                "total": len(safe),
                "snapshot_dir": str(SNAPSHOT_DIR),
            },
            ensure_ascii=False,
        )
    except Exception as e:  # defensive fallback
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def workflow_test(name: str) -> str:
    """测试工作流编排（mock action，不执行真实脚本） · 验证步骤/依赖/后端/约束"""
    try:
        from ecos.workflow.executor import test_workflow

        result = test_workflow(name)
        safe = {}
        for k, v in result.items():
            try:
                json.dumps(v)
                safe[k] = v
            except (TypeError, ValueError):
                safe[k] = str(v)
        return json.dumps(safe, ensure_ascii=False)
    except Exception as e:  # defensive fallback
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def workflow_cache_status() -> str:
    """查询工作流缓存状态 · 命中数/条目数/缓存条目详情"""
    try:
        from ecos.workflow.cache import status

        return json.dumps(status(), ensure_ascii=False)
    except Exception as e:  # defensive fallback
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def workflow_cache_invalidate(workflow_name: str = "") -> str:
    """使工作流缓存失效 · 空=全量失效

    Args:
        workflow_name: 指定工作流名，空字符串=全部清除
    """
    try:
        from ecos.workflow.cache import invalidate, invalidate_all

        if workflow_name:
            cleared = invalidate(workflow_name)
            return json.dumps(
                {
                    "invalidated": True,
                    "workflow": workflow_name,
                    "entries_cleared": cleared,
                },
                ensure_ascii=False,
            )
        else:
            cleared = invalidate_all()
            return json.dumps(
                {
                    "invalidated": True,
                    "all": True,
                    "entries_cleared": cleared,
                },
                ensure_ascii=False,
            )
    except Exception as e:  # defensive fallback
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def workflow_circuit_breaker_status() -> str:
    """查询后端熔断器状态 · 当前不可达的后端列表"""
    try:
        from ecos.workflow.circuit_breaker import status

        return json.dumps(status(), ensure_ascii=False)
    except Exception as e:  # defensive fallback
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def workflow_circuit_breaker_reset(backend: str = "") -> str:
    """重置后端熔断器 · 空=全量重置

    Args:
        backend: 后端名称（如 agora/swarm/runtime），空=全部清除
    """
    try:
        from ecos.workflow.circuit_breaker import reset, reset_all

        if backend:
            reset(backend)
            return json.dumps({"reset": True, "backend": backend}, ensure_ascii=False)
        else:
            count = reset_all()
            return json.dumps(
                {"reset": True, "all": True, "entries_reset": count}, ensure_ascii=False
            )
    except Exception as e:  # defensive fallback
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ── 主入口 ──


def main():
    print("⚠️ ECOS MCP 独立 CLI 已弃用，请使用 cockpit 替代", file=sys.stderr)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
