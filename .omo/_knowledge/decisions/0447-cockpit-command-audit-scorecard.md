---
id: ADR-0447
status: accepted
lifecycle: spec
owner: xiamingxing
last_updated: 2026-09-01
---

# ADR-0447: cockpit 命令多维审查评分卡 SSOT (15 维)

- **Status**: ACCEPTED
- **Date**: 2026-09-01
- **Authors**: xiamingxing, worker-d-audit
- **实现**: `projects/cockpit/src/cockpit/commands/command_audit.py`、
  `projects/cockpit/docs/command-audit/`（325 张评分卡 + _REPORT.md）
- **关联**: ADR-0445 (delegation/catalog), ADR-0446 (chain/JSON_CAPABLE)

## Context and Problem Statement

用户要求对每个命令（全量递归所有子命令）做多维审查：功能/应用场景/目标/
性能/可用性/稳定性/扩展性/可观察性/日志监控告警/可进化/可运营/可运维/
Agent 友好度/输入输出易读性/状态与长期记忆。此前无任何命令质量审查先例。

## Decision

1. **评分卡 SSOT**: `docs/command-audit/<cmd_path>.yaml`（顶级 `<cmd>.yaml`、
   子命令 `<cmd>.<sub>.yaml`），每卡 15 维 `{score 1-5|null, evidence,
   suggestion}`；`summary.total` 由 CLI 实算（手写视为 lint 违规）。
2. **节点权威来源**: `walk_command_tree(create_parser())` 递归遍历 argparse
   树（alias 去重、REMAINDER 委派只记根节点）—— 325 节点，100% 覆盖。
3. **CLI 四子命令**: `command-audit init`（骨架生成+覆盖率）/
   `validate [--strict]`（schema 校验）/ `report`（_REPORT.md：维度均分、
   低分 TOP-N、P0 达标率）/ `lint`（覆盖率+180 天过期+schema 违规，非零
   退出可挂 CI）。
4. **评审策略**: agent 批量初稿 + P0（28 个高频顶级命令）全量 15 维真实
   评审（evidence 带 file:line 或 --help 实测证据）；其余 297 张骨架 null
   滚动补齐，lint 挡覆盖率回退。
5. **审查结论驱动改进**: 最弱维度 logging_alerting 2.57 / observability
   3.18 / performance 3.00；未达标 dashboard/journey 的改进建议已入卡；
   io_readability 维度驱动 `--output json` JSON_CAPABLE 扩容。

## Consequences

- ✅ 命令质量可度量、可 lint、可 diff；agent 可读（YAML）
- ✅ create_parser() 抽取后 main 与审计共用同一 parser 树（零漂移）
- ⚠️ 325 张中 297 张待补真实评审 —— 滚动机制，lint 保证不回退
