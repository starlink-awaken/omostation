---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-06
last-reviewed: 2026-09-06
bet_id: BET-Y1Q4-T5-02
risk_level: L1
human_gate: false
value_indicator_policy: false
type: ssot
---

# T5-02 B.D.S.K. 四角对抗审议融入 Cockpit 设计

## 1. 目标

提供 `cockpit bdsk evaluate --spec <file>` 一键评审：对重大技术方案或
高风险外发内容，自动执行商业（Business）/研发（Developer）/安全
（Security）/知识（Knowledge）四角对抗审议，输出含 4 角评语、风险
雷达图与折中方案的 MADR 决策报告。

## 2. In scope

1. `projects/cockpit/src/cockpit/commands/bdsk.py`（新文件）：
   - `cmd_bdsk_evaluate(spec_path)`：读取方案文件 → 复用
     `bdsk_engine.py` 四角审议引擎 → 逐角生成评语（规则启发式：
     方案文本中的成本/风险/依赖/未知项信号词映射四角关注点）→
     汇总 MADR 决策报告（Markdown：背景/四角评语/风险雷达表/
     折中方案/决议建议）。
   - `--demo` 模式：内置样例 spec，供 verify 命令与冒烟。
   - 风险雷达：五维评分表（成本/工期/安全/可维护性/未知度，0-5 分，
     规则推导），以 Markdown 表格呈现。
2. `cockpit bdsk` 子命令 argparse 注册（_subcommands.py）。
3. 测试：4 角评语完整性、MADR 结构、demo 模式、指定 spec 评审。

## 3. Out of scope

- 不引入 LLM 生成（评语为规则启发式；LLM 增强属后续）。
- 不改 bdsk_engine.py 既有契约（只消费）。
- 不自动拦截外发（评审报告供 T10-116 外发面人工参考；自动触发门禁
  属后续 bet）。

## 4. 验收（对齐 ledger done_when）

1. `cockpit bdsk evaluate --spec <file>` 一键评审 exit 0 且产出报告。
2. 报告含 4 角评语、风险雷达表、折中方案三要素。
3. `uv run python -m cockpit.cli bdsk evaluate --demo` exit 0。
