---
lifecycle: history
owner: engineering-agent
last_updated: 2026-08-27
title: 深度复盘：业务流程全链路 × Agent 协作机制 (2026-08-27)
type: retro
---
# 深度复盘：业务流程全链路 × Agent 协作机制 (2026-08-27)

> 数据基线: 近 48h main 144 commits, 4 worktrees, resident health=recovered, mail 700 分类

## 一、业务流程全链路体检 (信号 → 认知 → 旅程 → 治理 → 沉淀)

### 1.1 信号层 (mail-daemon / signal-poller / BCOS)

| 指标 | 实测 | 评估 |
|------|------|------|
| mail-daemon 心跳 | 20:29 新鲜 | ✅ 活 |
| 分类累积 | 700 条 (400→2天→700) | ✅ 快速增长 |
| 规则短路占比 | ~92% (643/700 参考+JetBrains) | ⚠️ 信噪比极低 |
| **任务邮件** | **仅 1 封** | ❌ 核心信号源近乎枯竭 |
| BCOS 信号路由 | **无状态文件** | ❌ 未实际运行 |

**发现 F1 [信号枯竭]**: 数字大脑等了 2 天的 auto-journey, 700 封邮件里只有 1 封"任务"。
不是机制坏了——是上游没有真任务进来。JetBrains 刷屏淹没了邮箱 (643/700 = 91.9%)。
**行动**: 规则短路已在省算力 (92% 不进 LLM), 但可再进一步——JetBrains 通知类
整发件人进黑名单跳过落库, 或设"同发件人日上限"。

**发现 F2 [BCOS 空转]**: `make bcos-signals` 无状态产物。信号路由 W1-D2 建了但没跑。
设计了"公文/会议/调研/代码"四类信号路由, 但实际信号源只有邮件一个。
**行动**: 要么接真实信号源跑起来, 要么降级为设计文档 (YAGNI 审查)。

### 1.2 认知层 (mail-agent 分类 + 累积闭环)

| 指标 | 实测 | 评估 |
|------|------|------|
| 规则短路 | 92% 调用省掉 | ✅ 机制有效 |
| 脏 category | **1 条** (`通知/任务/参考/垃圾/个人`) | ⚠️ 白名单防御未拦截 |

**发现 F3 [白名单失效一例]**: 有一条记录 category 串成全部合法值拼接。白名单
`VALID_CATEGORIES` 是"取第一个匹配"还是"整体匹配"? 若 LLM 输出了整个选项列表,
整体匹配会失败 fallback 未分类, 但这条却成功落库了。防御有缺口。
**行动**: mail_agent.py 的 category 校验改为"拆词后取第一个合法值"或拒绝整串。

### 1.3 旅程层 (journey-runner / auto-journey)

- admin-notification-workflow v3 状态机 ✅ (journey-validate 13/13)
- health-medical-workflow P1 契约 ✅ (4 states/4 transitions)
- **auto-journey 触发: 0 次** — 由 F1 信号枯竭导致, 机制本身已武装 (4 场景测试过)

### 1.4 治理层 (GaC / resident / 调度)

| 指标 | 实测 | 评估 |
|------|------|------|
| GaC 本地门 | 57 checks ALL GREEN | ✅ (花了大力气修到这) |
| 调度器 | ok, 0 drift, 0 orphan | ✅ |
| meta-doctor | ok, 0 stale, 0 dead | ✅ |
| rule_baseline | 180 (实际 ~74) | ✅ 余量充足 |

### 1.5 沉淀层 (resident sediment)

| 指标 | 实测 | 评估 |
|------|------|------|
| sediment runs | 387 成功 / 115 失败 (23%) | ⚠️ 失败率偏高 |
| retro 候选 | resident retro 机制在产 (T10-18/19/20 收尾 retro 已入库) | ✅ |

**发现 F4 [sediment 失败率 23%]**: 115/502 失败。失败类型未细分 (events.jsonl 路径
未定位)。可能是正常重试, 也可能是系统性失败。
**行动**: 给 sediment 失败加分类统计 (agent 死亡/超时/断言失败), 超 30% 触发告警。

## 二、常驻 Agent 体系 (Resident) 深度评估

### 2.1 五角色实际运行状态

| 角色 | 状态 | 证据 |
|------|------|------|
| **daemon (决策/执行)** | ✅ 活跃 | 35s 前 tick, watermark 2.28MB |
| **heartbeat** | ✅ 活跃 | 每 2min 一条, health=recovered |
| **sediment (沉淀)** | ⚠️ 半健康 | 387 runs 但 23% 失败 |
| **monitor (监控)** | ❌ 疑似停滞 | 最后 alert = 昨天 06:20, `alert:None`, **delivered: false** |
| **decision** | ✅ | ledger chain ok, sequence 39 |

