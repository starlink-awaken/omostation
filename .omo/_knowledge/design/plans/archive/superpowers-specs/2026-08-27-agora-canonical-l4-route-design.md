---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-27
last-reviewed: 2026-08-27
bet_id: BET-Y1Q3-T10-22
risk_level: L2
type: ssot
last_updated: 2026-09-03
---

# Agora canonical L4 route 设计

## 1. 目标

修复 Agora `mcp_bootstrap` 通过 `__file__.parents[4] / projects/l4-kernel` 推断 L4 路径的问题。Workspace 嵌套运行时必须解析主 Workspace 的 canonical `projects/l4-kernel`；standalone Agora 只有在显式允许时才使用 nested L4 fallback。

## 2. 规则

1. `OMOSTATION_WORKSPACE_ROOT` 是最高优先级的显式 Workspace 根；其下必须存在 `projects/l4-kernel`。
2. 若未设置显式根，则从源码祖先目录寻找同时包含 `.omo/_truth/registry/documents-domain-projects.yaml` 和 `projects/l4-kernel` 的 Workspace 根。
3. standalone Agora 可识别自身根下的 `projects/l4-kernel`，但结果必须标记 `legacy-nested`，不能伪装成 canonical。
4. 显式 `L4_KERNEL_ROOT` 只能是绝对目录；不存在或相对路径必须 fail closed。
5. L4 service metadata 必须暴露 `l4_route_mode` 与 `l4_kernel_root`，供 config、canary 和治理审计使用。
6. 本波次不删除 nested L4、不更新 root gitlink、不切换生产客户端或调度配置。

## 3. 数据流

```text
Agora mcp_bootstrap
  → resolve L4 root (explicit Workspace > SSOT ancestor > explicit legacy)
  → build stdio service argv
  → ProxyManager / BOS route
```

禁止通过 shell 拼接或隐式 `cwd` 选择 L4；argv 必须保持结构化，路径选择必须可测试、可审计。

## 4. 测试契约

- Workspace root precedence resolves to `<workspace>/projects/l4-kernel`.
- Invalid explicit `L4_KERNEL_ROOT` is rejected.
- Standalone root returns `legacy-nested` only when the nested path exists.
- A nested Agora checkout cannot accidentally resolve to `<workspace>/projects/projects/l4-kernel`.
- L4 service metadata preserves source and route mode.
- Existing mcp bootstrap tests remain green.

## 5. 后续门

Child PR 合并后，root wave must compare root and child gitlink, then run dual-instance route canary. Only after consumer zero, route uniqueness, registry digest equality and rollback proof may a separate wave remove `projects/agora/projects/l4-kernel`.
