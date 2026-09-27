---
status: active
lifecycle: generated
owner: governance-team
last-reviewed: 2026-09-24
type: derived
source: bin/ssot/gen-help-docs.py
---

# Cockpit CLI · 🛠️ 系统 (System)

> 自动生成于 1970-01-01T00:00:00Z | 分册源自 [docs/CLI-REFERENCE.md](../CLI-REFERENCE.md)
> 生成器: `bin/ssot/gen-help-docs.py` | 请勿手动编辑

本册收录 **15** 个命令。索引与交叉表见 [docs/CLI-REFERENCE.md](../CLI-REFERENCE.md)。

## `cockpit agent-runtime`

Agent 运行时生命周期管理

**用法**:

```bash
cockpit agent-runtime [flags]
cockpit agent-runtime --json          # 机器可读输出
cockpit agent-runtime --dry-run       # 预检 (无副作用)
cockpit agent-runtime --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit audit`

🔍 6 维度全方位审计

**用法**:

```bash
cockpit audit [flags]
cockpit audit --json          # 机器可读输出
cockpit audit --dry-run       # 预检 (无副作用)
cockpit audit --help          # 完整参数面
```

  · 所属域: `governance`  |  成熟度: stable  |  风险: low


## `cockpit capabilities`

统一能力发现入口 — 搜索/推荐/全量列出 (CLI+BOS+Scene+Journey)

**用法**:

```bash
cockpit capabilities [flags]
cockpit capabilities --json          # 机器可读输出
cockpit capabilities --dry-run       # 预检 (无副作用)
cockpit capabilities --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit gac`

GaC 治理健康检查 (ADR-0106, 7 机制 + 115 规则 + drift)

**用法**:

```bash
cockpit gac [flags]
cockpit gac --json          # 机器可读输出
cockpit gac --dry-run       # 预检 (无副作用)
cockpit gac --help          # 完整参数面
```

  · 所属域: `governance`  |  成熟度: stable  |  风险: low


## `cockpit health`

一键系统健康检查 (7 维度)

**用法**:

```bash
cockpit health [flags]
cockpit health --json          # 机器可读输出
cockpit health --dry-run       # 预检 (无副作用)
cockpit health --help          # 完整参数面
```

  · 所属域: `system`  |  成熟度: stable  |  风险: low


## `cockpit journey`

Journey State Graph 状态表达校验器

**用法**:

```bash
cockpit journey [flags]
cockpit journey --json          # 机器可读输出
cockpit journey --dry-run       # 预检 (无副作用)
cockpit journey --help          # 完整参数面
```

  · 所属域: `scene`  |  成熟度: stable  |  风险: low


## `cockpit monitor`

实时监控 (进程 / 资源 / 指标)

**用法**:

```bash
cockpit monitor [flags]
cockpit monitor --json          # 机器可读输出
cockpit monitor --dry-run       # 预检 (无副作用)
cockpit monitor --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit panorama`

7 维全景终极可观测仪表盘 (执行/服务/内容/知识/数据/异常/债务)

**用法**:

```bash
cockpit panorama [flags]
cockpit panorama --json          # 机器可读输出
cockpit panorama --dry-run       # 预检 (无副作用)
cockpit panorama --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit product-health`

产品健康度检测

**用法**:

```bash
cockpit product-health [flags]
cockpit product-health --json          # 机器可读输出
cockpit product-health --dry-run       # 预检 (无副作用)
cockpit product-health --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit project`

16 项目全景 4D 体检与诊断

**用法**:

```bash
cockpit project [flags]
cockpit project --json          # 机器可读输出
cockpit project --dry-run       # 预检 (无副作用)
cockpit project --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit proxy-env`

输出兼容外部客户端的本地环境变量 (OPENAI_API_BASE)

**用法**:

```bash
cockpit proxy-env [flags]
cockpit proxy-env --json          # 机器可读输出
cockpit proxy-env --dry-run       # 预检 (无副作用)
cockpit proxy-env --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit runtime`

运行时环境管理

**用法**:

```bash
cockpit runtime [flags]
cockpit runtime --json          # 机器可读输出
cockpit runtime --dry-run       # 预检 (无副作用)
cockpit runtime --help          # 完整参数面
```

  · 所属域: `system`  |  成熟度: stable  |  风险: low


## `cockpit status`

系统健康仪表盘 (Phase / CARDS / 研究工作台)

**用法**:

```bash
cockpit status [flags]
cockpit status --json          # 机器可读输出
cockpit status --dry-run       # 预检 (无副作用)
cockpit status --help          # 完整参数面
```

  · 所属域: `system`  |  成熟度: stable  |  风险: low


## `cockpit tui`

极客终端交互控制台 (Textual 全屏 TUI · Vim 键盘流)

**用法**:

```bash
cockpit tui [flags]
cockpit tui --json          # 机器可读输出
cockpit tui --dry-run       # 预检 (无副作用)
cockpit tui --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit version`

版本信息

**用法**:

```bash
cockpit version [flags]
cockpit version --json          # 机器可读输出
cockpit version --dry-run       # 预检 (无副作用)
cockpit version --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


---

*由 `bin/ssot/gen-help-docs.py` 于 1970-01-01T00:00:00Z 生成*