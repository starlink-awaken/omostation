# STRAT-P81 Agent 执行指令 (兑现期 · 长期交接单)

> Status: **ACTIVE** · SSOT 上位: `.omo/_knowledge/decisions/STRAT-P81-strategic-roadmap.md` (PROPOSED)
> 适用对象: 承接兑现期任一 Stage / 纵贯线的 agentic worker
> 跨度: 2026-08 ~ 2027-06。本文件是**执行指令**, 战略变更去改 STRAT-P81。
> 前序交接单: `.omo/plans/strat-p80-agent-execution-brief.md`（其 §0 启动序列与全局禁令**全部继承**, 不再重抄）

---

## 0. 每次会话启动（继承 P80 §0, 增补两条）

1. 照 P80 brief §0 执行: bootstrap → status → 读 BRIEF → **红线: 有 diff 先 start workflow**（ADR-0203）
2. **增补 · Stage 门禁检查**: 读本文件 §1 进度表 + `phase-scope.yaml::metrics_caliber`,
   确认自己领的任务属于**当前已解锁的 Stage**。上一 Stage 门禁未过 → 不得启动下一 Stage 新建设, 只能做修复/清欠
3. **增补 · 物理口径自检**: 凡产出 G-DEL 指标, 先确认 `env_class`。
   sim 数据填官方 pass 字段 = 最高级违规（ADR-0226 fail-closed, CI 会拒但你不该走到 CI）

## 1. Stage 进度与解锁条件（每 Stage 收尾时由收尾 agent 更新本表）

> **2026-07-24 更新（ADR-0228）**: M1 验收**通过**（用户拍板）, 兑现期正式启动。
> 物理底座**挂起**（用户决策）, 解锁表按"非物理优先"重排如下。

| Stage | 窗口 | 解锁条件 | 状态 |
|-------|------|----------|------|
| S0 入场与清欠 | 2026-08 | S0.1 ✅ S0.2 ✅ · S0.3 挂起（physical-hosts 卡保留） | CLOSED (S0.3 挂起) |
| S1 非物理项（注册中心/调度 harness/故障转移设计） | 2026-08~12 | M1 ✅（ADR-0228 D2）· 仅本地/sim, 只填 `meets_sim_harness` | **OPEN** |
| S1 物理 KPI（G-DEL.1/3 官方达标） | 待硬件 | `reachable_physical_hosts ≥4`（G-DEL.3 ≥2） | BLOCKED（等机器） |
| S2 多角色协作（G-DEL.2b 为 process-local 口径） | 提前至 2026-08~ | ADR-0228 D2 提前解锁 · **G-DEL.2b ✅ ADR-0232** | **OPEN**（运营中） |
| S3 蜂群初步 | 2027 | G-DEL.2b ✅（ADR-0232）+ kill-switch 设计过人类评审 | LOCKED（等 kill-switch） |
| 纵贯线 A/B | 全程 | 无（与 Stage 并行） | OPEN |

### 当前指令（下一个 agent 从这里开始）

**Batch 2 执行中/收尾**: `.omo/plans/strat-p81-batch2-workorder.md`（ADR-0232）。
G-DEL.2b 官方达标 ✅（process-local）。S1 调度 harness C2：**partial** 直至连续 3 wall-clock 天 sim 报告齐。
S3 仍 LOCKED。§F 物理官方达标 / 涌现实装 / 第4-5 角色实装 仍须人类拍板。

---

## Stage 0 · 入场与清欠（立即执行, ~3 周）

### S0.1 M1 提前验收申请 【首推】— profile: governance-agent

- **动作**: 汇总三门禁 evidence（daemon 在线率 / claim 覆盖与主仓冲突 / health+anomaly, 全部指针化引用 SSOT）
  → 写申请卡进 BRIEF Decision Inbox（needs-human, 附 ADR-0210 §Confirmation 逐条对照）
- **验收**: 卡片在 Inbox 可见, 人类拍板后补「M1 验收通过」ADR 并把本文件 §1 表 S1 翻 OPEN
- **禁止**: 未拍板前任何文档宣称「已进入兑现期」

### S0.2 P80 残留 4 卡清偿 — profile: engineering-agent

- **输入**: `.omo/tasks/planned/needs-human-p80-phase45-{tick-timeout,agora-health,task-entropy,bos-stdio}.yaml`
- **动作**: 逐卡实现（tick_timeout=30 / agora :9000 /health / task 文件 477→<200 归档 / bos_stdio→<65% 按既有迁移计划再迁 ~8 服务）
- **验收**: phase45-plan.md 七 endpoint 复测全绿, 复测审计入 audits, 四卡关闭

