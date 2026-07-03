---
status: proposed
lifecycle: architecture
owner: governance-team
last-reviewed: 2026-07-03
related:
  - ../patterns/p73-truth-driven-engineering-pattern.md
  - ../../.omo/standards/omo-governance-surfaces.md
  - ../../.omo/standards/agent-mutation-protocol.md
  - ../../.omo/standards/agent-workflow-contract.md
  - ../../bin/compass_radar.py
  - ../../bin/generate-brief.py
  - ../../scripts/sync_omo_state.py
  - ../../scripts/generate-governance-data.py
---

# ADR-0128: 多 Agent 并发下治理状态生成的架构收敛

## 1. 问题陈述

当前 workspace 中，多个 AI agent 并行工作时，`.omo/state/*.yaml`、`BRIEF.md`、`.omo/_control/governance-data.json` 等**运行时投影文件**被反复刷新，导致：

- 工作区持续处于 dirty 状态，子模块指针 PR 被生成物污染；
- agent 频繁需要 `git reset`/`git checkout` 清理，产生大量无意义操作；
- pre-commit / pre-push hook 因 SSOT 漂移或混合 lane 反复失败；
- 生成内容实际未变，但 mtime/哈希变化触发 git 状态波动。

本 ADR 旨在给出**治本级**架构设计，在保持现有 OMO/C2G/GaC 架构收敛的前提下，消除并发刷新冲突。

## 2. 现状根因分析

### 2.1 触发源

| 触发源 | 机制 | 问题 |
|---|---|---|
| `.githooks/post-commit` | 每次 commit 后 `nohup` 异步执行 `scripts/generate-governance-data.py` | 每 agent 每 commit 触发一次异步写；nohup 无法串行 |
| `bin/install-watch-agent.py` | launchd `WatchPaths` 监听 `.omo/_truth/registry` 和 `projects/ecos/src/ecos/ssot` | 文件系统事件风暴，registry 变化即触发 `compass_radar.py` |
| 各 agent/脚本 | 直接调用 `bin/compass_radar.py`、`bin/generate-brief.py`、`scripts/sync_omo_state.py` | 无统一入口、无锁、无事件去重 |

### 2.2 结构性问题

1. **推模式（Push）副作用不可重入**：commit 是高频操作，却被绑定到状态刷新。commit 应该是“业务动作结束”，而不是“生成动作开始”。
2. **运行时投影被当作源码 commit**：`.omo/state/health.yaml` 等文件的 `persistence_mode` 是 `runtime_ssot + operational + until_replaced`，却被纳入 git tracked 面，与源码同生命周期。
3. **写入未走 OMO broker**：`compass_radar.py`、`generate-brief.py` 等工具直接 `write_text`/`write_yaml_atomic`，未登记到 `.omo/_truth/registry/mutation-surfaces.yaml`，违反 `omo-governance-surfaces.md` 的 broker 原则。
4. **无进程级协调**：多个 agent 独立进程，无 `flock`、无事件总线、无单写者。
5. **子模块无退出清理协议**：agent 在子模块跑测试/uv 后产生 `uv.lock` 变更，不 commit 也不 reset，根仓库看到 dirty submodule。

## 3. 设计目标

1. **收敛到现有架构**：不新建独立系统，复用 `projects/omo` broker、`omo event emit`、`agent-workflow.py claim`、OMO mutation surface registry。
2. **读写分离**：把“状态投影的读”和“状态源的写”分开；投影按需/定时生成，不随每次 commit 推。
3. **单写者 + 去重**：同一时刻只有一个 writer；内容未变不写盘。
4. **子模块 clean exit**：agent 在子模块操作后必须完成 commit 或 reset。
5. **可审计**：所有状态刷新通过 `omo event emit` 留下 `agent_mutation_intent` / `agent_mutation_complete` 记录。

## 4. 方案对比

| 方案 | 描述 | 优点 | 缺点 | 是否符合收敛 |
|---|---|---|---|---|
| A. 内容指纹 | 写入前比较 hash，无变化不写 | 简单、立即生效 | 不解决并发写冲突 | 部分 |
| B. 文件锁 | `fcntl.flock` / `filelock` 保护写 | 防止并发覆盖 | 锁粒度粗，仍多触发 | 部分 |
| C. 关闭 post-commit，改 CI/cron | 移除 hook 副作用，定时刷新 | 彻底消除 commit 级风暴 | 实时性下降 | 是 |
| D. 单 state-sync agent + 事件总线 | 唯一 writer，其他 agent emit `state_stale` 事件 | 串行、可审计、可扩展 | 需要实现事件消费 | 是（推荐） |
| E. 运行时投影 gitignore | `.omo/state/` 等移出 tracked | 从源头消除 dirty | _dashboard/Brief 入口需调整 | 是（长期） |

