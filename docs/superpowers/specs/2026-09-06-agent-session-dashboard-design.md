---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-06
last-reviewed: 2026-09-06
bet_id: BET-Y1Q4-T9-01
risk_level: L1
human_gate: false
value_indicator_policy: false
type: ssot
---

# Agent Session Dashboard（ASD）规格

> **定位**：新 agent 会话冷启动时加载的**无 UI 信息聚合面板**。  
> **形态**：Markdown + JSON（`asd.session.v1`），可选 ASCII/Mermaid；**不是** Web Dashboard。  
> **台账**：`BET-Y1Q4-T9-01`（本规格）→ `BET-Y1Q4-T9-02`（MVP）→ `BET-Y1Q4-T9-03`（全板块+MCP+drill）。

---

## 1. 问题陈述

今日会话冷启动要拼齐「现在该干什么」，需串跑多条互不统一的命令：

| 表面 | 缺口 |
|------|------|
| `agent-workflow bootstrap` | 无台账/SFOP/价值 KR/风险热图 |
| `omo-status` | 人机 Rich 面板，难程序化下钻 |
| `cockpit brief` / `workspace_context` | 仅 cards/phase 切面 |
| `kos-cold-start` | 依赖 KOS MCP，非常态结构化面板 |
| `bet-ledger status` | 需主动查，不在启动路径 |

结果：信息孤岛、缺少板块隔离的 IA、无可机读上下钻契约、触发分散（CLAUDE Step A/B）。

---

## 2. Goals / Non-goals

### Goals

1. 一条命令（或 bootstrap 钩子）产出可指导行动的全景面板。  
2. 固定 **8 板块** + **维度隔离**；板块间只互链 `refs`，不串表。  
3. 多样呈现：表格 / Mermaid / spark / callout / 摘要 / 命令块。  
4. **上下钻**：L0 Header → L1 Panel → L2 Dimension → L3 Evidence/Commands。  
5. 稳定 `--json` schema，供 MCP / skill 消费。  
6. **只读聚合**现有真源，不新建第二套 SSOT 写面。

### Non-goals

- Web / cockpit-ui 页面（`cockpit dashboard` 另轨）。  
- 替代 `bet-ledger` / `omo audit` 写面。  
- v1 全量 KOS 向量检索（可 degraded）。  
- 把运行时数值硬编码进 `CLAUDE.md`。  
- 新增平行 Mesh dispatcher / 第二 OS。

---

## 3. 信息架构

### 3.1 三层导航

```
L0  Session Header（≤30s 可读）
    ├─ overall health + ≤3 highlights
    ├─ primary_action + alt_actions[2]
    └─ panel drill index
L1  Panels（8，严格隔离）
L2  Dimensions（agent 决策维）
L3  Evidence / Commands（path | cmd | receipt）
```

- **下钻**：`asd --panel P-LEDGER` / `asd --dim D-BET` / JSON path。  
- **上钻**：L3 → dimension summary → panel lamp → Header。

### 3.2 八大板块（信息隔离）

| Panel | 问题 | 主数据源（只读） | 禁止混入 |
|-------|------|------------------|----------|
| **P-ORIENT** | 优化什么？ | VISION / OBJ-* / CMP-* / north_star | 锁、子模块细节 |
| **P-ARCH** | 脊骨健康？ | SFOP、project-registry、layer-index | BET 进度数字 |
| **P-GOV** | 门禁/漂移？ | meta-doctor、gac、P74、governance-checks | 业务场景正文 |
| **P-LEDGER** | 领哪个 BET？ | 3y-bet-ledger、claimable/in_progress | 代码健康细节 |
| **P-SWARM** | 谁在写？ | omo-status JSON、locks、worktrees | 战略叙事 |
| **P-VALUE** | 署名/采纳？ | north_star meters、journey/KR | GaC 规则列表 |
| **P-KNOW** | ADR/债务？ | AGENT-BRIEF 指针、ADR 索引、KOS 可选 | CI 红灯细节 |
| **P-NEXT** | 立刻做什么？ | 规则裁定（非 LLM） | 重复全文拷贝 |

跨板块只允许 `cross_refs[{from,to,reason}]`。

### 3.3 维度映射（投影自 dimension-system，非 1:1 堆砌）

| ASD Dim | 对齐 | 主面板 | 形态 |
|---------|------|--------|------|
| D-HEALTH | D7+X2 | P-GOV / Header | 灯号 + score |
| D-SSOT | X4 | P-ARCH / P-GOV | 漂移表 |
| D-AUDIT | X1 | P-GOV | 违规计数 |
| D-VALUE | X3/D5 | P-ORIENT / P-VALUE | KR 表 |
| D-SCENE | D1/D3 | P-KNOW | 场景生命周期摘要 |
| D-SURFACE | D8 / Y1 减法 | P-GOV / P-NEXT | 净增减警示 |
| D-BET | D6 | P-LEDGER | 窗口进度 + claimable |
| D-SWARM | 运营横切 | P-SWARM | 锁/心跳表 |
| D-ARCH | SFOP/DFSQ | P-ARCH | Mermaid 槽位图 |
| D-ACTION | — | P-NEXT | 有序命令块 |

### 3.4 Widget 类型（v1）

`callout` · `kpi` · `table` · `mermaid` · `spark` · `prose` · `commands` · `ref`

### 3.5 Header 裁定（可测、非 LLM）

优先级高→低：