### S0.3 物理底座 4 机就绪 — profile: engineering-agent（人机协作）

- **依赖（人类）**: macmini 修复上线 · y7000p SSH · macbook(tailscale) SSH 可达
- **动作**: 全节点接入 Tailscale 并把探测/测量脚本 endpoint 切到 tailnet 地址;
  跑 `measure_physical.py --start` 4 主机; 结果回填 `phase-scope.yaml` inventory + audits(evidence)
- **验收**: `reachable_physical_hosts ≥ 4`（脚本探测记录）; G-DEL.1 BLOCKED 解除条件满足
- **禁止**: 手填主机数; 探测不过就如实记录并写 needs-human 卡

## Stage 1 · 多机协作真机化 — profile: engineering-agent 主力

- **S1.1 G-DEL.3**: 先 2 机真机 sync 测量（p99<100ms）达标, 再扩 4 机。测量报告 `env_class=physical_multi_host`
- **S1.2 注册中心**: runtime+agora 节点注册/心跳/能力发现; 假死检出有测试; 设计先立 ADR
- **S1.3 分布式调度 + G-DEL.1**: 真机 harness 常态跑批（foundry cron 接入）, 4 机 success>99% 连续 7 天再宣达标
- **S1.4 故障转移演练**: 拔线演练脚本化, 报告入 audits; 任务零丢失
- **S1.5 节点在线率进健康分**: compass 口径扩展需先过 write-owners（单 writer 原则, ADR-0227）
- **验收整体**: G-DEL.1 + G-DEL.3 官方 meets_gate=true（物理口径）

## Stage 2 · 多角色协作 — profile: engineering-agent + governance-agent

- **S2.1 角色框架**: 角色定义/协作协议 ADR 先行; 3 角色（建议: 工程/治理/审计）跑真实任务
- **S2.2 G-DEL.2b**: 3 角色协作完成率 >95%, 以真实任务批次测量（≥30 任务样本）
- **S2.3 角色记忆共享**: gbrain 跨任务上下文, 隔离边界有测试（角色 A 不可越权读角色 B 私有上下文）
- **S2.4 角色成本进 X3**: 每角色完成率/成本可在 BRIEF 看到

## Stage 3 · 蜂群初步（安全优先）— profile: governance-agent 把关

- **S3.0 前置**: kill-switch + 人类否决通道设计 ADR, **过人类评审后**才可写代码
- **S3.1 涌现检测器**: G-DEL.5b 准确率 >80%; 误报/漏报矩阵入 audits
- **S3.2 集体决策（有限范围）**: 仅任务分派/优先级投票; 每次决策留痕可回放; 人类可一键否决
- **S3.3 cockpit 蜂群面板**: 展示节点/角色/任务流, 数据全部指针化读 SSOT

## 纵贯线 A · KOS/个人大脑 — profile: c2g-agent

- 季度测量写回 `goals/current.yaml::KOS-Q-GROWTH` + evidence audit（沿用既有格式）
- 2027Q1 冲 5000: 不足时先扩 seed 源清单报人类选择, 不自行抓取隐私敏感源
- 2027Q2 图谱 PoC: KOS × gbrain 一条真实查询链路端到端 demo, 立 ADR 记录架构选择

## 纵贯线 B · 治理运营 — profile: governance-agent

- weekly: `compliance --json` 巡检 + P74 沉默 workflow 检查; 异常写卡进 Inbox
- monthly: X3 软门禁月报（环比进 BRIEF）
- 每 Stage 收尾: 战略复盘 vs 本 STRAT, 偏差 >1 个月 → amend ADR + 更新 §1 进度表
- 常态: health < 95 → 立即广播冻结信号（Inbox 卡）, 各 agent 停新建设转修复

---

## 升级与汇报协议（全 Stage 通用）

1. **需人类拍板的事项**（写卡进 BRIEF Inbox, 不得自决）: M1/各 Stage 门禁验收 · G-DEL 达标宣布 ·
   涌现类能力上线 · 预算超 30% · 砍范围 · KOS 新数据源
2. **每 run**: closeout 留完成度; 架构级选择立 ADR 并回填 STRAT-P81 `related`
3. **接力**: 每 Stage 收尾更新 §1 进度表 + 写 handoff 摘要, 下一 agent 从本文件冷启动即可继续

---

*生成: 2026-07-24 · run: 20260724T020855Z-governance-state-mutation-d9220bd6 · 上位 SSOT: STRAT-P81*
