# P49 治理注册表收口 — TASK-A5378E91 漂移修复 + 3 候选 done

> **Upstream**: P48-GBR-AHEAD (mof-version v0.0.36) / OMO 100 A+ 持续
> **Appetite:** 4 hours
> **Vector:** V2 (c2g brainstorm 转化)
> **Type:** Feature + 治理收口

## 背景与上下文

P48 (commit 993ca322) 完成后审计：

- **3 候选 PLANNED 残留**:
  - `IMPORTED-f9b1e2`: 任务1 (c2g brainstorm 历史, 0 描述, 无实际工作)
  - `OPC-P6-SELF-EVOLUTION-doc-gate-e`: OPC phase 6 治理 (历史 OPC task, 闭环)
  - **`TASK-A5378E91`: 治理注册表漂移** (真实债!)
- **TASK-A5378E91 描述**:
  - cockpit test_no_subcommand fail
  - `omo-governance-surfaces.yaml` registry 漂移
  - `debt/workers` 过期注册 (已 gitignore/搬家)
  - `DOC-LIFECYCLE.md / bets.json / tasks.json` 新资产未注册
- **mof-drift 仍 2 LOW** (gbrain TODOs, P49 不修)

## 目标

### P49 R1 (今天, 1h) — 立项 + 修 TASK-A5378E91
- **G1**: c2g bet → omo broker → P49-REG-CLEANUP PLANNED task
- **G2**: 修 omo-governance-surfaces.yaml: 删 `debt/workers` 过期注册, 加 `DOC-LIFECYCLE/bets.json/tasks.json` 新注册
- **G3**: 跑 cockpit test_no_subcommand 验证 (期望 pass)

### P49 R2 (今天, 1h) — 3 候选 done
- **G4**: 3 PLANNED 候选 (IMPORTED-f9b1e2 / OPC-P6-SELF-EVOLUTION-doc-gate-e / TASK-A5378E91) 全部 done
- **G5**: TASK-A5378E91 done 用真实 evidence (registry 修 + test pass)

### P49 R3 (今天, 0.5h) — 收口
- **G6**: P49-REG-CLEANUP task → done
- **G7**: mof-version v0.0.36 → v0.0.37
- **G8**: 收口报告入 `.omo/_knowledge/audits/`
- **G9**: governance 100 A+ + PLANNED 清零 (0 candidate) 持续

## 技术要求

- **零路径破坏**: 不改 P45-P48 任何文件
- **registry 修**: 沿用 P48 末尾 commit (89cd7f6f) 的 fix pattern
- **test_no_subcommand**: 跑 cockpit test 验证 (期望 0 fail)

## 验收标准

1. **G1** P49-REG-CLEANUP PLANNED task 创建
2. **G2** omo-governance-surfaces.yaml registry 修正 (debt/workers 删 + 3 新增)
3. **G3** cockpit test_no_subcommand 0 fail
4. **G4** 3 PLANNED 候选 done
5. **G6-G9** task done + mof-version v0.0.37 + 收口报告
6. **PLANNED 目录清零** (0 candidate/pending)

## 风险

| 风险 | 缓解 |
|------|------|
| registry 修错触发 omo CLI 故障 | 跑 cockpit test + omo governance 验证 |
| 3 候选 cascade 误判 | 评估每个 evidence 后再推进 |
| mof-extract 钩子副作用 | 与 P48 R3 同策略 (刷 health.yaml + commit) |

## 关联

- TASK-A5378E91: 真实债 (P48 末尾 commit 89cd7f6f 已修部分)
- P48 R3: mof-drift v3 + 17 项目 lint
- P45 R6: frontmatter 100% (DOC-LIFECYCLE.md)
- c2g/ bet: 历史 IMPORTED-* 任务

## NoGos (YAGNI)

- ❌ 不实施 gbrain 53 TODOs (P50+)
- ❌ 不修 mof-drift 6 维度逻辑
- ❌ 不改 mof-version 工具
- ❌ 不删任何 task (cascade done 不是删)