1. 硬红：SFOP fail / 主树脏且非 worktree / 关键写面锁冲突  
2. 台账腐蚀信号 / P74 silent>0 且无 check coverage  
3. 可认领 P0（无 ★）  
4. 价值 KR 未测缺口  
5. 默认：`agent-workflow suggest` 或读 AGENT-BRIEF → status  

输出：`primary_action` / `alt_actions[2]` / `stop_conditions[]`。

---

## 4. 技术架构

### 4.1 组件

```
Trigger: CLAUDE Step B / make agent-workflow-bootstrap
      → optional ASD_ON_BOOTSTRAP=1 / --with-asd
CLI:    bin/agent-session-dashboard.py  (Phase 1)
        compact | full | panel | json
MCP:    session_dashboard (Phase 2)
Collectors → normalizer(asd.session.v1) → renderer
真源（禁止复制写）:
  bootstrap_report · omo-status --json · bet-ledger
  check-sfop-slots · workspace_context · north_star · meta-doctor
```

- **落点**：根仓薄聚合器；可选 `cockpit asd` 包装同一实现。  
- **禁止**：本规格交付 cockpit-ui 页面。

### 4.2 Schema `asd.session.v1`

```yaml
schema: asd.session.v1
generated_at: ISO8601
workspace_root: path
health: {overall: green|yellow|red, reasons: [string]}
header:
  one_liner: string
  highlights: [{level, text, ref}]
  primary_action: {title, cmd, rationale}
  alt_actions: [{title, cmd}]
panels:
  - id: P-LEDGER
    title: 台账执行
    status: green|yellow|red|unknown
    summary: string
    dimensions:
      - id: D-BET
        widgets:
          - type: table|mermaid|callout|kpi|spark|prose|commands
            data: ...
            drill: {up, down, evidence: [path|cmd|receipt]}
cross_refs: [{from, to, reason}]
degraded: [{source, error}]
```

### 4.3 性能预算

| 模式 | 预算 | 行为 |
|------|------|------|
| compact（默认） | ≤2.0s | Header + 红黄板块；慢源跳过 |
| full | ≤8.0s | 全 panels |
| panel X | ≤3.0s | 单板块 |
| json | 同档 | 无 Rich 开销 |

KOS / remote submodule probe 默认 lazy + degraded。

### 4.4 与现有命令

| 现有 | 关系 |
|------|------|
| bootstrap | Phase 2 末尾可挂 compact（可关） |
| omo-status | collector，保留 |
| cockpit brief | collector → P-KNOW/P-NEXT；长期可 thin-wrap |
| kos-cold-start | P-KNOW 可选增强 |
| CLAUDE.md | **仅指针**，不贴数值 |

---

## 5. 触发路径（会话）

1. **Phase 0（本 bet）**：`CLAUDE.md` Step B 增加 ASD 规格/未来 CLI 指针。  
2. **Phase 1**：`python bin/agent-session-dashboard.py --mode compact` 可独立运行。  
3. **Phase 2**：`make agent-workflow-bootstrap` 默认附带 compact（`ASD_ON_BOOTSTRAP=0` 可关）；MCP `session_dashboard`。

---

## 6. 分阶段交付

| Phase | BET | 交付 |
|-------|-----|------|
| **0** | **T9-01（本）** | 本规格 + 台账/战役关联 + CLAUDE 指针 |
| 1 | T9-02 | MVP aggregator + 5 核心面板 + 单测 |
| 2 | T9-03 | 全 8 面板 + bootstrap 钩子 + MCP + drill |
| 3 | 可选 | Mermaid/spark 打磨；收敛 brief 重复面 |

---

## 7. 验收（T9-01）

- [x] 本文件含 IA / schema / 触发 / 阶段 / 验收  
- [ ] `3y-bet-ledger.yaml` 含 `BET-Y1Q4-T9-01`、`CMP-Y1-AGENT-ORIENT`、`MS-Y1-ASD-SPEC`  
- [ ] `bet-ledger.py lint` / `show` / `portfolio lint` 通过  
- [ ] `CLAUDE.md` 有 ASD 入口指针（无硬编码数值）

---

## 8. 风险与表面积

| 风险 | 缓解 |
|------|------|
| 再堆状态脚本 | collector 复用；禁新 SSOT 写面 |
| 拖慢会话 | compact 默认 + 超时 degraded |
| 与 cockpit dashboard 混淆 | 正式名 ASD；CLI `agent-session-dashboard` / `asd` |
| 台账并发腐蚀 | 最小 diff；冲突则拆 PR |

**Y1 约束**：Phase 1 若新增 `bin/agent-session-dashboard.py`，须在复盘中记账，并优先标示可收敛的重复面（如 brief 薄包装）。

---

## 9. Compact 输出示意

```
ASD · <timestamp> · overall=YELLOW
一句话：脊骨绿；台账窗口有缺口；优先真相/减法，勿盲目扩面。

重点：
  ⚠ <最高优先级信号>
  · SFOP / P74 / KR 摘要

主动作： <cmd>
备选： <cmd> · <cmd>
drill: P-LEDGER | P-ARCH | P-VALUE | P-NEXT
```

---

## 10. 关联

- Campaign：`CMP-Y1-AGENT-ORIENT` → Objective：`OBJ-HOLDABILITY`  
- Milestone：`MS-Y1-ASD-SPEC` → required bet：`BET-Y1Q4-T9-01`  
- Track：`T9-OBSERV`  
- 后续：`BET-Y1Q4-T9-02` / `T9-03`（实现轨，本文件仅预告）
