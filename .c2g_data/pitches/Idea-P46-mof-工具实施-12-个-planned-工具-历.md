# P46 mof 工具实施 (12 个 planned 工具) + 历史 PLANNED candidate 推进

> **Upstream**: P45-DOC-LIFECYCLE (v0.0.32) / OMO 100 A+ 收口
> **Appetite:** 1.5 day
> **Vector:** V2 (从 c2g brainstorm 转化)
> **Type:** Feature + 治理收敛

## 背景与上下文

P45 完成后审计 bin/mof-* 工具状态：

- **16 个 mof 工具**: 4 个真活 (mof-drift / mof-enforce / mof-version / mof-fix-cross-project.sh)
- **12 个 `Status: planned` 占位**: mof-act / mof-analyze / mof-assign / mof-autonomous / mof-decide / mof-evolution / mof-export / mof-graph / mof-io / mof-manage / mof-scan / mof-fix-cross-project.sh (部分)
- **mof-drift 报告 LOW 项**: 主要是 gbrain 53 TODOs (gbrain 子仓, P46+ 处理)

P45 R4 治理面让 mof 工具状态显式化（`Status: planned` 注释），但**没真正实现**这些工具。

同时 P44-P45 把所有 PLANNED 历史任务已收口，但**根仓 11 个 PLANNED candidate/pending** 仍是历史 task 状态。

## 目标

### P46 R1 (今天, 1h) — 立项 + 11 PLANNED 推进
- **G1**: 11 个 PLANNED candidate/pending → 推进 done (cascade from P45)
  - BET-ARCH-CONVERGENCE / IMPORTED-* / OPT-BOS-GATEWAY / REMEDIATE-ARC-CONV-* / TASK-* / TASK-DEBT-CLOSURE-EVIDENCE
  - 评估每个: 是否有 evidence 在子仓? 没有 → 标 `superseded by P45/P46`
- **G2**: c2g bet → omo broker → P46-MOF-IMPL PLANNED task

### P46 R2 (今天, 1h) — mof 工具实施 (低风险先)
- **G3**: mof-io — IO 工具 (封 mof-extract-hooks 逻辑)
- **G4**: mof-graph — 依赖图工具 (基于 mof 节点)
- **G5**: mof-scan — 安全扫描工具
- **G6**: 移除 `Status: planned` 注释 → 标 `Status: implemented`

### P46 R3 (今天, 0.5h) — 治理集成验证
- **G7**: omo governance 跑通 (期望 100 A+ 持续)
- **G8**: mof-version bump v0.0.32 → v0.0.33
- **G9**: 收口报告

## 技术要求

- **零路径破坏**: 不改 P45 已落地的 R1-R8 任何文件
- **mof 工具实施**: 沿用现有 bin/mof-* 模式 (Python + yaml + sys.path 操作)
- **PLANNED 推进**: 用 omo broker (complete_task) 路径
- **WARN only**: mof 工具必须用前 3 个真活 mof-* 的同款 entry point 模式

## 验收标准

1. **G1** 11 个 PLANNED 全部 done (或 cascade archived)
2. **G2** P46-MOF-IMPL PLANNED task 创建
3. **G3-G5** 3 个 mof 工具实施 + Status 改 implemented
4. **G7** omo governance ≥ 100 A+
5. **G8** mof-version v0.0.33
6. **G9** 收口报告入 .omo/_knowledge/audits/

## 风险

| 风险 | 缓解 |
|------|------|
| mof 实施破坏现有 mof-drift/mof-enforce/mof-version | 不动它们的实现, 只新增 mof-io/mof-graph/mof-scan |
| 11 PLANNED 推进后 omo governance 报新 WARN | 推进到 done 应不触发 (N+1 check) |
| pre-commit 钩子误触发 | mof-io 实施后不需新增钩子 (保持现状) |

## 关联

- P45-DOC-LIFECYCLE (v0.0.32): 治理面 100 A+ 完美
- P45 R4: 12 mof 工具标 Status: planned
- P44 DEFER 任务: 已被 P45 superseded

## NoGos (YAGNI)

- ❌ 不实施所有 12 个 mof (只做 3 个低风险 R2)
- ❌ 不改 P45 任何文件
- ❌ 不实现 mof 工具的"完整功能" (最小可用即可)
- ❌ 不在 P46 推子仓 ahead (gbrain 15 commits 留 P47)