**推荐组合：A + D + E 分阶段落地**，B 作为 D 的底层实现细节。

## 5. 推荐架构设计

### 5.1 总体结构

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent / Cron / CI                        │
│  (emit state_stale / claim surface / run sync command)       │
└───────────────────────┬─────────────────────────────────────┘
                        │ omo event emit
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              OMO Event Log (.omo/change-log/events.jsonl)   │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ state-sync   │ │ dashboard    │ │ ssot-guardian│
│ cron/agent   │ │ service      │ │ (drift check)│
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────┐
│              OMO Ingress Broker (projects/omo)               │
│   write_system_projection() / write_health_projection()      │
│   FileLock + content fingerprint + mutation ledger           │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│           Runtime Projection (gitignored or generated)       │
│   .omo/state/health.yaml                                     │
│   .omo/state/system.yaml                                     │
│   .omo/state/system_health.yaml                              │
│   .omo/_control/governance-data.json                         │
│   BRIEF.md (kept as rendered view, CI-generated)             │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 关键组件

#### 5.2.1 State Sync Broker (`projects/omo/src/omo/omo_ingress_state.py`)

新增一个 ingress 模块，作为**唯一被授权写 `.omo/state/` 的入口**。

职责：
- 接收 `state_sync_request`（来自事件总线或 CLI `omo state sync`）；
- 对写操作加 `FileLock`；
- 生成新内容后做 hash 比较，无变化则跳过写盘；
- 写盘时同步 append `mutation ledger`；
- 暴露 `omo state sync --dry-run` 供 agent 检查是否需要刷新。

登记到 `.omo/_truth/registry/mutation-surfaces.yaml`：

```yaml
- name: omo_state_projection
  path: projects/omo/src/omo/omo_ingress_state.py
  target_surface: .omo/state/
  allowed_actor:
    - state-sync-agent
    - ci-bot
```

#### 5.2.2 State Sync Agent / Cron

唯一定时运行的 writer，建议用 `bin/agent-workflow.py` 注册一个 workflow：

```yaml
workflows:
  state-sync:
    profile: state-syncer
    steps:
      - emit: agent_mutation_intent
      - run: omo state sync
      - run: generate-brief --if-changed
      - emit: agent_mutation_complete
```

调度：
- **本地开发**：每 5 分钟一次（launchd/cron），不阻塞 agent；
- **CI**：在 `gac-gate` 最后一步运行，保证 main 上的投影最新；
- **agent 手动触发**：当 agent 认为自己改动了影响 state 的源数据时，emit `state_stale` 事件，state-sync agent 在下一轮刷新。

#### 5.2.3 事件契约扩展

在现有 `agent_mutation_intent` / `agent_mutation_complete` 基础上新增：

```bash
# agent 发现状态可能过期时 emit
omo event emit \
  --type state_stale \
  --source "<agent-name>" \
  --payload '{"surfaces":[".omo/state/health.yaml"],"trigger":"task_closed","run_id":"<uuid>"}'

# state-sync agent 完成刷新后 emit
omo event emit \
  --type state_sync_complete \
  --source "state-sync-agent" \
  --payload '{"run_id":"<uuid>","files":["health.yaml"],"changed":true,"commit_sha":"<sha>"}'
```

#### 5.2.4 内容指纹写入

所有生成工具增加 `write_if_changed` 工具函数（可放到 `projects/omo/src/omo/utils/`）：

```python
def write_if_changed(path: Path, content: str | bytes) -> bool:
    if path.exists():
        old_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        new_hash = hashlib.sha256(content.encode() if isinstance(content, str) else content).hexdigest()
        if old_hash == new_hash:
            return False
    path.write_text(content) if isinstance(content, str) else path.write_bytes(content)
    return True
```

应用范围：`compass_radar.py`、`generate-brief.py`、`generate-governance-data.py`、`sync_omo_state.py`。

#### 5.2.5 移除 commit 级副作用

修改 `.githooks/post-commit`：

