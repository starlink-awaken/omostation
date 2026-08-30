# State Management Specification

> 最后更新: 2026-08-30
> 状态: active

## 1. 统一路径规范

所有 state file 必须使用以下路径：

```
.omo/state/<domain>/<name>.json
```

例如：
- `.omo/state/governance/orchestrator-state.json`
- `.omo/state/runtime/health.json`

禁止直接将 state file 放在 `.omo/state/*.json`。

## 2. 统一 Schema

所有 state file 必须包含以下字段：

```json
{
  "version": "1.0",
  "updated_at": "2026-08-30T00:00:00Z",
  "schema_version": "1.0",
  ...
}
```

## 3. 并发控制

写入 state file 前必须通过 `omo-mcp_acquire_lock` 获取锁。

## 4. 过期策略

超过 30 天未更新的 state file 自动归档至 `.omo/_archive/state/`。

## 5. 管理工具

所有 state file 的读写必须通过 `bin/ssot/state-manager.py` 进行，不允许直接 `json.dump` 或 `json.load`。
