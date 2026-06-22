---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# ADR-0003: P28 TECH-RADAR 实施绕过 agora 网关

- **Status**: ACCEPTED
- **Date**: 2026-06-05
- **Authors**: omostation P28-W3
- **Supersedes**: (无)
- **Superseded by**: (无)

## Context and Problem Statement

P28-W1-TECH-RADAR 任务是"技术雷达简报自动生成"，数据流是
`fetcher（抓 ArXiv/GitHub/HuggingFace） → analyzer（评分） → kos_writer
（写入知识库）`，输出物为 `.omo/_delivery/tech-radar-2026-06-05-report.md`。
问题是：

- **场景**: P28-W1 必须在收尾前产出可演示的 TECH-RADAR 简报，作为 W1 健康度证据
- **痛点**: 严格按"全部 L1 包走 agora 网关"的 Phase 27 治理原则，TECH-RADAR
  实施需先把 fetcher / analyzer / kos_writer 3 个服务在 agora 注册（共 3 条路由），
  但 P28-W0 审计发现 agora 路由表基本空、且 ADR-0001 已决定"按需注册"
- **约束**:
  - W1 时间窗紧（< 1 周），走 agora 完整注册 + 健康检查 + 调用方验证流程无法
    在 W1 收尾前完成
  - agora 注册失败的 fallback 路径未定义（一旦失败 = W1 任务卡住）
  - 演示场景中 3 个服务是"线性调用链"，没有跨服务共享状态需求
- **决策张力**: 与 Phase 27 "agora 作为唯一 L0 网关"原则有局部冲突

## Decision Drivers

* **W1 收尾必须出可演示产出**: P28-W1-E2E-DEMO 依赖 TECH-RADAR 简报作为健康证据
* **agora 治理债务**: agora 路由表当前基本空（4% 覆盖），注册 3 条新路由
  等于"先上车后补票"，违反"先有调用方验证、再有路由"原则（见 ADR-0001）
* **回滚成本低**: TECH-RADAR 是只读分析任务（抓取 + 评分 + 写入），不修改
  上游数据，绕过 agora 不会污染其他系统
* **后续治理路径明确**: W2+ 阶段可单独安排"agora 注册 fetcher / analyzer /
  kos_writer"任务（与 P28-W3-ADR-SETUP 平行）

## Considered Options

1. **绕过 agora + 直接调 kairon 包（fetcher → analyzer → kos_writer）**（推荐）
2. 严格走 agora：先注册 3 个服务、再调用
3. 跳过 TECH-RADAR，等 W2/W3 agora 治理完成再做

## Decision Outcome

**Chosen option: "1. 绕过 agora + 直接调 kairon 包（fetcher → analyzer → kos_writer）",
because W1 阶段必须出可演示产出，agora 修复放后续 wave；TECH-RADAR 是只读分析
任务，绕过 agora 不会污染其他系统，且后续可低成本回接到 agora。**

具体执行路径：

```
W1 TECH-RADAR (T+0):
  fetcher.py → 直接 import kairon.fetcher（绕过 agora）
  analyzer.py → 直接 import kairon.analyzer
  kos_writer.py → 直接 import kairon.kos_writer
  输出 → .omo/_delivery/tech-radar-2026-06-05-report.md

W2+ agora 治理:
  注册 fetcher / analyzer / kos_writer 3 个服务到 agora
  改造 W1 脚本为 agora 客户端（`agora.call("fetcher.fetch", ...)`）
  保留 1 周双写过渡期（直连 + agora 都跑、对比结果）
```

### Consequences

* Good: W1 收尾前可演示（不受 agora 治理债务阻塞）
* Good: 绕过 agora 不影响其他系统（TECH-RADAR 是只读分析）
* Good: 明确 W2+ agora 治理路径，不留技术债
* Bad: 局部违反"全部走 agora"原则（W1 期间 3 个包不走）
* Bad: 后续改回 agora 需双写过渡期（1 周），有短期维护成本
* Bad: W1 阶段 agora 监控盲区（fetcher / analyzer / kos_writer 无调用指标）

### Confirmation

* 短期（W1 收尾）: `.omo/_delivery/tech-radar-2026-06-05-report.md` 生成成功，
  内容含 ≥ 30 条抓取项 + Top 11 升级候选
* 中期（W2 入口）: agora 治理任务 P28-W2-AGORA-REG 已计划（未启动），
  含 fetcher / analyzer / kos_writer 3 个服务注册
* 长期（W3+）: W1 直连脚本已废弃或改造为 agora 客户端，
  `grep "from kairon.fetcher import" scripts/` 应为 0 结果（或仅在过渡分支）

## Pros and Cons of the Options

### 1. 绕过 agora + 直接调 kairon 包

* Good: W1 收尾有产出（不受 agora 阻塞）
* Good: 不污染其他系统（只读分析）
* Good: 后续回接 agora 路径明确（1 周双写过渡）
* Bad: 局部违反 Phase 27 治理原则
* Bad: agora 监控盲区

### 2. 严格走 agora：先注册 3 个服务

* Good: 严格遵守"全部走 agora"原则
* Good: agora 监控完整
* Bad: W1 时间窗内无法完成注册 + 健康检查 + 调用方验证
* Bad: 一旦注册失败 = W1 任务卡住（无 fallback）
* Bad: 与 ADR-0001 "按需注册"原则冲突（这 3 个服务的"按需"还没到 W1）

### 3. 跳过 TECH-RADAR，等 agora 治理完成

* Good: 不引入任何治理债务
* Good: 不违反任何原则
* Bad: W1 健康证据缺失，P28-W1-E2E-DEMO 受影响
* Bad: 进度倒退 1 周（P28-W1 整体延后）
* Bad: 与 P28-W0-NORTH-STAR 计划的"W1 出 TECH-RADAR 简报"目标冲突

## References

* `.omo/_delivery/tech-radar-2026-06-05-report.md` — W1 TECH-RADAR 实际产出
* `.omo/tasks/planned/P28-W1-TECH-RADAR.yaml` — TECH-RADAR 任务规约
* `.omo/tasks/planned/P28-W1-E2E-DEMO.yaml` — 依赖 TECH-RADAR 简报的演示任务
* ADR-0001: agora 路由表精简策略（L1 包按需注册的总原则）
* Phase 27 治理简报 — agora v2.0.0 网关定位