```bash
# 旧：每次 commit 异步生成
# nohup python3 "$ROOT/scripts/generate-governance-data.py" >/dev/null 2>&1 &

# 新：仅 emit lightweight stale 信号，不直接写盘
if command -v omo >/dev/null 2>&1; then
  omo event emit --type state_stale --source post-commit --payload '{}' >/dev/null 2>&1 || true
fi
```

同理，移除/改造 `bin/install-watch-agent.py` 的 `WatchPaths` 直接调用 `compass_radar.py`，改为 emit `state_stale`。

#### 5.2.6 子模块 Clean Exit 协议

新增 `bin/agent-workflow.py` 子命令或 hook：

```bash
# agent 退出子模块前运行
omo submodule cleanup <path>
```

行为：
- 若子模块有未 commit 变更且属于生成物（`uv.lock`、`_derivation_logs/`、`.omc/`），自动 reset；
- 若属于代码变更，提示 agent 必须 commit/push；
- 根仓库 pre-push hook 调用此检查，阻断 dirty submodule 的 root push。

## 6. 与现有架构的收敛点

| 现有机制 | 本设计如何使用 |
|---|---|
| `omo-governance-surfaces.md` | 把 `.omo/state/` 明确为 `runtime_ssot`，通过 broker 写入 |
| `agent-mutation-protocol.md` | state-sync agent emit intent/complete；其他 agent emit `state_stale` |
| `agent-workflow-contract.md` | 新增 `state-sync` workflow，`claim` 锁 `.omo/state/` surface |
| `omo event emit` | 作为去耦和审计总线，替代直接文件监听 |
| `ssot-guardian.py` | 检测未走 broker 的 direct-omo-io 和 dirty submodule |
| `mutation-surfaces.yaml` | 登记 `omo_state_projection` 入口 |
| `mutation ledger` | broker 写入时记录 `actor/action/target` |

## 7. 落地路线图

### Phase 1：止血（1-2 天）

1. 给 `compass_radar.py`、`generate-brief.py`、`generate-governance-data.py` 加 `write_if_changed`。
2. 关闭 `.githooks/post-commit` 的异步 nohup，改为 emit `state_stale`。
3. 新增 `omo state sync --dry-run` 模式。

### Phase 2：单写者（1 周）

1. 实现 `projects/omo/src/omo/omo_ingress_state.py` broker。
2. 改造 `scripts/sync_omo_state.py` 为 broker 的 CLI wrapper。
3. 注册 `state-sync` workflow 和定时任务。
4. 移除 launchd `WatchPaths` 直接调用，改事件 emit。

### Phase 3：读写分离（2-4 周）

1. 将 `.omo/state/`、`.omo/_control/governance-data.json` 标记为 generated/runtime，探讨是否 gitignore。
2. `BRIEF.md` 改为 CI 生成，本地不强制同步。
3. dashboard / cockpit 从 broker 或 runtime 目录读取，不依赖 git tracked 文件。

### Phase 4：子模块治理（持续）

1. 实现 `omo submodule cleanup`。
2. pre-push hook 强制 clean submodule。
3. 在 agent 工作流中增加子模块退出检查。

## 8. 预期效果

- `.omo/state/` 和 `BRIEF.md` 的 dirty 状态从“每次 commit 都变”降到“仅 state-sync agent 写一次”；
- 多 agent 并行时，写冲突归零（单写者 + 文件锁）；
- 无意义 git diff 归零（内容指纹）；
- 子模块 dirty 在 push 前被自动清理或显式 commit；
- 所有状态变更可审计（event log + mutation ledger）。

## 9. 风险与回退

| 风险 | 缓解 |
|---|---|
| state-sync agent 崩溃导致状态滞后 | CI gate 最后一步仍强制刷新；`state-freshness-check` 告警 stale |
| 单写者成为瓶颈 | state generation 是轻量计算（<1s），FileLock 短暂；可水平扩展为队列 |
| BRIEF.md 不再实时 | cockpit 改为读取 `.omo/state/` 或调用 broker API |
| 历史工具依赖直接写 `.omo/state/` | 保留兼容 shim 6 个月，逐步迁移，lint gate 检测新 direct-io |

## 10. 待决策

1. 是否接受 `BRIEF.md` 改为 CI-only 生成？
2. 是否接受 `.omo/state/` 移入 gitignored runtime 目录？
3. `state-sync agent` 用 launchd cron 还是 Agora 事件消费者实现？
4. 子模块 dirty 自动 reset 的允许名单（如 `uv.lock`、`_derivation_logs/`、`.omc/`）是否需要项目级配置？
