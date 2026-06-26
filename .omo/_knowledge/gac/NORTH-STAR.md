# GaC 北极星 — 治理即代码 (Governance-as-Code)

> **锚定 GaC 体系的方向 / 不变量 / 反模式. 防走偏的北极星.**
> 日期: 2026-06-26 | 决策: ADR-0106 | SSOT: 本文件 + `.omo/_truth/registry/governance-checks.yaml`
> 维护: 任何 GaC 方向变更必须更新本文件 + 记 ADR

---

## GaC 是什么

把 X1-X4 治理维度 + M0/L0/L2 治理规则, 通过**声明式注册表 + 统一执行通道**, 实现"规则定义 / 执行 / 工具三层分离"的治理架构.

对标: **OPA (策略即数据)** + omostation 独有 **MOF 元模型派生**.

不是新 project, 不是新层. 是**横切关注点的统一治理面** — 激活已有零件 (governance-checks.yaml + ADR + 四平面 + agora 横切先例).

---

## 北极星 (系统目标)

> 让 omostation 的治理从「事后审计 + 散落规则」转向「声明式 + drift 自愈 + 元治理」, 支撑**多 agent/多 session 并行不冲突** + **规则动态增长不漂移**.

两个核心能力:
1. **多 agent 并行** — worktree 隔离 + 协议强制 + GaC 规则兜底
2. **动态一致性** — 规则/hook 持续增长, 结构不矛盾, 实现不漂移

---

## 不变量 (必须满足, 违反 = 走偏)

1. **规则 SSOT** — `governance-checks.yaml` 是唯一规则源, 各工具读它不复制
2. **声明式** — 规则是数据 (YAML), 不是代码 (硬编码检查逻辑)
3. **执行通道统一** — 规则通过 hook / MCP / gate 执行, 不散落在各工具内部
4. **drift 必检** — 注册表 vs 实际执行定期双向校验 (radar 原语)
5. **元模型约束** — 规则上 MOF M1, 元模型派生保证结构一致 (mof-validate)

---

## 反模式 (禁止)

- ❌ **硬编码规则** — 代码里写死检查逻辑 (必须登记到注册表)
- ❌ **规则散落** — 多文件多注册表 (governance-checks.yaml 是唯一源)
- ❌ **无 drift 检测** — 规则声明了不执行, 无告警 (必须 radar 定期检)
- ❌ **无 lifecycle** — 死规则堆积 (必须 draft/active/deprecated + gc 清理)
- ❌ **新建 project 装 GaC** — GaC 是横切不是层 (执行器是 omo/ecos/model-driven)
- ❌ **协议靠自觉** — 锁/worktree 不接 hook 强制 = 摆设 (必须执行通道兜底)

---

## 动态一致性 7 机制 (规则/hook 增长保证)

> 这是「规则增长 + 一致性」的根治答案.

| # | 机制 | 作用 | 对标 |
|---|------|------|------|
| 1 | **声明式规则** | 加规则 = 加 YAML, 不改代码 | OPA policy |
| 2 | **schema 校验** | 加规则时强制结构 (id/dimension/layer/check_type/executor/lifecycle/version) | pydantic/jsonschema |
| 3 | **泛化执行器** | hook/MCP 读注册表按 check_type 执行, 规则变执行器不变 | OPA 引擎 |
| 4 | **drift 检测 + 自愈** | 注册表 vs 实际执行双向校验, 漏执行自动绑定 | K8s controller / GitOps |
| 5 | **矛盾检测** | 规则间一致性 (同 target 矛盾 severity 告警) | OPA policy conflict |
| 6 | **版本 + lifecycle** | draft→active→deprecated→removed, 语义化版本 + 共存期 | K8s API deprecation |
| 7 | **MOF 元模型派生** | M1 RuleDefinition → M2 RuleInstance → M3 ExecutionBinding, 元模型约束 | omostation 独有 (OPA 没有) |

**核心**: 动态性靠机制 1+3 (声明式 + 泛化执行器), 一致性靠机制 2+4+5+7 (schema + drift + 矛盾 + 元模型).

