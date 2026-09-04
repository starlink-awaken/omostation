---
lifecycle: history
owner: auto-fix-loop
last_updated: 2026-08-24
title: "Retro — BET-Y1Q3-T6-08: GaC 本地门禁剩余债务清理"
type: retro
---

# Retro — BET-Y1Q3-T6-08: GaC 本地门禁剩余债务清理

## 元信息
- **BET**: BET-Y1Q3-T6-08
- **窗口**: Y1Q3
- **Track**: T6-SUBTRACT
- **负责人**: governance-agent (kimi-cleanup-20260819)
- **起止**: 2026-08-19 → 2026-08-19
- **Appetite**: 4 hours
- **实际耗时**: ~1.5 hours

## Q1 实际耗时 vs appetite
实际耗时约 1.5 小时，远低于 4 小时 appetite。主要原因：
- ADR 索引缺口只是追加 4 行，工作量小。
- bin/ 减法配额在 PR #1725 合并后已经自然满足（活跃脚本 410），无需额外归档。
- 真正的剩余债务是 `.artifacts/` 未注册导致的 `root-directory-governance-scan` 失败，修复只需修改 `.gitignore` 与 policy。

## Q2 done_when 是否全部通过
全部通过：
1. ✅ 4 个未索引 ADR（0415-0418）写入 INDEX.md。
2. ✅ `make gac-local-gate` 46 checks ALL GREEN（含 root-directory-governance、adr-coverage 等）。
3. ✅ `.artifacts/` 注册为允许忽略面（.gitignore + root-directory-governance-policy.yaml）。

## Q3 过程中发现的与 plan 不符的事实
- **预期**: 需要归档 6 个 bin/ 脚本才能恢复全绿。
- **实际**: 合并 PR #1725 后 bin/ 活跃脚本已降至 410，无需再归档。之前的“416 超基线”是合并前的快照，未及时更新。
- **预期外债务**: `.artifacts/` 目录因本次运行 `affected-graph.py` 生成，但既未 gitignore 也未在 policy 中注册，导致 `root-directory-governance-scan` 失败。这是 workflow 工具链自身的产物，属于新发现债务。

## Q4 净增减
| 维度 | 变化 | 备注 |
|------|------|------|
| ADR 索引 | +4 行 | 0415-0418 补齐 |
| 根目录治理 policy | +1 行 | `.artifacts/` 加入 allowed_ignored_dirs |
| .gitignore | +1 行 | `.artifacts/` 忽略 |
| 3y-bet-ledger.yaml | +1 BET 条目 | T6-08 完成记录 |
| bin/ 活跃脚本 | 0 | 已满足基线 410 |
| GaC 规则 / 脚本 / 代码行 | 0 | 无新增治理规则或代码 |

## Q5 下一个认领本 track 的 agent 需要知道什么
1. **运行 `affected-graph.py` 会生成 `.artifacts/`**：该目录是临时 receipt，必须保持 gitignored + policy 允许忽略，否则 `root-directory-governance-scan` 会红。
2. **合并后状态可能变化**：如果基于合并前的失败快照制定计划，先重新跑一遍 `make gac-local-gate` 确认实际失败项，避免做无用功。
3. **change-lane-check 严格按 lane 拆分 commit**：`.gitignore` 被归为 `other`，`docs/` yaml 是 `docs_data`，`.omo/` 是 `governance_state`，三者不能混在一个 commit。
