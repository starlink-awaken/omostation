---
title: 收敛期六项 · 落地执行总表
status: active
type: execution-status
owner: 夏明星
created: 2026-07-15
related:
  - .omo/_knowledge/decisions/0210-three-year-strategy-execution-convergence.md
  - .omo/_knowledge/decisions/0218-agent-isolation-p0-verify-and-hygiene.md
  - docs/STRATEGY-M1-EVIDENCE.md
  - docs/RUNTIME-DAEMON-REMEDIATION.md
  - docs/HEALTH-SCORE-ISC3-DESIGN.md
  - docs/STRATEGY-INDEX.md
note: >
  ADR-0210 收敛期 6 项的执行落地实况（2026-07-15 沙箱盘点）。运行时数字权威源
  .omo/state/*.yaml。代码/cron/入库类落地在授权 dev 环境执行。
---

# 收敛期六项 · 落地执行总表（2026-07-15）

> **贯穿结论**：收敛期 6 项里 **5 项是"已建未验/未完成"，仅 1 项（KOS）真·从零**。
> 这是 ADR-0210 核心论点「图纸 A 级、实物 B- 级」最强的自证——
> **杠杆是"核实+激活+收尾"，不是"从头造"**。

## 一、六项落地总表

| # | 收敛期项 | Pri | 真实状态 | 已建部分 | 剩余落地动作 | 归属 |
|---|---------|-----|---------|---------|-------------|------|
| 1 | Agent Isolation | P0 | ✅ **实测达标** | pre-push blocking + worktree 隔离 + 卫生净 | ISC-4 branch-protection API 核实（gh）| 授权终端 |
| 2 | 修复 L1 runtime | P0 | 🟡 根因深挖：**运行态问题非改码** | 探测 transient 跳过逻辑源码已存在（health.py `_is_transient`/`_tick`）| **运行态诊断**：重启 gateway 拾取源码修复 + 活体查 `_is_transient` 分类；沙箱内 gateway 已被并发重启（48h→88min）报 all-20-dead | 你机器活体调 |
| 3 | 重构 health_score | P1 | 🟡 权重已调/输入脏 | ISC-2 权重已执行面主导(runtime 0.5) | ISC-3：runtime 去假阳性 + governance 执行面化 + 口径单源 | dev+OMO broker |
| 4 | gitlink 巡检 cron | P1 | 🟢 **脚本就绪，差挂 cron** | `bin/submodule-gitlink-check.py` | 挂 foundry 6h cron deck | dev/cron 配置 |
| 5 | 单写者 + 门禁免疫 | P2 | 🟡 **声明已实现，自愈未实现** | `write-owners.yaml` + GaC #38 + audit 工具 | L2 门禁即免疫（失败自动生成修复草案 commit）+ 确认 audit 进 pre-commit | dev 改码 |
| 6 | KOS 索引启动 | P1 | 🔴 **真·未启动** | 无（kos/ = 0 篇）| 建入库流程，把 636 创意创作产出首批导入 kos/ | dev+数据 |

## 二、三个"已建未验"的证据（图纸 A / 实物 B- 的活体）

- **①Isolation**：ROLLOUT 文档称"未启用"，实测 pre-push blocking 早已 active（07-04 起）。
- **⑤单写者**：ADR-0210 列为待办，实际 `write-owners.yaml`（GaC #38）已 version 1、覆盖 system.yaml 逐字段 owner。
- **④gitlink**：治本脚本 PR#351 早就写好，只差最后一步"挂 cron"。

> 三者都印证：这个系统**不缺设计，缺"最后一厘米"的激活与验证**。收敛期真正的工作量
> 远小于"从零"，前提是承认"已建"并去核实，而非重复造。

## 三、落地优先级（按杠杆 × 成本）

```
先做 (高杠杆/低成本):
  ④ gitlink 挂 cron        —— 1 步配置, 脚本已就绪
  ① ISC-4 gh 核实          —— 1 条命令, 收尾 Isolation
  ② runtime probe 修复      —— 改 ~10 行, 直接把 daemon 假红灯→真值, 拉起 health

再做 (中杠杆, 有依赖):
  ③ health_score ISC-3     —— 依赖 ② 先落 (否则放大假信号)
  ⑤ 门禁即免疫 L2          —— 声明已在, 补自愈草案机制

后做 (真·新建, 长周期):
  ⑥ KOS 索引启动           —— 唯一从零, 是跃迁期个人大脑的前置, 越早起量越好
```

## 四、M1 达标缺口（对齐 ADR-0210 门禁）

| M1 门禁 | 现状 | 差距 |
|---------|------|------|
| 并发 agent 主仓冲突 = 0 | 🟢 机制达标（Isolation 实测）| 待持续观察 |
| daemon 在线率 ≥ 90% | 🔴 假红灯 0.6-0.75 | 差 ②runtime probe 修复（改码即达标）|
| health_score 反映执行面 | 🟡 权重对/输入脏 | 差 ②+③ |

> **M1 的钥匙就是第 ② 项**：runtime probe 一修，daemon 假红灯→真值≥0.9，M1 的
> daemon 门禁达标，health 自动升到真值≈96。**②是整个收敛期性价比最高的一锤。**

## 五、沙箱已完成 vs 待授权环境

**沙箱已完成（诊断/设计/证据，全部留档）**：
- ①Isolation 三态核实 + 卫生清理（实测达标）
- ②runtime 根因定位到具体文件行 + 整改盘点
- ③health_score ISC-3 完整设计
- ④⑤⑥ 真实状态盘点 + 落地动作清单

**待你授权终端/dev 环境（需 git 凭证 / gh / 改子模块码 / OMO broker）**：
- push 本会话所有执行文档 + 战略文档
- ②改 probe 码 + PR；④挂 cron；⑤补 L2 自愈；⑥建 KOS 入库
- 每项走 ADR-0203 workflow + 独立 worktree + PR（dogfood Isolation）

---

*收敛期执行总表 · 2026-07-15 · 夏明星 · 运行时数字以 .omo/state/*.yaml 为准*
