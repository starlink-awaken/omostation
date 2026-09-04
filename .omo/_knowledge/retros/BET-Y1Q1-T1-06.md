---
lifecycle: history
owner: governance-team
last_updated: 2026-08-09
title: BET-Y1Q1-T1-06 复盘
type: retro
---
# BET-Y1Q1-T1-06 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 1 week。过渡期 PASW 覆盖 + 路径 bug 修复 + 残留清理于 08-08 完成（done_at 2026-08-08），未超出。
终局（拓扑改造后删除 PASW）挂在 BET-Y1Q1-T1-05 多实例单写者落地后执行。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| 过渡期 PASW_ISOLATED_SUBS 覆盖全部 18 个子模块 | ✅ ADR-0404 扩展 |
| 18 个 rewind 存量清零 (与 T1-02 联动) | ✅ |
| 修 gac-worktree.sh 路径 bug (PASW 建到 projects/Workspace/.subtrees/) | ✅ |
| 清理现存 PASW 残留 (三份重复检出 32.2 万行) | ✅ |
| 拓扑改造完成后同一 PR 内删除 PASW 实现与 D5 纪律条目 | ⏳ 未完成 — 依赖 T1-05 (多实例单写者), 属终局条件 |

未过: 终局删除条件依赖拓扑改造 (T1-05)，非本 bet 自身缺陷。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **E8 PASW 覆盖缺口是 rewind 根因**: 所有 worktree 共用 .git/modules/projects/<sub>，PASW 只隔离 3 个子模块，worktree A 切 commit 影响 worktree B。终局是删 PASW 而非扩 PASW。
2. **E15 表面积可被无意义优化**: projects/Workspace/.subtrees/ 三份重复检出被 .gitignore 忽略，但文件系统扫描可见 —— 建/删 worktree 就能大幅波动「表面积」指标。旧版 bet-ledger surface 曾把它算入。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增:
- gac-worktree.sh 路径修复 + PASW 覆盖扩展
- ADR-0404 (PASW 全子模块扩展)
- 清理 32.2 万行残留检出
- 无新增 GaC 规则

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **PASW 是过渡方案**: 终局在 T1-05 拓扑改造（每 agent 独立 clone）后删除 PASW 实现与 D5 纪律条目。
2. worktree claim 自动提取所有子模块构建隔离树（Global PASW, ADR-0404）。
3. 表面积测量应排除 .subtrees/ 等 gitignore 检出（E15 教训）。

---

## 条件移交记录（2026-08-15，台账信任修复 r2，处置 D2）

spotcheck 曾判本 bet「❌ 不符（轻）」——Q2 第 5 条（拓扑改造完成后删除 PASW 实现与 D5 纪律条目）⏳ 未完成却标 done。复核后裁定**保持 done**，理由：

1. **条件归属去重**：第 5 条在 BET-Y1Q1-T1-05 的 done_when 里**逐字重复**（"D3 减法: D2/D3/D5 三条纪律退役并删除实现"）——该终局条件的 owner 是 T1-05（candidate），不是 T1-06。
2. T1-06 的实质交付 4/5 已全部实测通过（spotcheck 机械重跑：submodule=19、PASW_ISOLATED_SUBS grep=5）。
3. 把 Y1Q1 的 bet 挂起数周等 Y1Q3 的依赖是记账错位——本条记为「移交 T1-05 的终局条件」，T1-06 账面关闭。（原 Q2 的 ⏳ 保留不动，历史如实。）
