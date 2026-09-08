---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-09-04
---

# Cockpit CLI 命令参考

> 自动生成于 1970-01-01T00:00:00Z | 源: cockpit.commands.registry (SSOT) + capability-registry.yaml
> 生成器: `bin/ssot/gen-help-docs.py` | 请勿手动编辑

共 **0** 个命令条目。八大正交域: 。

## 目录

- [遗留命令映射](#遗留命令映射) (0 个)
- [全局 Flags](#全局-flags)
- [MCP 工具映射](#mcp-工具映射)

---

## 遗留命令映射

| 命令 | 域 | 目标 |
|------|-----|------|

## 全局 Flags

所有命令共享的全局参数面:

| Flag | 说明 |
|------|------|
| `--help` / `-h` | 命令帮助 |
| `--version` / `-V` | 版本号 |
| `--json` | 机器可读 JSON 输出 |
| `--dry-run` | 预检模式 (不执行副作用) |
| `--quiet` / `-q` | 静默模式 |
| `--verbose` / `-v` | 详细输出 |
| `--output` / `-o` | 输出文件路径 |
| `--trace-id` | 链路追踪 ID (跨命令 trace 贯穿) |

## Shell 自动补全

```bash
source <(cockpit completion bash)   # Bash
source <(cockpit completion zsh)    # Zsh
cockpit completion fish | source    # Fish
```

输错命令时会给出 Levenshtein 最近邻建议 (`Did you mean ...`)。

## MCP 工具映射

| CLI 命令 | MCP 服务器 | 工具数 |
|----------|-----------|--------|
| `cockpit omo` | `omo` | 22 |
| `cockpit kairon` | `kos/iris/sophia/kronos/minerva/codeanalyze/forge/ontoderive` | 123 |
| `cockpit gbrain` | `gbrain` | 75 |
| `cockpit model-driven` | `model-driven` | 28 |
| `cockpit agora` | `agora` | 110 |
| `cockpit family-hub` | `family-hub` | 0 |
| `cockpit mesh` | `aetherforge` | 0 |
| `cockpit compute` | `aetherforge` | 0 |

*由 `bin/ssot/gen-help-docs.py` 于 1970-01-01T00:00:00Z 生成 (T8-16 全量模式)*