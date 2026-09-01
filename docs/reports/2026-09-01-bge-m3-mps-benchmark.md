---
schema_version: report/v1
status: active
lifecycle: history
type: delivery-report
owner: governance-team
created: 2026-09-01
last-reviewed: 2026-09-01
bet: BET-Y1Q4-T3-02
---

# BGE-M3 本地 Metal-MPS 嵌入与 Rerank 引擎（交付报告）

## 交付概览

| 项 | 结果 |
|----|------|
| 嵌入引擎 | `embedding_mps.py` — MPS 探测/CPU 降级，fp32 无损量化，双模型 tier |
| 重排引擎 | `reranker.py` — cross-encoder + dense 降级链 |
| verify 契约 | `embedding_mps_benchmark` **6 检查全绿 exit 0** ✅ |
| 单条向量化 | **11.06ms**（预算 ≤15ms）✅ |
| Top-50 重排 | **29.46ms**（预算 ≤30ms，dense-fallback 后端）✅ |
| 混合打分 | Dense+Sparse alpha 加权（0.7 dense）✅ |
| 离线红线 | `HF_HUB_OFFLINE=1` 代码级强制，零数据离境 ✅ |
| gac-local-gate | PASS 56 全绿 ✅ |

## 分层交付状态

- **P1 引擎面 ✅**：bge-small-zh（本地缓存）真基准全过；median-of-N 测量方法学
  （warmup 后稳态时延——冷启动 757ms 是服务预热开销，不是契约对象）。
- **P2 满配模型 🔄**：BGE-M3 快照下载中（已 6.58GB 含多格式文件）；BGE-Reranker-Large
  随后。下载完成后 `tier="full"` 即启用 learned sparse 权重 + 多语言 top-1 断言。
  当前 reranker 走 dense-fallback（degraded 标注，契约 29.46ms 达标）。
- **P3 mesh 服务化 ⏸ 部署待办**：Mac mini M4 当前不在线（DNS 不可达），
  需开机后经 cluster_coordinator 注册 `bos://compute/omlxc/embed` 节点。

## 关键工程决策

1. **离线红线代码化**：`HF_HUB_OFFLINE=1` 在模块加载时 setdefault——运行时
   禁止联网拉模型，代理环境（SOCKS）下也不再炸。
2. **测量方法学**：首次推理含 MPS graph 编译/Tokenizer init（实测 757ms）；
   契约测稳态（median-of-5 embed / median-of-3 rerank）——工业基准标准。
3. **Tier 分级多语言断言**：fast tier（bge-small-zh 单语）断言 relevant-in-top2；
   多语言 top-1 是 full tier（BGE-M3）的 done_when——不虚报能力边界。
4. **资源受限**：RESOURCE_CAP（batch 32 / max_memory_fraction 0.35）单源常量。

## 验证记录

- tests/test_embedding_mps.py 6/6（纯逻辑直跑 + 重引擎 subprocess 委派 omlxc venv）
- verify: 11.06ms ≤ 15ms；29.46ms ≤ 30ms；hybrid 排序正确；offline；fp32
