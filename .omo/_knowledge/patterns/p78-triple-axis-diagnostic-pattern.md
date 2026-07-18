---
status: active
lifecycle: pattern
owner: governance-team
last-reviewed: 2026-07-17
related:
  - p73-truth-driven-engineering-pattern.md
  - p71-baseline-recovery-pattern.md
  - ../audits/2026-07-17-static-vs-runtime-diagnostic-audit.md
---

# P78 Triple-Axis Diagnostic Pattern — 声明/执行鸿沟系统的三维查证纪律

> **Generated**: 2026-07-17 (9 轮静态误判翻案后提炼)
> **SSOT**: 本轮实战 + memory `verify-claim-three-layers` + P73 D1 陷阱
> **Purpose**: 抽象"在声明/执行鸿沟频发的 eCOS 里做系统诊断"的纪律, 防"凭静态 grep 错判 / 不跑运行时实证 / 不读决策记录 / 缺自我对抗".
> **与 P73 关系**: P73 是补集 — P73 治"凭路径直觉判存在性"(D1), P78 治"用单维切片去诊三维系统". P73 是三维里的"静态层"深化, P78 把另外两维(运行时/决策)和"自我对抗"补齐.

## 1. 模式识别 (静态单维诊断的 4 类翻车)

| 陷阱 | 症状 | 本轮案例 (2026-07-17) |
|------|------|---------|
| **T1** 静态计数 ≠ 运行时 | grep 字符串数判断"覆盖面", 实际运行时动态加载 | `POC_SERVICES` grep=65 → 运行时 yaml 加载=154, evidence-smoke 早 gap=0 |
| **T2** 路径直觉判存在性 (承 P73 D1) | 报"module 悬空/零实现", 实际查的路径前缀错 | 6 条 aetherforge/bus-foundation "悬空" 全是验证脚本路径写错 |
| **T3** 看 ADR status 判落地 | ADR=proposed 判"未落地", 实际 broker 已实现 | ADR-0128 proposed → `omo_ingress_state.py` 已存在 |
| **T4** 单向依赖查耦合 | 只看 X→外, 漏 外→X | family_hub.db 只看 family-hub 内核, 漏 ecos+cockpit 4+处直读 |

## 2. 标准应对: 三维查证 + 自我对抗

### 纪律 1: 三维查证 (治 T1/T2/T3)

诊断"系统零实现 / 架构缺口 / 功能缺失 / 某机制未落地"前, **三维同查**, 缺一即误判:

1. **静态层** — grep / 路径 / import (必要不充分)
2. **运行时层** — 实测: `evidence-smoke` gap / CI 结果 / 文件存在性 / mtime 新鲜度 (**真相所在**)
3. **决策层** — ADR status + related + superseded / `bos-unimplemented.yaml` 登记 / roadmap / registry (**意图所在**)

工具速查:
- 运行时: `bin/gac/evidence-smoke.py --json` (BOS 鸿沟实测), `ls`/`stat` 验文件新鲜度 (mirror vs source mtime)
- 决策层: `rg -l <topic> .omo/_knowledge/decisions/`, 读 ADR 的 status/lifecycle/related/supersedes
- 静态: `rg` 宽泛 + Read 完整 (见 P73 纪律 1 的 5 位置查询法)

### 纪律 2: 双向依赖查耦合 (治 T4)

查"X 依赖谁" **同时**查"谁依赖 X":
- `rg "<X 的存储/schema/接口>" projects/ --include=*.py` (外→X 反向)
- 不只看 X 内核, 查 X 的 db/schema/文件被谁直读 (既成耦合常藏在此)

### 纪律 3: 主动写反证 (治确认偏误)

每个断言下结论前, 自问 **"我怎么知道自己错了"**, 主动找 ≥1 条反证.
**不等用户/外部当 RedTeam — 把对抗内置.** 本轮老王靠用户连追 5 轮才翻案, 是反面教材.

### 纪律 4: 方案设计前过覆盖度审计 (治重复造轮)

提"加机制 / 新方案 / 新 gate"前, 先:
- `ls bin/ssot/ .github/workflows/` (扫工具仓/gate 仓)
- 读相关 ADR (机制可能已有决策)
- 确认"缺的"真缺, 不是没扫到

本轮实证: 喊"缺 anti-drift 机制", 实际 **38 CI gate + 60 ssot 工具 + ADR 体系** 早建好, evidence-smoke gap=0.

## 3. 诊断前置 4 问 (已固化进 AGENTS.md §9)

报"系统问题/架构缺口"前, 过这 4 问:
1. 这个结论的**反证**找了吗? (确认偏误)
2. 查了**运行时实证**吗, 还是只 grep? (静态 ≠ 运行时)
3. 读了**相关 ADR/决策记录**吗? (意图层)
4. 扫了**工具仓/gate 仓**, 确认"缺的"真缺吗? (覆盖度)

## 4. 何时用

- 报"系统零实现 / 架构缺口 / 某功能缺失"前
- 系统性分析 / 方案设计任务 (尤其要先出方案时)
- 喊"缺机制 / 要新建 X" 前
- 多轮返工 / 判断错误发现时
- 任何"基于 grep/路径/ADR-status" 下结论的场景

## 5. 实证 (2026-07-17, 9 轮翻案链)

完整记录见 [audit](../audits/2026-07-17-static-vs-runtime-diagnostic-audit.md). 关键翻案:

| 断言 (静态) | 三维纠正 | 教训 |
|------|------|------|
| evidence-smoke "94 条无覆盖" (grep=65) | 运行时查全 154, gap=0 (ADR-0219 实测) | T1 |
| 6 条 module 悬空死罪 | 路径前缀错, aetherforge/bus-foundation 全存在 | T2 |
| ADR-0128 未落地 (proposed) | `omo_ingress_state.py` 已实现 | T3 |
| family-hub 独立违规 | ecos+cockpit 既成耦合, schema 稳定无痛点 → YAGNI | T4 |
| 缺 anti-drift 机制 | 38 gate + 60 工具已建 | 纪律 4 |

**收敛结论**: 9 轮后真正"要做"的接近零 (仅 registry service_count 可选小活), 系统治理健康度远超静态初判. 最理想方案常是"少做" — 能发现"自己开的药是多余的"比"开更多药"更专业.
