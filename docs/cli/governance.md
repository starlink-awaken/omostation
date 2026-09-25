---
schema: md/v1
status: active
lifecycle: generated
owner: governance-team
last-reviewed: 2026-09-25
type: derived
source: bin/ssot/gen-help-docs.py
---


# Cockpit CLI · 🏛️ 治理 (Governance)

> 自动生成于 1970-01-01T00:00:00Z | 分册源自 [docs/CLI-REFERENCE.md](../CLI-REFERENCE.md)
> 生成器: `bin/ssot/gen-help-docs.py` | 请勿手动编辑

本册收录 **16** 个命令。索引与交叉表见 [docs/CLI-REFERENCE.md](../CLI-REFERENCE.md)。

## `cockpit audit-ledger`

📒 [DEPRECATED] 治理审计账本 ADR-0201 → 查询 .omo/_knowledge/decisions/ + cockpit command-audit

**用法**:

```bash
cockpit audit-ledger [flags]
cockpit audit-ledger --json          # 机器可读输出
cockpit audit-ledger --dry-run       # 预检 (无副作用)
cockpit audit-ledger --help          # 完整参数面
```

  · 成熟度: deprecated  |  风险: low

```bash
cockpit audit-ledger
  # → 提示: 决策查询改用: ls .omo/_knowledge/decisions/ | grep ADR-0201
```


## `cockpit bdsk`

B.D.S.K. 虚拟董事会 (4角对抗辩论与 0-Touch 影子预演)

**用法**:

```bash
cockpit bdsk [flags]
cockpit bdsk --json          # 机器可读输出
cockpit bdsk --dry-run       # 预检 (无副作用)
cockpit bdsk --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit cards`

CARDS 卡片状态管理 (list / get / search / serve)

**用法**:

```bash
cockpit cards [flags]
cockpit cards --json          # 机器可读输出
cockpit cards --dry-run       # 预检 (无副作用)
cockpit cards --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit command-audit`

15 维命令评分卡管理 (init/validate/report/lint)

**用法**:

```bash
cockpit command-audit [flags]
cockpit command-audit --json          # 机器可读输出
cockpit command-audit --dry-run       # 预检 (无副作用)
cockpit command-audit --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit context`

显示系统上下文 (Phase / CARDS / 约束 / 引导)

**用法**:

```bash
cockpit context [flags]
cockpit context --json          # 机器可读输出
cockpit context --dry-run       # 预检 (无副作用)
cockpit context --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit controller-shadow`

读取 Runtime 旧控制器影子迁移回执

**用法**:

```bash
cockpit controller-shadow [flags]
cockpit controller-shadow --json          # 机器可读输出
cockpit controller-shadow --dry-run       # 预检 (无副作用)
cockpit controller-shadow --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit dlp-guard`

外发前防泄密扫描 (敏感识别+挂起+脱敏)

**用法**:

```bash
cockpit dlp-guard [flags]
cockpit dlp-guard --json          # 机器可读输出
cockpit dlp-guard --dry-run       # 预检 (无副作用)
cockpit dlp-guard --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit domain-status`

显示 Documents 域项目绑定与引导状态

**用法**:

```bash
cockpit domain-status [flags]
cockpit domain-status --json          # 机器可读输出
cockpit domain-status --dry-run       # 预检 (无副作用)
cockpit domain-status --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit facts-audit`

审计 Documents 文档域 facts 文件

**用法**:

```bash
cockpit facts-audit [flags]
cockpit facts-audit --json          # 机器可读输出
cockpit facts-audit --dry-run       # 预检 (无副作用)
cockpit facts-audit --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit facts-validation`

读取 Runtime Facts 审计回执

**用法**:

```bash
cockpit facts-validation [flags]
cockpit facts-validation --json          # 机器可读输出
cockpit facts-validation --dry-run       # 预检 (无副作用)
cockpit facts-validation --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit governance`

架构治理 (委派 arcnode-*)

**用法**:

```bash
cockpit governance [flags]
cockpit governance --json          # 机器可读输出
cockpit governance --dry-run       # 预检 (无副作用)
cockpit governance --help          # 完整参数面
```

  · 所属域: `🏛️ 架构与治理 (Governance, Contracts, GAC, Audits)`  |  成熟度: stable  |  风险: low


## `cockpit harness`

Harness 全生命周期合规 (trace/verify/gac/compliance/…)

**用法**:

```bash
cockpit harness [flags]
cockpit harness --json          # 机器可读输出
cockpit harness --dry-run       # 预检 (无副作用)
cockpit harness --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit mcp`

启动 MCP server 或列出工具

**用法**:

```bash
cockpit mcp [flags]
cockpit mcp --json          # 机器可读输出
cockpit mcp --dry-run       # 预检 (无副作用)
cockpit mcp --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit model-freshness`

读取 Runtime 模型新鲜度回执

**用法**:

```bash
cockpit model-freshness [flags]
cockpit model-freshness --json          # 机器可读输出
cockpit model-freshness --dry-run       # 预检 (无副作用)
cockpit model-freshness --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit policy`

⚖️ 领域监管合规与 Policy-as-Code 红线审查 (E-POL-*)

**用法**:

```bash
cockpit policy [flags]
cockpit policy --json          # 机器可读输出
cockpit policy --dry-run       # 预检 (无副作用)
cockpit policy --help          # 完整参数面
```

  · 所属域: `governance`  |  成熟度: stable  |  风险: low  |  委派目标: `ecos.cli.constraint policy`


## `cockpit sanyi-status`

读取 Runtime 三医状态一致性回执

**用法**:

```bash
cockpit sanyi-status [flags]
cockpit sanyi-status --json          # 机器可读输出
cockpit sanyi-status --dry-run       # 预检 (无副作用)
cockpit sanyi-status --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


---

*由 `bin/ssot/gen-help-docs.py` 于 1970-01-01T00:00:00Z 生成*