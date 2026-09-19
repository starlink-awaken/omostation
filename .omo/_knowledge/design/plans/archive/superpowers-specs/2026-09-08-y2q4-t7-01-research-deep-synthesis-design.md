---
schema_version: specification/v1
spec_version: 1.0.0
title: BET-Y2Q4-T7-01 specification
bet_id: BET-Y2Q4-T7-01
status: accepted
lifecycle: contract
owner: governance-agent
last-reviewed: 2026-09-08
---


# Spec: 生命科学与大模型架构前沿文献自动精读与技术选型沙盘

## Motivation

知识层归并（T6-02，9,097 LOC 减法）之后，知识系统需要一个**真实信号源**来驱动
本体图谱与场景卡进化。当前领域知识更新依赖人工追踪 PubMed/BioRxiv/arXiv，
无自动化精读链路。本 bet 建立文献自动精读 pipeline：抓取 → 相关性过滤 →
三段式精读卡（摘要/方法/影响）→ 创新点提取 → 技术选型权衡矩阵。

## 关键事实（D1 真理验证，2026-09-08）

- `projects/domain-cartridges/research/` 与 `docs/scene-cards/research-deep-synthesis.yaml`
  均不存在（本次新建）。
- `docs/scene-cards/` 既有场景卡生命周期：draft → shadow → assisted → supervised → routine
  （`.omo/standards/scene-card-lifecycle.yaml`）。done_when ① 要求 research-deep-synthesis
  场景卡晋级 **assisted**（需 30-sample + calibration ≥ 0.6）。
- 测试命令 `uv run python -m domain.research.test_synthesis_pipeline` 需在
  `projects/domain-cartridges/` 包结构内可运行。

## 交付物

1. `docs/scene-cards/research-deep-synthesis.yaml` — 场景卡（晋级 assisted）
2. `projects/domain-cartridges/research/` — 精读 pipeline 包：
   - 论文抓取源适配（PubMed/BioRxiv/arXiv，网络异常安全跳过）
   - 相关性过滤 + 每日 Top-3 精读
   - 三段式精读卡生成（摘要/方法/影响）
   - 技术选型权衡矩阵输出
3. `projects/domain-cartridges/research/test_synthesis_pipeline.py` — verify 测试

## 非目标

- 不进行海量无筛选文献的低质堆砌（non_goals）
- 不做真实网络抓取的端到端验证（网络依赖，circuit_breaker 安全跳过）

## 验证路径

- `uv run python -m domain.research.test_synthesis_pipeline` → exit 0
- `make gac-local-gate` → exit 0
- 场景卡生命周期校验（assisted 需 shadow 3-sample 基线 + calibration ≥ 0.6）
