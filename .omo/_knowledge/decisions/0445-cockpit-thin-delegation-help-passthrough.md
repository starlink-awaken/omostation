---
id: ADR-0445
status: accepted
lifecycle: spec
owner: xiamingxing
last-reviewed: 2026-09-01
type: ssot
---

# ADR-0445: cockpit 薄委派命令体系与 --help 透传

- **Status**: ACCEPTED
- **Date**: 2026-09-01
- **Authors**: xiamingxing, cockpit-cli-upgrade team
- **实现**: `projects/cockpit/src/cockpit/commands/delegation.py`
- **关联**: ADR-0122 (omo-debt 收编), ADR-0240 (model-driven 弃用)

## Context and Problem Statement

workspace 有 560 个活跃 bin/ 脚本与 24 个项目 CLI 入口，但 cockpit 仅委派约 10 个；
且 11 个存量 REMAINDER 委派命令（omo/runtime/agora/mof/policy 等）的壳 parser
默认 `add_help=True`，`--help` 被 argparse HelpAction 在子 parser 层拦截
（`sys.exit(0)`），用户永远只能看到壳的一句话提示，看不到下游 CLI 的真实
子命令列表 —— 可发现性的最大杀手。

## Decision

1. **薄委派模式**: 新命令纳入 cockpit 一律 REMAINDER 透传（零下游修改），
   `DelegatedSpec` 为唯一手写源，parser/handler/catalog 全部派生
   （`spec_to_meta`），杜绝双源漂移。
2. **--help 透传三件套**:
   - 壳 parser `add_help=False`（唯一能让 `--help` 到达 REMAINDER 的手段）
   - `reclaim_unknown_for_delegation`: argparse REMAINDER 不捕获前导 option
     （`cmd --help` 的 --help 落 unknown），对委派命令拼回 REMAINDER
   - `inject_empty_help`: 空参回退注入 `--help`（EMPTY_FALLBACK_OVERRIDES
     支持按命令覆盖，omo 顶层不支持 --help 则不注入）
3. **组模块自注册**: B 组（gac/adr/sweep/project_cli/root_bin）各建自己的
   模块暴露 `SPECS`/`register()`，`register_all` 聚合挂载 —— 并行实施零共享
   文件冲突。
4. 命令元数据治理字段（owner/maturity/risk/delegated_target/chain_enabled）
   随 CommandMeta 派生，high-risk 命令默认禁止进入 chain 编排。

## Consequences

- ✅ `cockpit policy --help` / `cockpit omo debt --help` 显示下游真实帮助
- ✅ 39 个新命令纳入（gac 8 + adr 8 + sweep 4 + 项目 CLI 7 + 根 bin 12），
  catalog 73→150+，help_map/产品地图自动同步（A3 SSOT 化）
- ⚠️ `-h` 不再显示壳帮助 —— 即期望行为；壳元信息走 `cockpit help <cmd>`
- ⚠️ 下游 CLI 自身不支持 --help 时（如 omo 顶层）透传后显示下游报错 ——
  这是下游原生行为的忠实呈现，修复责任在下游
