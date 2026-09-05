---
id: ADR-0441
status: accepted
lifecycle: spec
owner: xiamingxing
last-reviewed: 2026-08-30
type: ssot
---

# ADR-0441: Documents↔Workspace 协同机制 v1（DW 三原语）

- **状态**: ACCEPTED（principal 授权 2026-08-30）
- **日期**: 2026-08-30
- **BOS**: `bos://documents/collab/*`
- **关联**: ADR-0385（双轨 admission）、ADR-0409（owner convergence）、ADR-0431（反腐蚀五层）

## Context

控制面下沉战役（#2596→#2711）把 Documents 的可执行资产收敛进 Workspace（27 个
quarantine 包，活跃执行面 forbidden_executors=0）。下沉之后的核心问题变为：
**内容面（Documents，人读）与控制面（Workspace，机执行）如何长期协同**。

本决策不发明新机制，把本仓已实战验证的三个模式契约化：

## Decision — 三原语

### 原语 1：执行转发 D→W — Bridge Shell

- Documents 侧保留**薄壳文件**：文件头带标记 `l4-content-plane: workspace-bridge`，
  ≤2KB，`os.execv` 转发到 registry 认证的 Workspace owner 绝对路径。
- **fail-loud**：转发目标缺失必须 SystemExit 报出目标路径，禁止静默降级或内联重实现。
- 治理：bridge 清单入 registry（family 新增 `bridge_shells` 字段）；L4 分类器识别
  标记自动归 bridge 类（豁免 runtime 搬迁）；薄壳目标可达性纳入周期审计。

### 原语 2：内容访问 W→D — Owner Job 受控访问

- 范式：`learning_decay` 模式 — **aggregate-only**（只统计不取内容）、read-only 或
  explicit_apply_only、不把 Documents 内容泄入 Workspace 日志/回执。
- 写 Documents 的 owner 必须走 content-plane migration 事务协议
  （preflight→receipt→dry-run→apply→postflight→rollback manifest）。
- 每个 owner 在 registry `consumer_refs` 登记访问面。

### 原语 3：边界仲裁 — 三件套

- **L4 分类器** = 分类唯一真值（content/runtime/cache/contract/projection/bridge）。
- **consumer audit** = 执行面监控（forbidden_executors 恒 0），由事务时手动跑升级为
  周期审计（挂接已有调度面，见 Open Questions）。
- **quarantine 协议** = Documents 文件移动的唯一协议；路由 `bos://documents/*`。

## 立即落地件（本 PR）

1. 契约标准：`.omo/standards/documents-workspace-collab-v1.md`
2. registry schema：`bridge_shells` 字段 + 首个实例（kems-materialize 薄壳入册）
3. L4 分类器 gap 修复（l4-kernel 子仓）：无扩展名 + shebang + 可执行位 → runtime
   （kems-mcp 残留案例，分类器未识别导致控制面漏下沉）

## Open Questions

- consumer audit 周期化的挂载点（crontab 属用户配置，不擅自变更；候选：既有
  `l4-governance-weekly` 面或 agent-workflows periodic 机制）
- bridge shell 的 sha 指纹周期核验自动化

## Consequences

- 控制面清零可持续：新漏网 runtime 由分类器+consumer audit 双网捕捉
- 内容面不动原则升级为契约：Documents 只减控制面，内容/契约/投影不动
- 协同 3 原语成为后续 BET 的标准验收面（T10-69 终局直接复用）
