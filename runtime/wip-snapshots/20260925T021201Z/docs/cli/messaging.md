---
status: active
lifecycle: generated
owner: governance-team
last-reviewed: 2026-09-24
type: derived
source: bin/ssot/gen-help-docs.py
---

# Cockpit CLI · 📡 通讯 (Messaging)

> 自动生成于 1970-01-01T00:00:00Z | 分册源自 [docs/CLI-REFERENCE.md](../CLI-REFERENCE.md)
> 生成器: `bin/ssot/gen-help-docs.py` | 请勿手动编辑

本册收录 **5** 个命令。索引与交叉表见 [docs/CLI-REFERENCE.md](../CLI-REFERENCE.md)。

## `cockpit agora`

Agora BOS 网关入口 (委派 agora CLI)

**用法**:

```bash
cockpit agora [flags]
cockpit agora --json          # 机器可读输出
cockpit agora --dry-run       # 预检 (无副作用)
cockpit agora --help          # 完整参数面
```

  · 所属域: `bus`  |  成熟度: stable  |  风险: low


## `cockpit bus`

Omni-Bus 三平面入口 (status / topics / publish)

**用法**:

```bash
cockpit bus [flags]
cockpit bus --json          # 机器可读输出
cockpit bus --dry-run       # 预检 (无副作用)
cockpit bus --help          # 完整参数面
```

  · 所属域: `🌐 总线与通信 (Omni-Bus, Agora, BOS Services, Events)`  |  成熟度: stable  |  风险: low


## `cockpit events`

实时查看 Agora SSE 事件流 (Phase 34 L3 Dashboard)

**用法**:

```bash
cockpit events [flags]
cockpit events --json          # 机器可读输出
cockpit events --dry-run       # 预检 (无副作用)
cockpit events --help          # 完整参数面
```

  · 所属域: `bus`  |  成熟度: stable  |  风险: low


## `cockpit events-watch`

监听 BOS Inbox 紧急待办与提醒快照

**用法**:

```bash
cockpit events-watch [flags]
cockpit events-watch --json          # 机器可读输出
cockpit events-watch --dry-run       # 预检 (无副作用)
cockpit events-watch --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit ssb`

[DEPRECATED] SSB 签名链操作 — ECOS SSB 独立 CLI 已弃用，请使用 cockpit 替代

**用法**:

```bash
cockpit ssb [flags]
cockpit ssb --json          # 机器可读输出
cockpit ssb --dry-run       # 预检 (无副作用)
cockpit ssb --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


---

*由 `bin/ssot/gen-help-docs.py` 于 1970-01-01T00:00:00Z 生成*