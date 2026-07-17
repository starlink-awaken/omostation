---
title: 三年战略 · c2g 对齐审计报告
status: draft
type: strategy-audit
owner: 夏明星
created: 2026-07-15
related:
  - docs/STRATEGY-3YEAR-PANORAMA.md
  - .omo/_knowledge/decisions/0210-three-year-strategy-execution-convergence.md
  - projects/c2g/.c2g_data/bets.json
  - projects/c2g/.c2g_data/tasks.json
note: >
  本报告记录 ADR-0210 三年战略经 c2g (Concept→Pitch→Bet→Task) 管线拆解后的
  战略对齐审计 (radar) 结果。任务属性为 local adapter 草案态，正式入 .omo 需
  切 ecos adapter + ADR-0203 workflow。
---

# 三年战略 · c2g 对齐审计报告（2026-07-15）

## 一、拆解概览

ADR-0210 三年战略的 15 个举措，经 c2g 正规桥接（CR-STRATEGY-01 孤儿拦截 + M2 Schema 校验）
物化为 **15 Pitch → 15 Bet → 15 Task**，覆盖三阶段无缺口。

| 阶段 | 举措数 | Appetite 区间 |
|------|--------|--------------|
| 一 · 收敛期（P44）| 6 | 2 小时 – 1 周 |
| 二 · 兑现期（P50）| 5 | 4 – 8 周 |
| 三 · 跃迁期（P60）| 4 | 6 – 8 周 |

## 二、radar 战略对齐审计结果（回填后）

```
📊 Task Inventory: 0 done + 15 planned = 15 total

📈 Priority:  P1=7   P0=4   P2=4
🛡️  Risk:     L2=6   L1=6   L3=2   L0=1
👥 Owner:     架构师=7  后端=5  SRE=2  前端=1
🌊 Phase:     收敛期=6  兑现期=5  跃迁期=4
🏷️  Status:   planned=15
🚨 Anomaly:   ⚠️ L3 高风险任务 2 个, 需重点 review
```

### 对齐判定

| 维度 | 状态 | 说明 |
|------|------|------|
| **覆盖对齐** | ✅ | 15/15 举措有 Bet+Task，阶段分布 6/5/4 与路线图一致，无孤儿 |
| **北极星对齐** | ✅ | 每个 Pitch 声明 Upstream，全过 CR-STRATEGY-01 |
| **优先级对齐** | ✅ | P0=4（Isolation/runtime/注册中心/角色框架）符合战略拍板项 |
| **风险对齐** | ✅ | L0–L3 分层，高风险集中在涌现/数字孪生（隐私+不可控） |
| **Owner 对齐** | ✅ | 分散到 4 角色，架构师 47% 低于 50% 单点阈值 |
| **门禁对齐** | ✅ | 15 Task 全部 `wait_for_gate: BET_APPROVED`（待批准下注） |

### 保留告警（预期，非噪声）

- **L3 高风险 2 项需 review**：`涌现检测+集体决策`（涌现不可控）、`个人数字孪生`（隐私）。
  这是战略真实高风险信号，radar 正确捕获；两项均已在 Pitch NoGos 设人工干预/本地存储约束。

## 三、阶段依赖 DAG

```mermaid
graph TD
    subgraph 收敛期 P44 · 只治本
        A0[P0 Agent Isolation<br/>BET-be85 · 架构师]
        A1[P0 修复 L1 runtime<br/>BET-0059 · SRE]
        A2[P1 重构 health_score<br/>BET-036b · 架构师]
        A3[P1 gitlink cron<br/>BET-8d92 · SRE]
        A4[P1 KOS 索引启动<br/>BET-b8c5 · 后端]
        A5[P2 单写者+门禁免疫<br/>BET-aa56 · 架构师]
    end

    M1{{M1 门禁 2027Q1<br/>daemon≥90% + 零主仓冲突}}

    subgraph 兑现期 P50 · 蜂群落地
        B0[P0 Agent 注册中心+调度<br/>BET-7e07 · 后端]
        B1[P0 角色框架+协议<br/>BET-664e · 架构师]
        B2[P1 状态同步+故障转移<br/>BET-3e60 · 后端]
        B3[P1 角色记忆共享<br/>BET-b7da · 后端]
        B4[P2 涌现+集体决策 ⚠L3<br/>BET-8c7c · 架构师]
    end

    M2{{M2 门禁 2027Q4<br/>多机可用≥85%}}

    subgraph 跃迁期 P60 · 个人大脑+外溢
        C0[P1 个人知识图谱<br/>BET-2522 · 后端]
        C1[P1 个人 AI 助手<br/>BET-c17d · 前端]
        C2[P2 数字孪生 ⚠L3<br/>BET-ede9 · 架构师]
        C3[P2 治理产品化<br/>BET-ef25 · 架构师]
    end

    A0 --> M1
    A1 --> M1
    A2 --> M1
    A5 --> M1
    A1 -.daemon稳.-> A2
    M1 --> B0
    M1 --> B1
    B0 --> B2
    B1 --> B3
    B2 --> B4
    B1 --> B4
    M1 --> M2
    B0 --> M2
    B1 --> M2
    A4 -.KOS积累.-> C0
    M2 --> C0
    C0 --> C1
    C0 --> C2
    C1 --> C2
    M2 --> C3
```

### 关键依赖链

- **收敛期是总门禁**：M1 不达标（daemon ≥ 90% / 并发 agent 零主仓冲突）不进兑现期——这是
  ADR-0210「只治本不加功能」纪律的硬约束。
- **A1（修 runtime）→ A2（health_score）**：daemon 稳后重构权重才有意义。
- **A4（KOS 启动）→ C0（个人知识图谱）**：跨越两阶段的长链，收敛期不启动 KOS，跃迁期个人大脑缺数据。
- **B1（角色框架）→ B3/B4**：角色记忆与涌现都依赖角色框架先立。
- **C0（知识图谱）→ C1/C2**：助手与孪生都建在个人图谱之上。

## 四、待办与后续

1. **属性入库**：当前 priority/risk/owner 为对齐审计而回填，正式生效需切 `--adapter ecos`
   并按 ADR-0203 先 `agent-workflow.py start`。
2. **大 Bet 二次拆细**：兑现/跃迁期 Bet appetite 多为 6–8 周，启动时应按 sub-pitch 再拆。
3. **L3 两项前置评审**：涌现、数字孪生启动前需专项风险评审（人工干预开关 / 隐私审计路径）。
4. **Owner 落实**：4 角色分工已定，具体到人待资源到位。

---

*审计工具: `c2g --adapter local radar` · 数据源: .c2g_data/tasks/planned/*.yaml · 2026-07-15*
