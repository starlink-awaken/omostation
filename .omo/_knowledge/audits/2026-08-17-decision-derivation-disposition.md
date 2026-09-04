---
title: 决策推演文档落地处置报告 (DECISION-SCENARIO-DERIVATION)
type: audit
owner: governance-agent
created: 2026-08-17
related:
  - /Users/xiamingxing/Downloads/DECISION-SCENARIO-DERIVATION-CONFIRMATION-2026-08.md
  - docs/ARCHITECTURE-STRATEGY-OUTLOOK-2026-08.md
last_updated: 2026-08-25
lifecycle: history
---

# 推演文档 7 项落地处置（2026-08-17，用户指令"ABCE 都批准，运维决策推进落地"+ 深调研指令）

| # | 项 | 推演建议 | 实际落地 | 证据 |
|---|---|---|---|---|
| 1 | D3 ADR-0413 | 签字 ACCEPTED | ✅ ACCEPTED + T6-01 done（#1647） | 台账 done_note |
| 2 | D5 ADR-0414 | 方案 a | ✅ ACCEPTED + G-DEL.1 PARKED-DEFERRED + 三 ADR related 回填（#1647） | phase-scope.yaml |
| 3 | dashboard cron | 删（先对比产出） | ✅ **对比后发现不等价**（scanner stdout-only vs dashboard 文件产物）→ 处置升级 F1'：删幽灵行 + **补真脚本入仓**（`bin/gac/cron-daily-dashboard.sh`，scanner 汇总落盘 daily-scan.jsonl）+ cron 重装 | 脚本实跑产出 2026-08-17 行 |
| 4 | mof-drift | 先比对再决策 | ✅ **比对推翻"二选一"前提**：crontab（M1 代码 vs 模型）与 Hermes（OMO 治理漂移）检测面**正交**；且发现 **Hermes 引用的 `scripts/opc_p6_drift_detector.py` 同样不存在（双向静默失败）**→ 双修：crontab 路径已修（G1）+ Hermes prompt 改指 `bin/mof/mof-drift`（jobs.json 已改） | drift_history 工具检索 + executions.db |
| 5 | E-DOC 接线 | 阶段 2 并入 | ✅ H2 已落（ADR-0191 双镜像标 DESIGN-ONLY）；接线（H1）登记为阶段 2 派工项 | ADR-0191 §2.2 标注 |
| 6 | 4 遗留 ADR | 快速分类 | ✅ 0209→SUPERSEDED（实践覆盖）/ 0367→保持 PROPOSED（仍相关）/ P80→SUPERSEDED（0410 覆盖）/ P81→SUPERSEDED-PARTIAL（0414+过期）——各文件处置标注 | 4 文件 §4 分支B 标注 |
| 7 | **绕过口子（§5）** | 直接派工修复 | ✅ **根因比推演更深**：cli.py 无 `if __name__` guard，`-m` 调用只 import 不执行（exit 0 零输出是 no-op 假象，非"拦截"）。三件修复：main guard + start 分支 chain_bind 门（无 bet exit 1 显式拒绝）+ loader sys.modules 注册。三路径实测：拒✓/豁免✓/放行✓，3 tests 固化 | omo 子仓 e76c4e4 |

## 关键打假（推演文档的两处修正）

1. **§3.2 前提错误**：推演假设两套 drift "可能重叠，二选一删一个"——实测检测对象不同
   （M1 模型 vs OMO 治理），且 Hermes 侧同样在静默失败。正确答案是**双修**不是删。
2. **§5 定性不足**：推演说"口子存在，需堵"——真实根因是 `-m` 调用从未执行过任何东西
   （无 main guard），"绕过"实为"整体 no-op"。修复覆盖面比推演建议更大（顺带治了
   exit-0 静默）。

## 长期维护锚点

- cron-daily-dashboard.sh **已入 git**（不再是幽灵）——脚本与 cron 行一一对应可审计
- Hermes jobs.json 变更已按边界声明 Q3 约定处置（纯运维路径修正，知会留档本报告）
- 4 ADR 处置标注可被 ADR 索引工具消费（SUPERSEDED 状态语义已入 frontmatter 后标注）
