# STRAT-P81 Batch 1 大工单 — 兑现期第一冲刺（多角色 + 注册中心 + 纵贯线）

> Status: **CLOSED** · 2026-07-24 · Appetite: **2-3 周** · Closeout: `.omo/_knowledge/audits/2026-07-24-batch1-closeout.md`
> 上位: STRAT-P81 (PROPOSED) + ADR-0228 (ACCEPTED, M1 通过/物理挂起/S2 提前解锁)
> 交接单: `.omo/plans/strat-p81-agent-execution-brief.md`（启动序列/红线/升级协议全部适用, 不重抄）
> **用户授权范围**: 本工单内全部任务一次性授权执行, 含按 AGENTS.md §6 既有 PR 流程落 main;
> 仍需逐项人类拍板的例外见 §E。**12 项任务, 按 A→E 波次推进, 波内可并行。**

---

## A 波 · 收口与看板（先做, ~0.5 天）

### A1 · 遗留 run 收口
- run `20260724T053532Z-governance-state-mutation-46126fa9` 补 verify + closeout（其 claims: ADR-0228/INDEX/brief/本工单）
- `needs-human-p81-m1-acceptance` 卡关闭, 关闭理由引用 ADR-0228
- 工作树未提交项（STRAT-P80/P81、ADR-0228、nodes.yaml、S0 审计）按既有 PR 流程落 main
- **验收**: `git status` 干净; compliance 无 active 悬挂 run

### A2 · 物理挂起周提醒机制（ADR-0228 D3 落地）
- session-brief/foundry 管线加一条: `needs-human-p80-physical-hosts` 卡存在时, BRIEF Inbox 每周一重申（含挂起天数）
- **验收**: BRIEF 出现带天数的重申行; 机制有测试或 dry-run 记录

## B 波 · S2 多角色协作（本工单主菜, ~1.5 周）

### B1 · 角色定义框架 + 协作协议（ADR 先行）
- 立 ADR: 3 角色首发（建议 engineering / governance / audit, 可按现有 agent profile 映射）,
  角色 = 能力集 + 权限边界 + 协作消息协议; 落 aetherforge/swarm 或 metaos（架构选择写进 ADR）
- 实现角色注册/加载/切换; 单测覆盖
- **验收**: ADR ACCEPTED + 3 角色可实例化, 协议消息可回放

### B2 · 3 角色真实任务试点（≥10 任务）
- 用真实 backlog 任务（如 debt 卡、doc 修复、测试补齐）跑 3 角色协作: 分派→执行→审计
- 每任务留协作轨迹（谁做了什么、交接点）
- **验收**: ≥10 任务完成, 轨迹入 audits, 失败任务有归因

### B3 · 角色记忆共享（gbrain, 承接 W3 资产）
- 角色间跨任务上下文写入/检索走 gbrain; **隔离边界测试**: 角色 A 不可读角色 B 私有上下文
- **验收**: 共享/隔离各有通过的测试; 检索延迟记录

### B4 · G-DEL.2b 正式测量（≥30 任务批次）
- 在 B1-B3 之上跑 ≥30 任务测量批, 计算 3 角色协作完成率
- `env_class` 如实标注（process-local 口径为 ADR-0225 官方允许）
- **验收**: 完成率报告入 audits; **>95% → 写 G-DEL.2b 达标申请卡进 Inbox（人类确认后才宣布）**; 未达标 → 归因 + 改进项立卡

### B5 · 角色指标进 X3/BRIEF
- 每角色完成率/成本进 BRIEF 仪表（复用 X3 管线, 指针化取数）
- **验收**: BRIEF 可见角色行

## C 波 · S1 非物理项（与 B 波并行, ~1 周）

### C1 · Agent 注册中心（设计 ADR + 实现）
- ADR: 节点/角色/能力三级注册模型, 心跳与假死检出, 与 agora I0 网关关系
- 实现 + 本地/sim 测试（多进程模拟节点即可, **只填 `meets_sim_harness`**）
- **验收**: sim 环境 4 逻辑节点注册/心跳/假死检出全过测试

### C2 · 分布式调度 harness 常态化（sim）
- 调度批任务 harness 接 foundry cron 每日跑（sim 口径）, 输出 success rate 趋势
- 机器恢复后同一 harness 直接切物理 endpoint（预留配置位）
- **验收**: cron 连续 3 天产出 sim 报告; 切换物理只改配置不改代码

### C3 · 故障转移设计 ADR + 演练脚本（纸面+脚本, 不依赖真机）
- ADR: 节点失联时任务迁移策略; 拔线演练脚本写好待机器恢复即用
- **验收**: ADR ACCEPTED + 演练脚本 dry-run 通过

## D 波 · 纵贯线（贯穿全程）

### D1 · KOS 增量 + 质量抽检
- 按既有 seed 管线加一批增量; 抽检 ≥20 篇准确率记录（沿用 EX05 抽检格式）
- **验收**: `measured_documents` 增长写回 goals + evidence audit

### D2 · 治理周巡检（本批内跑一轮）
- `compliance --json` + P74 沉默 workflow 检查 + health 快照核对; 异常写卡
- **验收**: 巡检报告入 audits

## E 波 · 收尾复盘（最后, ~1 天）

### E1 · Batch 1 closeout 审计 + 下批提案
- 12 项逐项对账（done/partial/blocked + evidence 链接）入 audits
- 更新 brief §1 解锁表; **Batch 2 提案卡**（含 G-DEL.2b 达标申请如适用）写进 BRIEF Inbox 等人类拍板
- **验收**: 审计 + 提案卡齐; 本工单状态改 CLOSED

---

## 仍需人类逐项拍板（不在本次授权内）

1. G-DEL.2b **官方达标宣布**（B4 只交申请卡）
2. 涌现类/S3 任何工作（本工单不含, 领了就是违规）
3. KOS 新数据源接入（D1 只用既有源）
4. 物理机相关的任何"恢复"宣称（等真机探测）

## 熔断条件（触发即停当前波次, 写卡升级）

- health < 95 · 单项预算超 30% · B4 完成率 < 80%（说明框架有结构性问题, 不硬冲指标）

---

*生成: 2026-07-24 · run: 20260724T053532Z-governance-state-mutation-46126fa9 · Appetite 2-3 周 · 12 任务*