### 2.2 关键发现

**发现 F5 [monitor 角色空转]**: resident-monitor 的最后一条 alert:
- 时间: Aug 26 06:20 (超过 24h 前)
- `idempotency_key: "alert:None"` — **告警内容为空**
- `delivered: false` — **告警未投递**

可能解释: (a) 系统恢复后确实无告警 (正常); (b) 监控规则匹配到了 None 内容 (bug);
(c) 投递通道断 (delivered=false)。需要区分"无异常所以无告警"和"有异常但告警坏了"。
**行动**: 加"监控自证心跳"——monitor 每 N 小时发一条 no-op 心跳证明自己活着,
否则无法区分"安静"和"死亡"。

**发现 F6 [health=recovered 的语义]**: 之前 degraded → 现在 recovered。
degraded_components 为空。恢复机制自愈了 (daemon tick 恢复)。这是好信号——
resident 的自愈在真实工作。

### 2.3 Resident 与并行 Agent 群的关系

resident 是**事件驱动的常驻运行时**; 我们这些"作战 agent"是**按需拉起的临时进程**。
两者通过 events 流交互:
- 3400 events 积累 (2.28MB) — 但主要来自作战 agent 的 workflow 事件
- resident 五问提炼 (T10-17) 已能从 events 提取确定性骨架
- **实际协作模式**: resident 当"黑匣子+心跳", 作战 agent 干活后靠 sediment 收尸

## 三、Agent 协作机制实测 (48h 高压环境)

### 3.1 规模

- **144 commits/48h** 进 main (平均 3/h)
- 4 worktrees 同时活跃
- 30+ PR 合并/关闭

### 3.2 事故模式统计

| 事故 | 次数 | 根因 |
|------|------|------|
| 子仓断指 | 3+ | 子仓 commit 未推远程 + admin merge 绕 CI |
| 冲突标记进 main | 1 (5 文件) | 并行 rebase 残留未检查 |
| 治理 agent 关 PR (scope) | 2 (#2308/#2322) | 一个 PR 混多种修复 |
| frontmatter 产伤 | 3 类 (吞---/JSON盖壳/枚举) | 写侧无护栏 |
| 覆盖修复 | 2 次 (修好的 ecos 指针被并行 merge 盖回) | 合并竞态 |

### 3.3 协作机制有效性评估

| 机制 | 有效性 | 备注 |
|------|--------|------|
| worktree 隔离 | ✅ 有效 | 4 worktree 并行无文件冲突 |
| pre-push 双闸 | ✅ 有效 | 断指都被本地拦或快速发现 |
| 治理 agent 审 PR | ✅ 有效但严 | scope 混杂会被关——纪律执行者存在 |
| admin merge | ⚠️ 双刃剑 | 解锁了推送但也放进过断指 |
| **协作标准文档** | ⚠️ 有但执行靠自觉 | 并行 agent 不一定都读 |

## 四、系统性结论与迭代建议

### 结论 1: 体系"活着"但"吃不饱"
基础设施 (resident/GaC/journey) 全部健康, 但**真实业务信号近乎为零** (任务邮件 1 封,
BCOS 未跑)。数字大脑处于"武装完毕、等待敌人"状态。
**迭代**: 信号源扩展比机制加固更紧迫——办公系统 (Seeyon OA) / 日历 / IM 的信号
接入优先级应高于旅程/规则优化。

### 结论 2: 高密度并行是事故之母
144 commits/48h 的密度下, 合并竞态、断指、scope 混杂是**统计必然**而非意外。
**迭代**: (a) 主干限速——PR 合并间隔/冲突检查窗口; (b) auto-bump 机器人统一
推进子仓指针, 禁止作战 agent 手动推 gitlink。

### 结论 3: 静默失败是最大盲区
monitor 的 alert:None + delivered:false 说明**告警链路本身没有自证机制**。
sediment 23% 失败无分类。这类"安静的坏"比报错的坏更危险。
**迭代**: 所有常驻角色加 no-op 心跳 (区别于系统心跳); 失败必须分类计数。

### 优先级排序

| P | 事项 | 理由 |
|---|------|------|
| P1 | monitor 自证心跳 + sediment 失败分类 | 静默失败盲区 |
| P1 | mail 规则黑名单 JetBrains 整域 | 92% 噪音消除 |
| P2 | 子仓 gitlink 推进权收归 auto-bump | 断指根治 |
| P2 | 主干合并限速/静默窗口 | 竞态减少 |
| P3 | BCOS 信号源接入或降级 | 空转处置 |
| P3 | category 白名单防御加固 | 脏数据源 |
