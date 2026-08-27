"""Pre-built pipeline templates.

Each preset is a Pipeline with named steps ready to run.
"""

# Determine workspace root from current file location
import os

from eidos.pipeline import Pipeline, PipelineStep

_WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

KNOWLEDGE_BASE = Pipeline(
    name="知识库构建 (完整版)",
    steps=[
        PipelineStep(tool="eidos", action="meta", args={"export": True}, output_file="/tmp/pipe-meta.json"),
        PipelineStep(
            tool="kos",
            action="ingest",
            args={"path": os.path.join(_WORKSPACE, "knowledge", "ingested"), "dry_run": True, "verbose": False},
            output_file="/tmp/pipe-ingest.json",
        ),
        PipelineStep(
            tool="kos",
            action="search",
            args={"query": "", "limit": 5, "meta-type": "document"},
            output_file="/tmp/pipe-search.json",
        ),
        PipelineStep(tool="eidos", action="viz", args={"type": "graph"}),
    ],
)

REASONING = Pipeline(
    name="推理链路 (完整版)",
    steps=[
        PipelineStep(
            tool="kos", action="search", args={"query": "", "limit": 5}, output_file="/tmp/pipe-reason-search.json"
        ),
        PipelineStep(tool="ontoderive", action="derive", args={"eidos": True}, output_file="/tmp/pipe-derive.json"),
        PipelineStep(tool="eidos", action="viz", args={"type": "graph"}, output_file="/tmp/pipe-viz.json"),
    ],
)

# KOS 数据管线 preset. 注: kos ingest/search 的 path/query 是 positional, 但 eidos
# to_cli() 只生成 --flag (L32-37), 不兼容. 故本 preset 用 status/domains (无
# positional) 做状态验证. 实质索引 (FTS5 + LanceDB 向量) 由 kos daemon 常驻维护:
#   python -m kos.maintenance.indexer --daemon --interval 300
# (indexer --daemon/--full-embed/L323 修复见 kairon commit d3329c1)
KOS_DATA = Pipeline(
    name="KOS 数据管线 (摄取→FTS5索引→状态, 向量由 kos daemon 常驻维护)",
    steps=[
        PipelineStep(
            tool="kos",
            action="ingest",
            positionals=[os.path.join(_WORKSPACE, "data", "kos")],
            output_file="/tmp/pipe-kos-ingest.json",
        ),
        PipelineStep(
            tool="kos",
            action="status",
            args={"format": "json"},
            output_file="/tmp/pipe-kos-status.json",
        ),
    ],
)

PRESETS = {
    "knowledge-base": KNOWLEDGE_BASE,
    "reasoning": REASONING,
    "kos-data": KOS_DATA,
}
