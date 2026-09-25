---
schema: md/v1
status: active
lifecycle: generated
owner: governance-team
last-reviewed: 2026-09-25
type: derived
source: bin/ssot/gen-help-docs.py
---


# Cockpit CLI · 🖥️ 基础设施 (Infra)

> 自动生成于 1970-01-01T00:00:00Z | 分册源自 [docs/CLI-REFERENCE.md](../CLI-REFERENCE.md)
> 生成器: `bin/ssot/gen-help-docs.py` | 请勿手动编辑

本册收录 **11** 个命令。索引与交叉表见 [docs/CLI-REFERENCE.md](../CLI-REFERENCE.md)。

## `cockpit chain`

多命令联动链路编排 (list/show/run/validate/init, YAML 声明式)

**用法**:

```bash
cockpit chain [flags]
cockpit chain --json          # 机器可读输出
cockpit chain --dry-run       # 预检 (无副作用)
cockpit chain --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit dashboard`

打开 Web Dashboard

**用法**:

```bash
cockpit dashboard [flags]
cockpit dashboard --json          # 机器可读输出
cockpit dashboard --dry-run       # 预检 (无副作用)
cockpit dashboard --help          # 完整参数面
```

  · 所属域: `system`  |  成熟度: stable  |  风险: low


## `cockpit fabric`

🧑‍💻 主权混合算力与 KV 缓存快照 (ADR-0197)

**用法**:

```bash
cockpit fabric [flags]
cockpit fabric --json          # 机器可读输出
cockpit fabric --dry-run       # 预检 (无副作用)
cockpit fabric --help          # 完整参数面
```

  · 所属域: `compute`  |  成熟度: stable  |  风险: low


## `cockpit fabric-mesh`

🕸️ [DEPRECATED] 算力网格检视 ADR-0202 → omlxc-compute-fabric skill

**用法**:

```bash
cockpit fabric-mesh [flags]
cockpit fabric-mesh --json          # 机器可读输出
cockpit fabric-mesh --dry-run       # 预检 (无副作用)
cockpit fabric-mesh --help          # 完整参数面
```

  · 成熟度: deprecated  |  风险: low

```bash
cockpit fabric-mesh
  # → 提示: 改用 skill: omlxc-compute-fabric (本地大模型推理 + 算力调度)
```


## `cockpit mesh`

omlx 算力网格路由入口 (nodes / route / serve)

**用法**:

```bash
cockpit mesh [flags]
cockpit mesh --json          # 机器可读输出
cockpit mesh --dry-run       # 预检 (无副作用)
cockpit mesh --help          # 完整参数面
```

  · 所属域: `compute`  |  成熟度: stable  |  风险: low


## `cockpit model-driven`

[DEPRECATED] 模型驱动生命周期入口 (ADR-0240 D1) — 拒绝执行

**用法**:

```bash
cockpit model-driven [flags]
cockpit model-driven --json          # 机器可读输出
cockpit model-driven --dry-run       # 预检 (无副作用)
cockpit model-driven --help          # 完整参数面
```

  · 成熟度: deprecated  |  风险: low


## `cockpit mof`

MOF 元模型操作 (委派 mof CLI)

**用法**:

```bash
cockpit mof [flags]
cockpit mof --json          # 机器可读输出
cockpit mof --dry-run       # 预检 (无副作用)
cockpit mof --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit observe`

可观测性栈（Langfuse）入口 (up / down / logs)

**用法**:

```bash
cockpit observe [flags]
cockpit observe --json          # 机器可读输出
cockpit observe --dry-run       # 预检 (无副作用)
cockpit observe --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit ops`

🔧 Service Gateway — 统一运维控制面

**用法**:

```bash
cockpit ops [flags]
cockpit ops --json          # 机器可读输出
cockpit ops --dry-run       # 预检 (无副作用)
cockpit ops --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit telemetry`

命令全生命周期可观测性与 Prometheus 指标导出

**用法**:

```bash
cockpit telemetry [flags]
cockpit telemetry --json          # 机器可读输出
cockpit telemetry --dry-run       # 预检 (无副作用)
cockpit telemetry --help          # 完整参数面
```

  · 所属域: `system`  |  成熟度: stable  |  风险: low


## `cockpit watchdog`

🐕 [DEPRECATED] 自治守护犬已退役 → Mesh-bound capability admission (Cockpit PR #78)

**用法**:

```bash
cockpit watchdog [flags]
cockpit watchdog --json          # 机器可读输出
cockpit watchdog --dry-run       # 预检 (无副作用)
cockpit watchdog --help          # 完整参数面
```

  · 所属域: `governance`  |  成熟度: deprecated  |  风险: low

```bash
cockpit watchdog --help
  # → 提示: 守护犬已退役, 请用 mesh capability admission (cockpit mesh fabric)
```


---

*由 `bin/ssot/gen-help-docs.py` 于 1970-01-01T00:00:00Z 生成*