# Phase 4 execution roadmap

> 日期: 2026-05-31
> 起点: Phase 3 completed，Phase 3 acceptance baseline green
> 主题: 把 worker 协作机制从“试点可用”推进到“默认执行底座”

## Goal

Phase 4 的目标不是再做一轮大而散的 capability 扩张，而是把已经存在的治理、worker、acceptance 机制进一步产品化：

1. 让 worker 协作从 pilot 走向稳定日常执行；
2. 让 reclaim / handoff / evidence chain 变成默认行为，而不是演练行为；
3. 让 `.omo` 的 control / truth / delivery 闭环更多靠自动校验，而不是靠人工盯盘。

## Worker collaboration assessment

结合现有 run records、pilot reclaim/handoff review、Phase 2 的两次真实 worker dispatch，可以得出一个比较清楚的判断：

- **机制有效，但仍偏手工。**
- `codebuddy` 在 `P2-FIX-HARDCODED-PATHS` 上交付了真实价值，证明外部 worker 能承担边界清晰的 L1 实施任务。
- `reasonix` 在 `P2-PLAN-SAFE-MESH-RBAC` 上输出了结构化 roadmap，证明外部 worker 适合聚焦规划/诊断型任务。
- reclaim/handoff pilot 成功，说明 envelope → dispatch → reclaim → second-worker review 这条证据链成立。
- 但目前 dispatch 频次低、checkpoint 产物浅、协同流程仍较依赖 coordinator 手工组织，尚未形成高吞吐的多 worker 作业面。

结论：**Phase 4 应该优先做 worker ops productionization，而不是立刻扩大 worker 数量或权限。**

## Wave 1 priorities

### 1. dispatch automation

目标：把 worker dispatch 从“能手动做”推进到“低摩擦、可重复、可收敛”。

重点：

- 统一生成 dispatch / prompt / review / reclaim 文件
- 自动回写 task YAML 的 `dispatch_id / run_ref / review_ref`
- 提供最小 worker status 视图，降低 coordinator 认知负担

当前已落地：

- `scripts/omo worker dispatch` 会自动生成 checkpoint / reclaim stub，并把 refs 回写到 task 和 dispatch
- `scripts/omo worker status` 可汇总 active dispatch、worker、checkpoint 数量、reclaim 指针

### 2. checkpointed reclaim drill

目标：把 reclaim/handoff 从早期中断演练升级成“带部分产物和 checkpoint 的恢复演练”。

重点：

- 强制 first worker 在 lease 窗口内留下 checkpoint
- reclaim note 必须引用 checkpoint / partial artifact
- second worker 必须能基于已有 checkpoint 续跑，而不是重新开始

当前已落地：

- `scripts/omo worker reclaim` 会把前序 dispatch 标记为 `reclaimed`
- successor dispatch 会继承 checkpoint / reclaim 证据，并在 prompt 中显式要求从 checkpoint 续跑

### 3. consistency auto-gate

目标：把 `.omo` 里最关键的状态对账固化成自动 gate。

重点：

- `state/system.yaml` 与 `tasks/active|blocked|done` 数量一致
- active task 必须具备必要的 `run_ref / review_ref / evidence_required`
- Phase 4 kickoff 相关 roadmap / review / task / state 入口保持互相可回指

当前已落地：

- `scripts/sync_omo_state.py` 会对 active task 缺失 `run_ref / review_ref` 自动写入 divergence flags

## Wave 2 outlook

在 Wave 1 稳定后，再进入：

1. **knowledge-linked handoff index**：把 handoff / approval / review / acceptance 关联为统一索引。
2. **worker utilization baseline**：开始用周维度衡量 external worker 的真实吞吐、成功率、reclaim 率。
3. **phase gate promotion automation**：让阶段升级前的文档/测试/acceptance 清单自动生成。

## Verification

- `.omo/tests/test_phase4_kickoff_docs.py`
- `.omo/tests/test_worker_mechanism_consistency.py`
- `.omo/tests/test_omo_automation.py`
- `.omo/tests/test_phase3_acceptance_runner.py`
- `python3 scripts/phase3_acceptance.py --write-report`

## Success criteria

- Phase 4 目标、状态、active tasks 已正式 seed 到 `.omo`
- worker 协作机制有书面 effectiveness review，可作为 Phase 4 基线
- 四平面入口能直接引到 Phase 4 roadmap 与 worker review
- Phase 3 acceptance baseline 继续保持绿色
