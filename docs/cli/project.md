---
status: active
lifecycle: generated
owner: governance-team
last-reviewed: 2026-09-24
type: derived
source: bin/ssot/gen-help-docs.py
---

# Cockpit CLI · 📋 项目 (Project)

> 自动生成于 1970-01-01T00:00:00Z | 分册源自 [docs/CLI-REFERENCE.md](../CLI-REFERENCE.md)
> 生成器: `bin/ssot/gen-help-docs.py` | 请勿手动编辑

本册收录 **12** 个命令。索引与交叉表见 [docs/CLI-REFERENCE.md](../CLI-REFERENCE.md)。

## `cockpit agent`

Agent 工作流编排（agent-workflow 别名）

**用法**:

```bash
cockpit agent [flags]
cockpit agent --json          # 机器可读输出
cockpit agent --dry-run       # 预检 (无副作用)
cockpit agent --help          # 完整参数面
```

  · 所属域: `workflow`  |  成熟度: stable  |  风险: low


## `cockpit agent-workflow`

Agent 工作流编排

**用法**:

```bash
cockpit agent-workflow [flags]
cockpit agent-workflow --json          # 机器可读输出
cockpit agent-workflow --dry-run       # 预检 (无副作用)
cockpit agent-workflow --help          # 完整参数面
```

  · 所属域: `workflow`  |  成熟度: stable  |  风险: low  |  别名: `agent`


## `cockpit bcos`

BCOS 业务域系统 (evolve/signals/north-star)

**用法**:

```bash
cockpit bcos [flags]
cockpit bcos --json          # 机器可读输出
cockpit bcos --dry-run       # 预检 (无副作用)
cockpit bcos --help          # 完整参数面
```

  · 所属域: `workflow`  |  成熟度: stable  |  风险: low  |  委派目标: `bin/bc-os/*.py`


## `cockpit c2g`

Concept-to-Governance 生命周期转化

**用法**:

```bash
cockpit c2g [flags]
cockpit c2g --json          # 机器可读输出
cockpit c2g --dry-run       # 预检 (无副作用)
cockpit c2g --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit compass`

战略罗盘 (OKR / 目标对齐)

**用法**:

```bash
cockpit compass [flags]
cockpit compass --json          # 机器可读输出
cockpit compass --dry-run       # 预检 (无副作用)
cockpit compass --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit debt`

技术债管理 (list / score / resolve)

**用法**:

```bash
cockpit debt [flags]
cockpit debt --json          # 机器可读输出
cockpit debt --dry-run       # 预检 (无副作用)
cockpit debt --help          # 完整参数面
```

  · 所属域: `governance`  |  成熟度: stable  |  风险: low


## `cockpit iterate`

迭代管理 (sprint / backlog / roadmap)

**用法**:

```bash
cockpit iterate [flags]
cockpit iterate --json          # 机器可读输出
cockpit iterate --dry-run       # 预检 (无副作用)
cockpit iterate --help          # 完整参数面
```

  · 所属域: `workflow`  |  成熟度: stable  |  风险: low


## `cockpit kems`

知识经济指标体系 (KEMS · KPI 追踪)

**用法**:

```bash
cockpit kems [flags]
cockpit kems --json          # 机器可读输出
cockpit kems --dry-run       # 预检 (无副作用)
cockpit kems --help          # 完整参数面
```

  · 所属域: `governance`  |  成熟度: stable  |  风险: low


## `cockpit readiness`

Readiness Dashboard (Phase / Gate / 核验)

**用法**:

```bash
cockpit readiness [flags]
cockpit readiness --json          # 机器可读输出
cockpit readiness --dry-run       # 预检 (无副作用)
cockpit readiness --help          # 完整参数面
```

  · 所属域: `system`  |  成熟度: stable  |  风险: low


## `cockpit scenario`

统一 scenario 入口 (radar / assistant / health)

**用法**:

```bash
cockpit scenario [flags]
cockpit scenario --json          # 机器可读输出
cockpit scenario --dry-run       # 预检 (无副作用)
cockpit scenario --help          # 完整参数面
```

  · 所属域: `scene`  |  成熟度: stable  |  风险: low


## `cockpit wave2`

Wave2 项目战略视图

**用法**:

```bash
cockpit wave2 [flags]
cockpit wave2 --json          # 机器可读输出
cockpit wave2 --dry-run       # 预检 (无副作用)
cockpit wave2 --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit workflow`

工作流管理 (run / list / status)

**用法**:

```bash
cockpit workflow [flags]
cockpit workflow --json          # 机器可读输出
cockpit workflow --dry-run       # 预检 (无副作用)
cockpit workflow --help          # 完整参数面
```

  · 所属域: `📋 智能体与交付 (Workflows, Agent Lifecycle, Residents, BCOS)`  |  成熟度: stable  |  风险: low


---

*由 `bin/ssot/gen-help-docs.py` 于 1970-01-01T00:00:00Z 生成*