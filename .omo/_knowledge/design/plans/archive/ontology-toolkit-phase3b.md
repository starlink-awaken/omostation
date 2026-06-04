# Phase 3B: Pipeline 编排

## 任务清单

### T1: Pipeline 协议定义 + `eidos pipeline` CLI ✅
- `eidos/src/eidos/pipeline/__init__.py` — PipelineDef, PipelineStep, run_pipeline
- `eidos/src/eidos/cli.py` — 扩展 `eidos pipeline --file <yaml>` 命令

### T2: 工具适配器 ✅
- `kos/commands/pipeline.py` — kos 的 pipeline 模式
- `minerva/src/minerva/knowledge/pipeline_adapter.py` — minerva 适配
- `ontoderive/engine/ecosystem/pipeline_adapter.py` — ontoderive 适配

### T3: 测试 ✅
- `eidos/tests/test_pipeline.py` — 7 tests