---

## Roadmap 6 阶段

| 阶段 | 重点 | 核心交付 | 代码量 |
|------|------|---------|:------:|
| **0 激活** | 北极星 + schema + 登记 + ADR | 规则可视, 方向锚定 | 零代码 |
| **1 绑定** | AGENTS.md 导出 + 泛化 hook + MCP 内置 | 执行统一 | 中 |
| **2 动态一致** | schema 校验 + drift + 矛盾 + lifecycle | 防走偏上线 | 中 |
| **3 元模型** | 规则上 MOF M1 + 派生链 | 元模型约束 | 中 |
| **4 度量** | 仪表盘 + drift 自愈 | 元治理闭环 | 中 |
| **5 常态化** | radar 每日 + gc 每周 | 持续治 | cron |

详见 [roadmap-v1.md](./roadmap-v1.md).

---

## 元治理递归 (最深刻的一点)

> GaC 治一切, **GaC 自己也要被治** — 用 GaC 的机制治 GaC.

| 维度 | GaC 治业务 | GaC 治 GaC 自己 (元治理) |
|------|-----------|------------------------|
| X1 审计 | 审计 agent 操作 | 审计 GaC 规则执行 (触发率/违规率) |
| X2 抗熵 | 检测数据 drift | **检测 GaC 自己 drift** (注册表 vs 实现) ← 防走偏核心 |
| X3 价值 | 任务 ROI | 规则 ROI (哪些规则真拦问题, 哪些噪音) |
| X4 一致 | SSOT | 规则 SSOT (governance-checks.yaml 唯一源) |

**你担忧的「久了走偏」= X2 抗熵对 GaC 自己的应用**. drift 检测 GaC 实现是否还匹配注册表. **GaC 用自己的机制防自己漂移**.

---

## c2g 元治理循环 (落地机制)

c2g 五原语**天然是 GaC 元治理循环** (设计同构, 不是工具复用):

```
brainstorm  →  GaC 新规则想法收口 (规则提案来源)
   ↓
draft       →  规则 Pitch (结构化: 维度/层/check_type/ROI)
   ↓
bet         →  Pitch → governance-checks.yaml 条目 + OMO Task
   ↓
radar       →  drift 检测 (注册表 vs 实际执行)  ← 机制 4
   ↓
gc          →  过时规则清理 (lifecycle deprecate)  ← 机制 6
```

---

## 不走偏红线 (日常执行准则)

- 任何**规则变更** → 走 ADR + 注册表 + drift 检测
- 任何**执行通道变更** → 注册表 `executor` 字段同步
- 任何**架构偏离** → 对照本北极星 + ADR-0106, 不符则先改 ADR
- 任何**新规则** → schema 校验 + lifecycle=draft 起步 + radar 验证执行
- 任何**规则废弃** → lifecycle=deprecated + gc 28 天清理

---

## 对标 (行业验证)

| 方案 | 借鉴点 | GaC 对应 |
|------|--------|---------|
| **OPA** | 策略即数据 + 多点执行 | governance-checks.yaml + hook/MCP/gate |
| **Styra (OPA 平台)** | policy lifecycle + 审计 + 可视化 | 规则 lifecycle + drift + 仪表盘 |
| **K8s Admission** | API 级治理 + webhook | PreToolUse hook |
| **GitOps** | 声明式 + drift 自愈 | X2 抗熵 + drift 自愈 |
| **Terraform Sentinel** | 策略即代码 | GaC 执行通道 |

**omostation 独有优势**: 机制 7 (MOF 元模型派生) — OPA 没有元模型层, GaC 规则上 M1 比纯 OPA 更强 (元模型约束派生).

---

## 维护

- **审阅频率**: radar 每日检 drift, gc 每周清死规则
- **变更流程**: brainstorm → draft → bet → ADR → 更新本文件
- **失效条件**: 本文件过时 = GaC 走偏的第一信号 (X2 告警)

---

*北极星 v1.0 · 2026-06-26 · ADR-0106 · GaC 防走偏锚定*
