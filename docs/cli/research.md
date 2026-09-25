---
status: active
lifecycle: generated
owner: governance-team
last-reviewed: 2026-09-24
type: derived
source: bin/ssot/gen-help-docs.py
---

# Cockpit CLI · 📚 研究 (Research)

> 自动生成于 1970-01-01T00:00:00Z | 分册源自 [docs/CLI-REFERENCE.md](../CLI-REFERENCE.md)
> 生成器: `bin/ssot/gen-help-docs.py` | 请勿手动编辑

本册收录 **8** 个命令。索引与交叉表见 [docs/CLI-REFERENCE.md](../CLI-REFERENCE.md)。

## `cockpit brief`

会话简报 (生成摘要)

**用法**:

```bash
cockpit brief [flags]
cockpit brief --json          # 机器可读输出
cockpit brief --dry-run       # 预检 (无副作用)
cockpit brief --help          # 完整参数面
```

  · 所属域: `scene`  |  成熟度: stable  |  风险: low


## `cockpit daily`

每日研究简报 (生成 + 推送)

**用法**:

```bash
cockpit daily [flags]
cockpit daily --json          # 机器可读输出
cockpit daily --dry-run       # 预检 (无副作用)
cockpit daily --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit discover`

发现可用功能和资源

**用法**:

```bash
cockpit discover [flags]
cockpit discover --json          # 机器可读输出
cockpit discover --dry-run       # 预检 (无副作用)
cockpit discover --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit knowledge`

本地知识库管理 (import / query / stats)

**用法**:

```bash
cockpit knowledge [flags]
cockpit knowledge --json          # 机器可读输出
cockpit knowledge --dry-run       # 预检 (无副作用)
cockpit knowledge --help          # 完整参数面
```

  · 所属域: `memory`  |  成熟度: stable  |  风险: low


## `cockpit memory`

Memory OS 统一控制面 (status/recall/write/forget → bos://memory/mos/*)

**用法**:

```bash
cockpit memory [flags]
cockpit memory --json          # 机器可读输出
cockpit memory --dry-run       # 预检 (无副作用)
cockpit memory --help          # 完整参数面
```

  · 所属域: `🧠 记忆与认知 (Memory OS, Knowledge Graph, Search, Brain)`  |  成熟度: stable  |  风险: low  |  别名: `mos`


## `cockpit memory-distill`

🧠 [DEPRECATED] 记忆蒸馏 ADR-0200 → KOS pipeline (gbrain + eidos)

**用法**:

```bash
cockpit memory-distill [flags]
cockpit memory-distill --json          # 机器可读输出
cockpit memory-distill --dry-run       # 预检 (无副作用)
cockpit memory-distill --help          # 完整参数面
```

  · 成熟度: deprecated  |  风险: low

```bash
cockpit memory-distill
  # → 提示: 改用: cockpit kairon --distill + cockpit gbrain --digest
```


## `cockpit research`

深度研究工作台 (ask / publish / list / audit / …)

**用法**:

```bash
cockpit research [flags]
cockpit research --json          # 机器可读输出
cockpit research --dry-run       # 预检 (无副作用)
cockpit research --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit search`

跨源搜索 (数据库 + BOS 知识引擎)

**用法**:

```bash
cockpit search [flags]
cockpit search --json          # 机器可读输出
cockpit search --dry-run       # 预检 (无副作用)
cockpit search --help          # 完整参数面
```

  · 所属域: `memory`  |  成熟度: stable  |  风险: low


---

*由 `bin/ssot/gen-help-docs.py` 于 1970-01-01T00:00:00Z 生成*