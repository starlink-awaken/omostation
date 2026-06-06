# ADR-0001: agora 路由表精简策略 — L1 包按需注册

- **Status**: ACCEPTED
- **Date**: 2026-06-05
- **Authors**: omostation P28-W3
- **Supersedes**: (无)
- **Superseded by**: (无)

## Context and Problem Statement

Phase 27 完成 OMO 蜂群网络纪元后，agora 网关定位为"唯一 L0 MCP 服务发现/代理/断路器"。
但 P28-W0-TOOL-HEATMAP 审计发现，agora 的路由表当前**基本空**：31 个 L1 包中只有 4%
（约 1-2 个包）已注册到 agora。问题是：

- **场景**: P28 进入"工具瘦身 + 知识工作流可观测化"阶段，需要决定 agora 路由表的
  增长节奏：是批量预注册全部 31 包，还是只注册当前真正在用的包？
- **痛点**: 一次性批量注册全部 31 包会引入**半生不熟的路由**（register 但无调用方验证、
  无健康检查基线、出问题难以定位），且与 P28-W2-PKG-SLIM 即将归档的策略冲突
  （归档后还要回滚路由）。
- **约束**:
  - agora 已有断路器与发现机制，注册是低成本的（不强制调用方改动）
  - 但路由上线后需在 `agora/router.py` 中维护，超出"零运维"基线
  - 首批 P28-W1-E2E-DEMO 演示只用到 fetcher → analyzer → kos_writer 3 个包
    （详见 ADR-0003）

## Decision Drivers

* **可观测性优先**: 路由表应有"谁在用、调用频次、错误率"等可观测信号；批量预注册
  会让这些信号被噪声淹没
* **瘦身协同**: P28-W2-PKG-SLIM 正在精简 L1 包，归档时若需同步清理 agora 路由，
  会显著增加归档操作的复杂度
* **零外部破坏**: agora 是 L0 公共组件，注册失败可能影响全部下游 L1 包；
  风险必须用"按需"方式隔离
* **演示驱动**: P28-W1-E2E-DEMO 只需最小可演示子集，无需全量注册

## Considered Options

1. **L1 包用直接包调用 + 后续按需注册**（推荐）
2. 批量预注册全部 31 个 L1 包
3. agora 路由表保持空，强制所有 L1 包不经过 agora 直连

## Decision Outcome

**Chosen option: "1. L1 包用直接包调用 + 后续按需注册", because agora 路由表基本空
（4% 覆盖），强行批量注册会引入半生不熟路由；按需注册保证"先有调用方验证、
再有路由"，最大化降低运维与归档协同成本。**

### Consequences

* Good: agora 路由表保持瘦小，新路由上线时已有调用方证据；归档 L1 包时无需同步
  清理 agora 路由
* Good: agora 故障域被最小化（已注册的少量路由 = 高置信度路由）
* Bad: L1 包不经过 agora 失去集中观测（需在 L1 包自身加埋点或用其他手段补齐）
* Bad: 后续 L1 包要做 agora 路由时需走完整注册流程，有一定启动成本

### Confirmation

* 短期验证（P28 收尾时）: agora 路由表条目数 ≤ 当前已验证的 E2E 演示调用链
  （≤ 5 条），且每条都有对应的调用方 + 调用频次记录
* 中期验证（P29 入口）: 如有新 L1 包上线，对应路由在 1 周内被注册
  （即"按需" = "周级别按需"，不是"项目级别批量"）
* 长期验证: 归档 L1 包时无 agora 路由清理工作项（路由数 ≈ 0）

## Pros and Cons of the Options

### 1. L1 包用直接包调用 + 后续按需注册

* Good: 最小风险，最大灵活性
* Good: 与 P28-W2-PKG-SLIM 瘦身策略无冲突
* Good: agora 故障域最小化
* Bad: 失去集中观测的统一入口
* Bad: 新 L1 包上线需走注册流程

### 2. 批量预注册全部 31 个 L1 包

* Good: agora 立即成为"完整路由表"，调用方零感知
* Bad: 31 个路由中至少 25 个无调用方、无健康检查基线 = 纯噪声
* Bad: 与 P28-W2 归档策略冲突（归档 = 同步清理路由 = 双倍工作）
* Bad: agora 故障域被放大（一个烂路由 = 全部 L1 包受影响）
* Bad: 不符合 Phase 27 治理债务"零半生不熟状态"原则

### 3. agora 路由表保持空 + L1 包强制不经过 agora

* Good: 极致简单
* Bad: 等于废弃 agora 主体功能（路由表空 = agora 不工作）
* Bad: 未来需要集中观测时需重做 agora，工作量 ≥ 方案 1 的两倍
* Bad: 与 Phase 27 已落地的"agora 作为唯一 L0 网关"决策直接冲突

## References

* `.omo/_knowledge/management/tool-heatmap-phase28.md` — P28-W0 工具热力图审计
* `.omo/_delivery/phase28-pkg-slim-plan.md` — P28-W2 包瘦身计划
* `.omo/tasks/planned/P28-W1-TECH-RADAR.yaml` — TECH-RADAR 任务（演示链路消费方）
* Phase 27 治理简报 — agora v2.0.0 网关定位
