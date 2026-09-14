---
id: ADR-0392
title: CI 修复 + 主仓 dirty 提交 — drafts persistence_mode + runtime state 同步
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-08
type: ssot
---

# ADR-0392 Decision: CI 修复 + 主仓 dirty 提交

> 承接 ADR-0390 / 0391 验证. 本轮聚焦:
> 1. 修 origin/main governance-verify 连续 failure 根因 (state-plane-assets)
> 2. 提交主仓 6 个 dirty state 文件 (合并 1 PR)

## 一、CI 修复 (实测量, 不靠猜)

**症状**: origin/main governance-verify 连续 5+ 次 failure (run 31224822603 / 31224739809)
**根因**: `.omo/_truth/registry/omo-governance-surfaces.yaml` 登记的 OMO-DRAFTS
asset 用 `persistence_mode: working`, 不在 `ALLOWED_PERSISTENCE_MODES` 集合里:

```python
# projects/omo/src/omo/omo_governance_surfaces.py:400
ALLOWED_PERSISTENCE_MODES = {
    "authoritative", "durable", "operational", "append_only",
    "archival", "compatibility_alias", "derived", "ephemeral",
}
# 'working' ∉ allowed
```

**修复**: `persistence_mode: working` → `operational`

理由: drafts 是"工作进行中资产", 与 cockpit control_state 同语义
(后者用 `operational + rolling_window`). OMO-DRAFTS 用 `manual_archive` 保留
模式 (草稿不自动清理, 由人工归档), 仅持久化语义需对齐.

**验证**:

```bash
$ uv run --directory projects/omo python -m omo.cli lint state-plane-assets
✅ omo lint state-plane-assets pass: top_level_assets=38 persistence_modes=8
```

**旁路注册表漂移 (P73 真理驱动)**: drafts 是并发 agent 在主仓 `.omo/drafts/`
创建的"草稿"目录 (含 `omni-bus-phased-program.md`). 登记于 5 轮之前 (PR #1107 era),
但 persistence_mode 选错是单点失误, 治本即修字段, 不重设制度.

## 二、Dirty 提交

主仓 `work/scene-v2-goals-wave2` 分支 dirty 10 个文件, 拆解:

| 文件 | 类别 | lane |
|------|------|------|
| `.omo/_truth/registry/omo-governance-surfaces.yaml` | SSOT 注册表 | governance_state |
| `.omo/_truth/registry/memory-os.yaml` | SSOT 注册表 (belief count 1→3) | governance_state |
| `.omo/state/health.yaml` | runtime 状态 | governance_state |
| `.omo/state/system.yaml` | runtime 状态 | governance_state |
| `.omo/state/agent-beliefs/{index,audit.log}` | belief 状态 (T3-02 推进产物) | **跳过 (worktree 缺目录, 属领先 9 commits 中的并发工作)** |
| `projects/{c2g,cockpit,kairon,metaos}/` | 子模块 dirty | **跳过 (其他 agent 工作, git-discipline §6)** |
| `projects/agora` (untracked) | 未跟踪 | 跳过 |
| `.omo/notepads/delegation-guardrails/` | 未跟踪 notepad | 跳过 (并发 agent 文档) |

**实际提交**: 4 个文件 (2 SSOT + 2 runtime state), 拆 2 commits 走 lane 纪律.

## 三、策略

主仓 `work/scene-v2-goals-wave2` 领先 origin/main 9 commits (swarm/scene 推进并发 work).
直接在该分支 commit 会带并发 9 commits 污染 PR → **新 worktree from origin/main
(a8154cd6)** 干净基础上提交, PR base 干净.

## 四、与 ADR-0390 / 0391 关系

- ADR-0390: omo_daemon 漏 checks 字段 (omo 子模块修复已 push 7a96dfb1)
- ADR-0391: M5 数据黑障验证报告 (本机直接调用 100% 生效, 等 dev 环境 daemon tick 二次验证)
- ADR-0392 (本 ADR): 主仓 CI 修复 + dirty 提交 (本轮范围)

## 五、后续

1. PR #1129 之前未推动此修复, 等本 PR 合并后 dev daemon tick 即可产出含 checks 数据
2. ADR-0390 §五 暂缓项 (归零 gate 处置 + NOISY warn 降级) 等数据恢复后启动
3. 验证命令 (12-24h 后):
   ```bash
   python3 -c "import json; [print(json.loads(l)['timestamp'], len(json.loads(l).get('checks',[]))) for l in open('.omo/_knowledge/governance-history.jsonl') if l.strip()][-5:]"
   ```
   预期: 至少 1 条 `checks > 0`