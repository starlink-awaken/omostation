# Agent Mutation Protocol — 自治代理写入协议

> 适用范围: 所有在 workspace 中自动运行的 AI Agent / cron / daemon
> 确立时间: 2026-06-24
> 关联规则: direct-omo-io baseline, SSOT guardian, OMO event log

## 1. 核心原则

1. **NO RAW STATE MUTATION**: 不要绕过 broker 直接改写 `.omo/` 或 `spaces/`。
2. **USE BROKER**: 持久化写入必须优先走 `omo CLI` / `projects/omo` 内核 / `projects/c2g` 入口。
3. **COMMIT AFTER MUTATION**: 任何产生文件变更的自治运行，结束后必须立即 `git commit`。
4. **EMIT INTENT**: 批量/定时写入前必须 emit `agent_mutation_intent` 事件到 OMO event log。

## 2. 事件契约

每次自治 agent 启动一批可能修改 `.omo/` 或子模块的操作前，emit:

```bash
omo event emit \
  --type agent_mutation_intent \
  --source "<agent-name>" \
  --payload '{"planned_surfaces":[".omo/tasks",".omo/state"],"trigger":"cron|event|manual","run_id":"<uuid>"}'
```

完成后 emit:

```bash
omo event emit \
  --type agent_mutation_complete \
  --source "<agent-name>" \
  --payload '{"run_id":"<uuid>","committed":true,"commit_sha":"<sha>"}'
```

## 3. 子模块指针管理

- 子仓库内的修改先在子仓库内 commit。
- 根仓库指针必须随后更新并 commit。
- 不允许长时间持有 dirty 子模块 working tree。

## 4. 检测与门禁

- `python3 bin/ssot-guardian.py` 检测子模块漂移和 direct-omo-io 违规。
- pre-commit hook 运行 `ssot-guardian`。
- CI 运行 `omo lint direct-omo-io`。

## 5. 违规处理

- 发现 direct-omo-io: 立即修复，将写入迁入 OMO 内核。
- 发现未提交子模块漂移: agent 必须回退或完成 commit。
- 未 emit intent 的批量写入: 视为审计缺失，补录事件并记录 debt。
