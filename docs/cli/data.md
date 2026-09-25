---
schema: md/v1
status: active
lifecycle: generated
owner: governance-team
last-reviewed: 2026-09-25
type: derived
source: bin/ssot/gen-help-docs.py
---


# Cockpit CLI · 📦 数据 (Data)

> 自动生成于 1970-01-01T00:00:00Z | 分册源自 [docs/CLI-REFERENCE.md](../CLI-REFERENCE.md)
> 生成器: `bin/ssot/gen-help-docs.py` | 请勿手动编辑

本册收录 **3** 个命令。索引与交叉表见 [docs/CLI-REFERENCE.md](../CLI-REFERENCE.md)。

## `cockpit contracts`

契约验证 (validate / list / export)

**用法**:

```bash
cockpit contracts [flags]
cockpit contracts --json          # 机器可读输出
cockpit contracts --dry-run       # 预检 (无副作用)
cockpit contracts --help          # 完整参数面
```

  · 所属域: `governance`  |  成熟度: stable  |  风险: low


## `cockpit data`

数据目录索引 / 类型注册 / TTL 清理

**用法**:

```bash
cockpit data [flags]
cockpit data --json          # 机器可读输出
cockpit data --dry-run       # 预检 (无副作用)
cockpit data --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit import`

导入外部内容 (Markdown / URL / 文件)

**用法**:

```bash
cockpit import [flags]
cockpit import --json          # 机器可读输出
cockpit import --dry-run       # 预检 (无副作用)
cockpit import --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


---

*由 `bin/ssot/gen-help-docs.py` 于 1970-01-01T00:00:00Z 生成*