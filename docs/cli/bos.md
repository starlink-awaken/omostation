---
status: active
lifecycle: generated
owner: governance-team
last-reviewed: 2026-09-24
type: derived
source: bin/ssot/gen-help-docs.py
---

# Cockpit CLI · 🧠 知识引擎 (BOS)

> 自动生成于 1970-01-01T00:00:00Z | 分册源自 [docs/CLI-REFERENCE.md](../CLI-REFERENCE.md)
> 生成器: `bin/ssot/gen-help-docs.py` | 请勿手动编辑

本册收录 **10** 个命令。索引与交叉表见 [docs/CLI-REFERENCE.md](../CLI-REFERENCE.md)。

## `cockpit ask`

快速大模型对话问答 (AetherForge)

**用法**:

```bash
cockpit ask [flags]
cockpit ask --json          # 机器可读输出
cockpit ask --dry-run       # 预检 (无副作用)
cockpit ask --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit bos`

BOS URI 查询与管理 (list / resolve / read / inbox / …)

**用法**:

```bash
cockpit bos [flags]
cockpit bos --json          # 机器可读输出
cockpit bos --dry-run       # 预检 (无副作用)
cockpit bos --help          # 完整参数面
```

  · 所属域: `bus`  |  成熟度: stable  |  风险: low


## `cockpit bos-capability`

BOS capability 域 / toolbox 外部能力 (list / invoke)

**用法**:

```bash
cockpit bos-capability [flags]
cockpit bos-capability --json          # 机器可读输出
cockpit bos-capability --dry-run       # 预检 (无副作用)
cockpit bos-capability --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit bos-inbox`

BOS Inbox 多源私有知识神经网查询与操作

**用法**:

```bash
cockpit bos-inbox [flags]
cockpit bos-inbox --json          # 机器可读输出
cockpit bos-inbox --dry-run       # 预检 (无副作用)
cockpit bos-inbox --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit brain`

个人数字大脑 (ask / remember / history / context)

**用法**:

```bash
cockpit brain [flags]
cockpit brain --json          # 机器可读输出
cockpit brain --dry-run       # 预检 (无副作用)
cockpit brain --help          # 完整参数面
```

  · 所属域: `memory`  |  成熟度: stable  |  风险: low


## `cockpit domains`

列出 L4 所有域及其状态

**用法**:

```bash
cockpit domains [flags]
cockpit domains --json          # 机器可读输出
cockpit domains --dry-run       # 预检 (无副作用)
cockpit domains --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit gbrain`

Postgres-native 知识库 (search / import / stats)

**用法**:

```bash
cockpit gbrain [flags]
cockpit gbrain --json          # 机器可读输出
cockpit gbrain --dry-run       # 预检 (无副作用)
cockpit gbrain --help          # 完整参数面
```

  · 所属域: `memory`  |  成熟度: stable  |  风险: low


## `cockpit kairon`

kairon 知识引擎 monorepo 聚合入口

**用法**:

```bash
cockpit kairon [flags]
cockpit kairon --json          # 机器可读输出
cockpit kairon --dry-run       # 预检 (无副作用)
cockpit kairon --help          # 完整参数面
```

  · 所属域: `memory`  |  成熟度: stable  |  风险: low


## `cockpit skill`

运行 L4 定时技能

**用法**:

```bash
cockpit skill [flags]
cockpit skill --json          # 机器可读输出
cockpit skill --dry-run       # 预检 (无副作用)
cockpit skill --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit vault`

搜索 L4 Vault 知识库

**用法**:

```bash
cockpit vault [flags]
cockpit vault --json          # 机器可读输出
cockpit vault --dry-run       # 预检 (无副作用)
cockpit vault --help          # 完整参数面
```

  · 所属域: `memory`  |  成熟度: stable  |  风险: low


---

*由 `bin/ssot/gen-help-docs.py` 于 1970-01-01T00:00:00Z 生成*