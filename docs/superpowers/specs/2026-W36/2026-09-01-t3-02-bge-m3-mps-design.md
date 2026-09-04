---
schema_version: specification/v1
spec_version: 1.0.0
title: Local Metal-MPS embedding & rerank engine
bet_id: BET-Y1Q4-T3-02
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-01
last_updated: 2026-09-01
type: ssot
last_updated: 2026-09-03
---

# Local Metal-MPS embedding & rerank engine (T3-02)

## Intent

替换外部公有向量 API：MBP M5 Max 与 Mac mini M4 本地部署 BGE-M3 多语言
多粒度嵌入 + BGE-Reranker-Large，Apple Silicon MPS 硬件加速，毫秒级时延。
100% 本地离线（数据零离境红线）；不使用损失精度的极低量化（non_goal）。

## Phased rollout (approved: 全面推进)

- **P1 引擎面（零下载）**：`embedding_mps.py` + `reranker.py` + benchmark 契约，
  用已缓存的 bge-small-zh-v1.5 跑真基准；MPS 探测 + CPU 降级链。
- **P2 满配模型**：BGE-M3（dense+sparse+multi-vec）+ BGE-Reranker-Large 下载
  部署，dense+sparse 混合打分 + 多语言 done_when 全达成。
- **P3 mesh 服务化**：Mac mini M4 经现有 cluster_coordinator 注册为嵌入
  服务节点（bos://compute/omlxc/embed，Phase B 远程化）。

## Architecture (KISS)

```
projects/omlxc/src/omlxc/dataplane/embedding_mps.py（嵌入引擎）
├─ resolve_device() — mps > cpu（Apple Silicon Metal，禁止 CUDA 分支）
├─ EmbeddingEngine(model_name, device)
│   ├─ encode(texts) → dense vectors (fp32, no lossy quant)
│   ├─ encode_sparse(texts) → CSR-style token-weight dict（BGE-M3 sparse 权重）
│   └─ hybrid_score(dense_q, dense_docs, sparse_q, sparse_docs, alpha) 混合打分
├─ MODEL_TIER: bge-small-zh-v1.5 (cached, fast) | BAAI/bge-m3 (full, dense+sparse)
└─ RESOURCE_CAP: max_memory_fraction 0.35（本地资源受限规则）

projects/omlxc/src/omlxc/dataplane/reranker.py（重排引擎）
├─ RerankEngine(model_name, device).rerank(query, docs, top_k)
│   └─ cross-encoder 分数 → 排序 + 时延统计
└─ MODEL_TIER: BAAI/bge-reranker-large

projects/omlxc/src/omlxc/dataplane/embedding_mps_benchmark.py（verify 薄壳）
└─ python -m omlxc.dataplane.embedding_mps_benchmark → run_benchmark() exit 0
    断言: 单条 encode ≤15ms; Top-50 rerank ≤30ms; offline; device 报告
```

## Latency contracts (done_when)

- 单条向量化 ≤15ms（bge-small MPS 实测量级 ~1-3ms；M3 亦在预算内）
- Top-50 重排 ≤30ms（reranker-large 分批；超时走 circuit_breaker 降级 dense 排序）
- Dense+Sparse 混合：alpha 加权（默认 0.7 dense），多语言文本混合评测断言

## Degradation (circuit_breaker)

MPS 不可用 → CPU；reranker 超预算 → dense 余弦排序降级并标注 degraded。

## Verify (BET contract)

- `uv run python -m omlxc.dataplane.embedding_mps_benchmark` → exit 0
- `make gac-local-gate` → exit 0
