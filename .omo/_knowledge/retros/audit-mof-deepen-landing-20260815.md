---
title: mof-deepen 落账追溯审计 — commit 575843deb (PR #1465)
type: retro
status: archived
owner: governance-team
created: 2026-08-15
lifecycle: history
related:
  - docs/plans/3y-bet-ledger.yaml
  - bin/ssot/admin_scenes.py
context: >
  人类 2026-08-15 指令: 追溯「数字大脑模块 + 行政流程 scenes」合并 (575843deb,
  work/mof-deepen → main, PR #1465, 10 模块 1444 行) 的记账缺口。本文件只做
  归属判定与事实记录, 不改台账 status, 不新增 bet 条目 (修复决策交人类)。
last_updated: 2026-08-18
---

# mof-deepen 落账追溯 — 2026-08-15

## 1. 事实

- **commit**: `575843deb` — PR #1465 "feat(ssot): 数字大脑模块 + 行政流程 scenes 合并到 main"，2026-08-14 19:14 合入，作者 starlink-awaken，Co-authored-by Copilot
- **范围**: `bin/ssot/` 下 10 个新模块（admin_scenes 248 / risk_engine 282 / deadline_tracker 170 / mail_reader 169 / health_agent 164 / mail_agent 130 / mail_daemon 91 / mail_sender 71 / doc_generator 54 行）+ `journey-runner.py` ADMIN_SCENES dispatcher 注册 (+7) + `admin-notification-workflow.yaml` journey spec (58 行)，共 **+1444 / −0**
- **台账归属**: `docs/plans/3y-bet-ledger.yaml` 全文 grep（mof-deepen / 数字大脑 / admin_scenes / 行政流程 / mail_daemon 等）**无任何 bet 条目对应** → 判定 **(ii) 无 bet 无主落账**
- **活性核查**（2026-08-15 实测）: 各模块被 1-6 个文件引用（journey-runner 注册 + 相互引用），**有接线、非死码**；但 **10 模块全部零测试文件**（tests/ 下无任何匹配）

## 2. 归属判定

**(ii) 无 bet 无主落账** —— 1444 行功能代码未经任何 bet 的 goal/done_when/write_surfaces 约束进入 main。这与「表面积超限是主要矛盾」（AGENT-BRIEF §1.2）直接冲突：按台账纪律，如此规模的新增面必须回答"我让系统变大还是变小了"，此合并**没有回答过**。

相近但不重合的既有账目（避免误归属）：
- T6-06~10（技能结晶/影子沙箱/算力配比等）主题相邻，但 write_surfaces 与交付物均不覆盖 bin/ssot/ 这 10 个模块
- 数字大脑 P0 域（邮件感知）在 `docs/plans/` 层有规划文档，但未台账化为 bet

## 3. 追溯 retro（五问格式，代 575843deb 的执行者补记）

**Q1**: 合并于 work/mof-deepen 分支长期搁置后的一次性收编；无 bet 无 appetite 对照（这正是缺口本身）。
**Q2**: 无 done_when 可对照（无 bet）。事实核查：功能接线完成（journey-runner 注册实测在），但**零测试**是未完成面。
**Q3（打假）**: ① 1444 行零 bet 约束落 main，绕过了 D3/表面积纪律；② commit 声称"排除旧分支 2 个过时子模块指针回退"——这类合并细节说明原分支经历了漂移，未经台账消化的漂移正是"声明≠事实"温床；③ 零测试的功能面与 spotcheck 发现的"verify 漂移"同源——没有可复核证据面的交付都在制造未来审计债。
**Q4**: 净增 1444 行 / 10 文件 / 0 删除（+journey spec）。按 D2 应记入 surface 账，此前漏记。
**Q5**: 待人类拍板事项见 §4。

## 4. 待人类拍板（本轮不处置）

1. **是否补登记追溯 bet**（如 `BET-Y1Q3-T1-XX`，status 直标 done + 本 retro 为证据），把 1444 行纳入台账管辖？——满足"账实相符"但制造一笔"先斩后奏"记录
2. **是否补测试面**：10 模块零测试，是否开一个独立 bet（T6-SUBTRACT 或 T1）补最小测试 + 触达验证？——1444 行无测试的功能面风险高于无代码
3. **是否溯源 work/mof-deepen 分支的完整提交史**，确认无其他未记账交付物？
4. **流程改进**：是否要求 PR 模板/CI gate 校验"大额新增必须携带 bet-id"？（#1465 的 PR 描述无 bet 引用，gate 未拦）

## 5. 与本轮其他审计的关联

- surface 溯源审计：主仓根 +217K 净增（9 天）中本合并占 1.4K，占比小但性质最差（零约束落账）
- spotcheck：本案例与 T2-02/T1-06 同属"证据面缺失"，但方向相反——它们是"有账无实"，本例是"有实无账"
