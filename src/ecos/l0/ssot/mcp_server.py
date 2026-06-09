#!/usr/bin/env python3
"""SSOT Kernel MCP Server — stdio JSON-RPC

让 Claude 在对话中直接运行 check/derive/extract/evolve。

注册到 Reasonix:
    add_mcp_server name=ssot command=python3 args=["tool/ssot-kernel/mcp_server.py"]

MCP Protocol: JSON-RPC 2.0 over stdin/stdout
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# 定位 ssot-kernel 源码（基于脚本自身位置，不依赖 cwd）
_SCRIPT_DIR = Path(__file__).resolve().parent
_SRC_DIR = _SCRIPT_DIR / "src"
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent  # SSOT 项目根
sys.path.insert(0, str(_SRC_DIR))

from .config_loader import load_domain  # noqa: E402
from .engine import RuleEngine  # noqa: E402
from .evolution.evolver import Evolver  # noqa: E402
from .extractor import TextSource  # noqa: E402
from .extractor.pipeline import ExtractionPipeline  # noqa: E402
from .reporter import Reporter  # noqa: E402
from .sync import sync_yaml_to_markdown  # noqa: E402

# ── 工具定义 ─────────────────────────────────────────


def _domain_path(dd: str) -> str:
    """解析领域目录路径，不存在时抛出友好异常"""
    # 尝试直接/相对路径
    p = Path(dd)
    if p.exists():
        return str(p.resolve())
    # 尝试相对脚本目录（tool/ssot-kernel/）
    alt = _SCRIPT_DIR / dd
    if alt.exists():
        return str(alt.resolve())
    # 尝试相对项目根
    alt2 = _PROJECT_ROOT / dd
    if alt2.exists():
        return str(alt2.resolve())
    raise FileNotFoundError(
        f"领域目录不存在: {dd}（已尝试: {p}, {alt}, {alt2}）\n  可用路径示例: domains/guozhuan"
    )


TOOLS = [
    {
        "name": "check",
        "description": "运行 SSOT 规则检查，返回每条规则的执行结果",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain_dir": {
                    "type": "string",
                    "description": "领域配置目录，默认 domains/guozhuan",
                    "default": "domains/guozhuan",
                }
            },
        },
    },
    {
        "name": "derive",
        "description": "执行全量规则引擎推导，生成 Markdown 报告",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain_dir": {
                    "type": "string",
                    "default": "domains/guozhuan",
                    "description": "领域配置目录",
                },
                "rounds": {
                    "type": "integer",
                    "default": 1,
                    "description": "多轮迭代次数",
                },
            },
        },
    },
    {
        "name": "compile",
        "description": "编译 YAML 为 JSON，含 Schema 校验 + 跨文件引用检查",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain_dir": {
                    "type": "string",
                    "default": "domains/guozhuan",
                    "description": "领域配置目录",
                },
            },
        },
    },
    {
        "name": "evolve",
        "description": "进化分析：从数据中挖掘新规则建议（只读，不修改文件）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain_dir": {
                    "type": "string",
                    "default": "domains/guozhuan",
                    "description": "领域配置目录",
                },
            },
        },
    },
    {
        "name": "stats",
        "description": "输出知识库统计信息（实体/事实/推论分布、引用热度）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain_dir": {
                    "type": "string",
                    "default": "domains/guozhuan",
                    "description": "领域配置目录",
                },
            },
        },
    },
    {
        "name": "sync",
        "description": "同步 YAML 引擎数据到 Markdown 知识库（dry-run 模式，不改文件）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "yaml_dir": {
                    "type": "string",
                    "description": "YAML 领域目录",
                },
                "md_dir": {
                    "type": "string",
                    "description": "Markdown 知识本体根目录",
                },
            },
            "required": ["yaml_dir", "md_dir"],
        },
    },
    {
        "name": "extract_from_file",
        "description": "从文件中提取知识结构（实体/事实），支持模板和 LLM",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "源文件路径（绝对路径或相对项目根）",
                },
                "domain_dir": {
                    "type": "string",
                    "default": "",
                    "description": "目标领域目录（写入目标）",
                },
                "use_llm": {
                    "type": "boolean",
                    "default": False,
                    "description": "强制使用 LLM 提取",
                },
                "model": {
                    "type": "string",
                    "default": "",
                    "description": "LLM 模型名（如 qwen3.5:4b）",
                },
            },
            "required": ["file_path"],
        },
    },
]


# ── 工具实现 ─────────────────────────────────────────


def do_check(args: dict) -> dict:
    dd = _domain_path(args.get("domain_dir", "domains/guozhuan"))
    config = load_domain(dd, use_cache=True)
    report = RuleEngine().execute(config)

    lines = [f"## {Reporter.summary_line(report)}", ""]
    for r in report.results:
        icon = "✅" if r.passed else ("🔴" if r.severity == "BLOCKER" else "🟠")
        lines.append(f"{icon} **{r.protocol_id}**: {r.name}")
        for d in r.details[:5]:
            lines.append(f"  {d}")
        lines.append("")

    return {
        "text": "\n".join(lines),
        "summary": Reporter.summary_line(report),
        "passed": report.passed,
        "total": report.total_rules,
        "blocker": report.blocker,
        "error": report.error,
    }


def do_derive(args: dict) -> dict:
    dd = _domain_path(args.get("domain_dir", "domains/guozhuan"))
    rounds = args.get("rounds", 1)
    config = load_domain(dd, use_cache=True)
    report = RuleEngine().execute(config, rounds=rounds)

    return {
        "text": Reporter.to_markdown(report),
        "summary": Reporter.summary_line(report),
        "passed": report.passed,
        "total": report.total_rules,
    }


def do_compile(args: dict) -> dict:
    dd = _domain_path(args.get("domain_dir", "domains/guozhuan"))
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        from .cli import cmd_compile

        # 模拟 argparse args
        class FakeArgs:
            dir = dd
            no_cache = False

        ret = cmd_compile(FakeArgs())

    output = buf.getvalue()
    return {
        "text": output.strip(),
        "exit_code": ret,
    }


def do_evolve(args: dict) -> dict:
    dd = _domain_path(args.get("domain_dir", "domains/guozhuan"))
    evolver = Evolver(dd)
    report = evolver.analyze()

    lines = [f"## 进化分析: {report.summary}", ""]
    for s in report.suggestions:
        tier_icon = {"high": "🔴", "medium": "🟡", "low": "🔵"}
        icon = tier_icon.get(s.tier, "⚪")
        lines.append(f"{icon} **[{s.tier}]** {s.name}")
        lines.append(f"  置信度: {s.confidence}")
        lines.append(f"  理由: {s.rationale[:120]}")
        lines.append("")

    return {
        "text": "\n".join(lines),
        "suggestion_count": len(report.suggestions),
    }


def do_extract(args: dict) -> dict:
    fp = args.get("file_path", "")
    if not os.path.exists(fp):
        return {"error": f"文件不存在: {fp}"}

    text = Path(fp).read_text("utf-8")
    source = TextSource(raw_text=text, source_name=os.path.basename(fp))
    pipe = ExtractionPipeline(domain_dir=args.get("domain_dir", ""))

    use_llm = args.get("use_llm", False)
    if use_llm:
        from .extractor.llm import LLMExtractor, OllamaBackend

        model = args.get("model", "") or os.environ.get("OLLAMA_MODEL", "qwen3.5:4b")
        llm_ext = LLMExtractor(backends=[OllamaBackend(model=model)])
        if llm_ext.can_handle(source):
            pipe.extractors = [llm_ext]

    result = pipe.run(source, auto_write=False)
    extraction = result["result"]

    lines = [f"提取 {len(extraction.candidates)} 个候选"]
    for c in extraction.candidates[:15]:
        snippet = c.source_snippet or json.dumps(c.content, ensure_ascii=False)[:60]
        lines.append(f"  [{c.category}] {c.id or '(无ID)'} — {snippet}")

    return {
        "text": "\n".join(lines),
        "count": len(extraction.candidates),
        "entity_count": len(extraction.entity_candidates),
        "fact_count": len(extraction.fact_candidates),
    }


def do_stats(args: dict) -> dict:
    dd = _domain_path(args.get("domain_dir", "domains/guozhuan"))
    config = load_domain(dd, use_cache=True)
    orgs = len([e for e in config.entities if e.entity_type == "Organization"])
    roles = len([e for e in config.entities if e.entity_type == "Role"])
    projects = len([e for e in config.entities if e.entity_type == "Project"])
    policies = len([f for f in config.facts if f.id.startswith("POL-")])
    data = len([f for f in config.facts if f.id.startswith("DAT-")])
    return {
        "text": (
            f"📊 统计: {config.domain.get('name', 'unknown')}\n"
            f"  实体: {len(config.entities)} (组织{orgs} 角色{roles} 项目{projects})\n"
            f"  事实: {len(config.facts)} (政策{policies} 数据{data})\n"
            f"  推论: {len(config.inferences)}\n"
            f"  规则: {len(config.rules)}\n"
            f"  关系: {len(config.relations)}\n"
            f"  状态机: {len(config.state_machines)}\n"
            f"  约束: {len(config.constraints)}"
        ),
    }


def do_sync(args: dict) -> dict:
    report = sync_yaml_to_markdown(
        yaml_dir=args["yaml_dir"],
        md_dir=args["md_dir"],
        dry_run=True,
    )
    lines = [
        f"同步报告: 新增{len(report.items_added)} 跳过{len(report.items_skipped)} 冲突{len(report.items_conflict)}"
    ]
    for fname, eid in report.items_added[:20]:
        lines.append(f"  ✅ {fname}: {eid}")
    if len(report.items_added) > 20:
        lines.append(f"  ... 还有 {len(report.items_added) - 20} 条")
    return {"text": "\n".join(lines), "new_items": len(report.items_added)}


HANDLERS = {
    "check": do_check,
    "derive": do_derive,
    "compile": do_compile,
    "evolve": do_evolve,
    "stats": do_stats,
    "sync": do_sync,
    "extract_from_file": do_extract,
}


# ── JSON-RPC 处理 ────────────────────────────────────


def handle_message(msg: dict) -> dict | None:
    method = msg.get("method", "")
    msg_id = msg.get("id")

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}

    elif method == "tools/call":
        name = msg.get("params", {}).get("name", "")
        raw_args = msg.get("params", {}).get("arguments", {}) or {}
        try:
            handler = HANDLERS.get(name)
            if not handler:
                raise ValueError(f"未知工具: {name}，可用: {', '.join(HANDLERS)}")
            result = handler(raw_args)
            error = result.pop("error", None)
            text = result.pop("text", str(result))
            content = [{"type": "text", "text": text}]
            if error:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -1, "message": error},
                }
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"content": content, "meta": result},
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -1, "message": f"{type(e).__name__}: {e}"},
            }

    elif method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "ssot-kernel", "version": "2.0.0"},
            },
        }

    elif method == "notifications/initialized":
        return None

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"未知方法: {method}"},
    }


# ── 主循环（stdio） ──────────────────────────────────


def main():
    buffer = ""
    for line in sys.stdin:
        buffer += line
        try:
            msg = json.loads(buffer)
            buffer = ""
        except json.JSONDecodeError:
            continue

        response = handle_message(msg)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
