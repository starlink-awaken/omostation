---
title: BET-Y1Q1-T6-08 retro — OPS-INFRA 四件核实
type: retro
owner: governance-agent
created: 2026-08-17
bet: BET-Y1Q1-T6-08
related:
  - /Users/xiamingxing/Downloads/AGENT-BRIEF-OPS-INFRA-GOVERNANCE.md
lifecycle: history
last_updated: 2026-08-18
---

# BET-Y1Q1-T6-08 复盘

## Q1 做了什么

OPS-INFRA 派工四任务全量落地：E-DOC 规则核实报告 / 调度重叠实测 / Hermes 边界声明 /
灾备清单。全程**本机终端权限可用**（派工指令最担心的"云端沙箱够不着宿主机"未发生），
Hermes/crontab/launchd 三处均实测直读。

## Q2 核心发现（按严重度）

1. **cron-daily-dashboard 静默失败 ≥11 天**（dashboard 最后产物 08-06）——脚本**从未入过 git**
   （全历史 -S 搜索零痕迹），crontab 引用幽灵文件，无告警。派工指令的怀疑完全证实。
2. **E-DOC(ln-001~005) 五条规则全部未接线**——只存在于 ADR-0191 Markdown，
   registry/CI/preflight 零实现；唯一"部分接线"的是 ln-005 的两个生成脚本（无强制门禁）。
3. **mof-drift 周巡检路径断**——crontab 写 `bin/mof-drift`，真实位置 `bin/mof/mof-drift`。
4. **launchd 26 个活跃 plist 未入库**（仅 2 个在 git）——单机最大灾备敞口。

## Q3 打假（与派工指令假设不符）

1. **E-DOC 编号不存在**：指令反复用 "E-DOC-001~005"，仓内任何文件无此编号——
   实际是 ADR-0191 §2.2 的 `ln-001~005`。指令起草者转写时换名未回仓核对。
2. **ADR-0190 撞号双义**：`.omo/_knowledge/decisions/0190` 是 dashboard JSON contract，
   MOF 动态约束引擎的 0190 在 `docs/adr/`。指令引用 "ADR-0190 (PR #1626)" 两处都不精确。
3. **"三处治理审计重复"不成立**：实测三层职责正交（引擎 audit / roadmap 投影 / CI 巡检），
   产出路径互不覆盖。蓝图 §1.2 的"重复"判断被推翻。
4. **派工的两份同名文件**（`_1` 后缀）内容逐行相同——用户侧重复下载，非两个不同指令。

## Q4 教训

- 幽灵 cron（引用从未入库的脚本）是静默失败的最隐蔽形态——git -S 全历史搜索
  是判定"从未存在 vs 被删除"的唯一可靠手段。
- 蓝图类二手分析（§1.2/§1.3）的"重复/未接线"结论必须实测复核——本轮 2/3 被修正。

## Q5 移交

修复决策全部交人类（派工指令明确要求）：dashboard cron 删行 vs 补脚本 / mof-drift 改路径 /
E-DOC 是否接线。边界声明已含 Q3 审批约定（即日生效）。
