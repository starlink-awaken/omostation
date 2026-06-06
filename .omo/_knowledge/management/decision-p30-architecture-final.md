# P30 架构最终决策 — v3.0 实施令

> 2026-06-06 | 决策者: 人类 + 老王架构联合
> 基于: architecture-final-state-v3.md + architecture-pure-analysis.md

## 一、5 大决策（已审批）

### 决策 1: kairon-governance → omo 合并 ✅
- 现状: kairon-governance v0.1.0 (88 测试, 6 模块)
- 目标: 功能迁 omo, 删独立包
- 理由: omo 已有 20+ 治理模块, 治理面唯一

### 决策 2: metaos 独立 ✅
- 现状: kairon/packages/metaos (6K, 自包含)
- 目标: projects/metaos/ 独立项目
- 理由: 编排引擎 ≠ 知识工程

### 决策 3: wksp → cockpit ✅
- 现状: kairon/packages/wksp (15K, 仅依赖 agora)
- 目标: projects/cockpit/{cli,web}
- 理由: 用户入口 = L3 层, 与 hermes-console 合并

### 决策 4: agora 物理独立延后 ⏸️
- 原因: 5 天高风险, 改 5 包接口 (import→MCP)
- 何时再做: P31 评估

### 决策 5: agent-runtime 拆分延后 ⏸️
- 原因: 22 测试在用, 拆破坏大
- 何时再做: P31 评估

## 二、P30 任务清单

| 任务 ID | 标题 | 估时 | 风险 |
|---|---|---|---|
| P30-W0-DECISION | 本文档（决策落定）| 0 | 0 |
| P30-W0-FOLD | 归档 P28/P29/IMPORTED 到 .omo/tasks/archived/ | 30min | 低 |
| P30-W0-PLAN-UPDATE | 更新 4 份 plan-phase*.md 反映 v3 决策 | 1h | 低 |
| P30-W0-DAEMON-INSTALL | 启动 omo daemon (launchd 开机自启) | 1h | 中 |
| P30-W1-METAOS-EXTRACT | metaos 独立出 kairon | 1天 | 低 |
| P30-W1-WKSP-EXTRACT | wksp 独立 + cockpit 建项目 + hermes 合并 | 1天 | 中 |
| P30-W1-GOV-MERGE | kairon-governance 6 模块功能迁 omo | 2天 | 中 |
| P30-W2-VERIFY | 全 6 项目 E2E 测试 + 健康分 | 1天 | 低 |

**总估时**: ~6 天

## 三、不做的事

- agora 物理独立 (P31)
- agent-runtime 拆分 (P31)
- shared-lib 解耦 (被 4 包引用, 闭环)
- eidos/kos 拆 L0+L2 (双向循环)
- minerva ↔ llm-gateway 拆 (双向循环)

## 四、执行顺序与依赖

```
P30-W0-DECISION (本决策)
    ↓
P30-W0-FOLD + P30-W0-PLAN-UPDATE (并行, 30min/1h)
    ↓
P30-W0-DAEMON-INSTALL (1h, 可与 W1 并行)
    ↓
P30-W1-METAOS-EXTRACT ─┐
P30-W1-WKSP-EXTRACT   ├─ 三项可并行, 风险递增
P30-W1-GOV-MERGE      ─┘
    ↓
P30-W2-VERIFY (6 项目 E2E)
```

## 五、退出标准

- [ ] kairon 23 包 → 20 包 (metaos/wksp/governance 移除)
- [ ] projects/ 5 → 6 (新增 metaos + cockpit)
- [ ] omo 治理模块从 17K → 20K
- [ ] `make kairon-test` 全绿
- [ ] 6 项目 health-check 全绿
- [ ] 治理历史 JSONL 写入 P30-W1-GOV-MERGE 完成事件

## 六、参考

- 终态视角: `architecture-final-state-v3.md`
- 纯分析: `architecture-pure-analysis.md`
- 旧版计划: `plan-phase30-architecture-maturity.md` (SUPERSEDED)
- INDEX: `.omo/INDEX.md`

---

*签发: 2026-06-06 · 维护人: omostation 首席架构师 + PM*
