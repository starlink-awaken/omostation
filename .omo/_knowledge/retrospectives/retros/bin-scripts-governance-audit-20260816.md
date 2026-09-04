---
title: bin/scripts 收敛审计复盘
type: retro
owner: governance-team
created: 2026-08-16
context: >-
  bin/ 与 scripts/ 全量审计完成，第一波交付治理计划、审计基线和 manifest 机制。
  bet_id unbound，按审计/治理复盘处理。
lifecycle: history
last_updated: 2026-08-18
---

# bin/scripts 收敛审计复盘

## 核验与交付 (2026-08-16)

| done_when | 结果 | 证据 |
|-----------|------|------|
| 完成 bin/ 与 scripts/ 全量能力审计 | PASS | `bin/tool-registry-audit.py --scope both` 产出 758 个脚本基线 |
| 明确长期收敛方向 | PASS | `docs/plans/bin-scripts-governance-plan.md`：bin 为主实现，scripts 为 compat shim |
| 建立可持续治理机制 | PASS | `docs/operations/bin-scripts-convergence-manifest.json` + `bin/tool-registry-audit.py` 复用，不新增重复 registry |
| 第一波保持非破坏性 | PASS | 未批量 rename、未删除、未移动文件；只沉淀计划、manifest、审计基线、复盘 |
| 与子项目/模块重合点可追踪 | PASS | 审计识别 parallel candidates 173、mirrored duplicates 234、shim candidates 236、archive candidates 87 |

## 审计基线摘要

- Total scripts: 758
- Python: 688，Shell: 68
- Non-snake_case names: 631
- Duplicate names: 237
- Parallel candidates: 173
- Mirrored duplicates: 234
- Shim candidates: 236
- Archive candidates: 87
- bin/scripts overlap 分类：merged 144 / different 44 / only_bin 340 / only_scripts 57

## Q1-Q5 简答

### Q1. 这次要解决什么问题？

bin/ 下脚本大量堆积，且与 scripts/ 及子项目存在能力重合；缺少统一入口、命名规范、归属规则和长期治理机制。

### Q2. 根因是什么？

脚本长期以“临时工具”方式追加，入口边界、命名、实现归属没有显式契约，导致同名、镜像脚本、能力平行实现不断出现。

### Q3. 交付是否达成？

达成第一波基线。核心结论是 `bin/` 作为主实现与入口，`scripts/` 仅保留兼容 shim；长期用 manifest + tool-registry-audit 门禁约束，不再新造 registry 系统。

### Q4. 有什么风险？

存量 631 个非 snake_case 命名和 87 个归档候选不能一次性机械迁移，否则会破坏既有调用链。后续波次必须逐批声明调用方、测试和兼容策略。

### Q5. 下一步做什么？

进入主仓库根目录治理：继续识别根目录与 bin/scripts/子项目的重合能力，复用 manifest + audit + PR + retro 机制滚动收敛。
