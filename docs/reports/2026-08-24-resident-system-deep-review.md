# resident 常驻 agent 体系与治理接线深度复盘

> **复盘时间**: 2026-08-24
> **复盘基线**: BET-Y1Q3-T1-10 (resident 体系) 全面接线完成 — F1~F7 全绿, WP-A~I 落地, 9/9 里程碑闭环
> **分析范围**: project-grain, 聚焦 resident 常驻 agent 体系 (ADR-0396) 与其治理接线 (MOF/SGF/BOS/CI/MCP/agent-workflow)
> **定位**: 补充性深度复盘 — 与 `docs/operations/STRATEGIC-ANALYSIS-2026-08-24.md`(通用 9 维度) 互补, 本篇聚焦 resident 体系增量与其架构/战略含义

---

## 0. 北极星定位

resident 体系是用户多常驻智能体成长体系愿景的**运行时载体**: 从"事件中心 → 订阅执行 → 常驻运维 → 共享资源"的自治闭环。它的核心命题不是"再建一套工具", 而是**把运维动作从"人类记得做"迁移到"系统自动做"**——这正是 memory 中多轮复盘反复确认的项目哲学: *encode human memory as machine checks*。

本篇复盘的判断准绳: **任何设计, 如果不能让系统的自治度/可观测度/防腐度三者之一显著提升, 就不是 resident 体系该做的事。**

---

## 1. 场景分析 (Scenario)

### 1.1 resident 体系服务的运营场景

| # | 场景 | 频率 | 入口 | 当前健康度 |
|---|---|---|---|---|
| R1 | 事件自动沉淀为知识 (事件中心→sediment) | 每 2min | cron daemon --role sediment | 🟢 285 runs / 400 草稿 |
| R2 | 监控告警自动转发 (observability→alert) | 每 2min | cron daemon --role monitor + alert | 🟢 水位推进正常 |
| R3 | 决策自动提案 (evolution-agent→decision) | 每 2min | cron daemon --role decision | 🟢 规则可达, 提案 JSON 含 trace_id |
| R4 | 订阅事件触发执行 (rules→execute→pi/multica) | 每 2min | cron daemon --role execute | 🟡 契约已通, 但真实 run 依赖事件到达 |
| R5 | 个人文件信号沉淀 (personal-signals→signals) | 每 5min | cron signals | 🟢 内容摘要水位幂等 |
| R6 | 人类/agent 查看体系状态 (status/roles) | 按需 | cockpit + agora MCP | 🟡 status.py 有 sub 误判缺陷 |

### 1.2 场景分析结论

**核心发现**: resident 体系把通用复盘文档中"S3 (workflow 纪律依赖人类注意力)"的战略风险, 在**运行时领域**上实质化解了——不是通过让 agent 更自觉, 而是通过**常驻 daemon + 规则级订阅**让"该做的运维动作"不再依赖任何 agent 主动想起。

**剩余风险**:
- **R4 执行闭环依赖真实业务事件**: 当前 execute 契约 (run_worker 三方校验) 已 fail-closed, 但"真实事件→真实 run"的端到端频率仍低。这是 resident 体系的**价值证明缺口**, 不是机制缺口。
- **R6 status.py sub 误判**: 活性判定把订阅层 `resident-sub.json` 混入, 导致健康体系误判 degraded (memory 实证)。这是**已知缺陷未修复**, 直接影响人类对体系的信任度。

### 1.3 场景战略建议

1. **R6 优先修复**: status.py 活性判定只认角色水位 `resident-{role}.json` (排除 `resident-sub.json`), 否则人类看 `resident status` 会误以为体系坏了。修复量小, 信任收益大。
2. **R4 价值证明**: 主动构造一个"订阅事件→自动执行"的真实 run 样例 (如"检测到 .omo 水位文件异常→自动清理"), 把 705 run 中 0 个真实 mesh run 的缺口补齐为可演示闭环。
3. **R1-R3 已是稳态**: 事件→知识/告警/决策链路已跑通多日, 进入"减告警噪声"阶段而非新增链路。

---

## 2. 功能分析 (Feature)

### 2.1 resident 功能清单 (实证核对)

| 模块 | 文件 | 功能 | 状态 |
|---|---|---|---|
| 五类角色 | `resident/roles.py` | sediment/decision/execute/monitor/heartbeat | ✅ |
| 路由规则 | `resident/resident-routes.yaml` | event_type+condition→action (schema resident-routes/v1) | ✅ |
| daemon | `resident/daemon.py` | --once --role 单次 tick, 水位续传 | ✅ |
| 事件摄入 | `resident/ingest.py` | bus-foundation events.jsonl 行号水位 | ✅ |
| 信号摄入 | `resident/signals.py` | 个人文件 content-digest 水位 | ✅ |
| 知识沉淀 | `resident/sediment.py` | 事件→知识草稿 | ✅ |
| 决策提案 | `resident/decision.py` | evolution-agent scan→提案 JSON (trace_id) | ✅ |
| 执行接入 | `resident/execute.py` | delivery_binding→pi run_worker | ✅ |
| 告警转发 | `resident/alert.py` | observability→critical/degraded→connector | ✅ |
| 资源检索 | `resident/resources.py` | 六类资源按 kind/capability 检索 | ✅ |
| 角色提升 | `resident/promote.py` | M4.1 草稿→retro 候选聚合 | ✅ |
| CLI | `resident/cli.py` | status/roles/daemon/decision/execute | ✅ |
| agora MCP | `server/tools_resident.py` | resident_status / resident_roles | ✅ (F5) |
| 治理 check | 3 个 CR-RESIDENT 工具 | STATUS/MOF-SYNC/BOS | ✅ (F1/F2) |
| CI 平面 | `ci-surfaces.yaml` | resident 平面登记 | ✅ (F3) |
| workflow 注册 | `_root.yaml` + `_base.yaml` | resident workflow + resident-runtime-observe | ✅ (F4) |
| sgf-policy gate | 3 resident gate | status/mof-sync/bos | ✅ (F6) |
| 文档 | AGENTS.md/CLAUDE.md | agora MCP + bos://resident/* URI | ✅ (F7, PR #2063) |

### 2.2 功能成熟度评估

**成熟 (可复制模式)**:
- **规则级订阅 (WP-C)**: 路由表声明式, AST 受限条件求值 fail-closed。这是 resident 体系**最可复制的架构资产**——任何"事件→动作"场景都可套用。
- **水位幂等 (WP-B/WP-D)**: byte_offset + content-digest 双水位, 截断回退, O(增量) 稳态。工程上非常扎实。
- **双载体执行 (execute.py)**: 批准门 + binding 契约 fail-closed, 支持 pi + multica 双后端。

**不成熟 (缺口)**:
- **执行价值证明**: 真实 mesh run 缺失 (705 run 中 0 个含 StepDispatched 的可用 run)。
- **status.py 健康判定**: sub 误判缺陷未修。
- **无资源生命周期**: 六类资源注册表可检索, 但"资源如何被消费/回收"未闭环。

### 2.3 功能战略建议

1. **把 resident-routes.yaml 提炼为通用模式文档**: 它是"事件驱动自治"的最小可复制范式, 应成为新 agent 体系 (如 BCOS) 的参考实现。
2. **补 status.py 修复 + 单测**: 缺陷已知且定位明确, 属"立单项即可修"级别。
3. **资源生命周期**: 注册表已有 6 类 8+ 资源实例, 下一步应让资源"被消费有记录"而非仅"可检索"。

---

## 3. 用户旅程 (User Journey)

### 3.1 人类运维旅程 (按需查看)

```
T+0s:  make resident-status          → daemon/events/sediment/alert/ledger 5 栏快照
T+2s:  cockpit resident status       → 同源 JSON (bos://resident/status)
T+5s:  (可选) agora MCP resident_status → agent 侧同源查询
T+30s: 发现 degraded → 定位是 status.py 误判还是真实水位过期
```

**评估**: 信息架构完整 (CLI/cockpit/MCP 三入口同源), 但**入口多也意味着判定标准必须唯一**。当前 status.py 的 sub 误判让三个入口同时报 degraded, 反而削弱信任。

### 3.2 Agent 自治旅程 (每 2min 自动)

```
T+0s:  cron 触发 daemon --once --role sediment/decision/execute/monitor/heartbeat
T+0.1s: 读 events.jsonl 行号水位 → 增量处理
T+0.5s: 规则求值 (resident-routes.yaml) → 匹配 → 动作
T+1s:   sediment 写知识草稿 / decision 写提案 / execute 构造 binding
T+2s:  水位写入 watermarks/resident-{role}.json
```

**评估**: 这是 resident 体系**最核心的旅程**——完全无人值守, 每 2min 五角色并行。它把通用复盘中的"S3 社会性纪律"在运行时域转化为**机械执行**。

### 3.3 旅程战略建议

1. **人类旅程**: 修 status.py 后, `make resident-status` 应成为"3 秒读懂体系健康"的单一信任入口。
2. **Agent 旅程**: 补一个"执行闭环可观测"视图 (execute 的 run 列表), 让 R4 的 0 真实 run 问题可视化, 而非埋在契约里。

---

## 4. 体验分析 (Experience)

### 4.1 体验优势

| 优势 | 说明 |
|---|---|
| 三入口同源 | CLI / cockpit / agora MCP 都委派 `omo resident`, 无信息分叉 |
| 水位幂等 | 截断/重启/并发都不重放不丢事件, 运维心智负担小 |
| fail-closed 默认 | 批准门/binding 契约缺失时安全拒绝, 而非静默降级 |
| 规则声明式 | resident-routes.yaml 一处改, 全角色生效 |

### 4.2 体验缺口 (本会话实测)

| 缺口 | 影响 | 建议 |
|---|---|---|
| status.py degraded 误判 | 人类看到健康体系报 degraded, 信任受损 | 排除 sub 水位 (memory 已记录根因) |
| sediment failures 115/400 | 285 runs 中 115 次失败, 无失败明细视图 | alert 侧加失败归类视图 |
| execute 无 run 列表 | R4 价值不可见 | 加 `omo resident execute list` |
| cron 日志分散 | 5 角色 + signals + alert 各一个 log 文件 | 统一日志视图 (可复用 resident status) |

### 4.3 体验战略建议

**短期**: 修 status.py + 给 sediment failures 加失败原因归类。这两项直接决定人类是否信任 resident 体系。

**中期**: execute run 列表视图, 让"执行闭环"从契约层面上升到可见层面。

---

## 5. 目标与愿景对齐 (Goal / Vision Alignment)

### 5.1 与多常驻智能体愿景的对齐度

用户愿景 (memory Q1-Q18 定案): *多输入渠道→事件中心→订阅执行→常驻运维→组织/蜂群*。

| 愿景层级 | resident 体系对应 | 对齐度 |
|---|---|---|
| 输入渠道 | bus-foundation + personal-signals (工作区事件 + 个人文件) | ✅ WP-A/WP-D |
| 事件中心 | events.jsonl + event-ledger 订阅层 | ✅ WP-1 |
| 订阅执行 | resident-routes.yaml 规则级订阅 | ✅ WP-C |
| 常驻运维 | 5 类角色 cron 常驻 | ✅ M4.3 |
| 共享资源 | 六类资源注册表 | ✅ WP-H |
| 组织/蜂群 | 预留 (domain/visibility 分层) | 🟡 未启用 |

### 5.2 三阶段成长路径的对齐

| 阶段 | 定义 | resident 现状 |
|---|---|---|
| 阶段1 知识 | 事件→知识沉淀 | ✅ 400 草稿 |
| 阶段2 能力 | 草稿→retro 候选→能力 | 🟡 promote 已有 (12 主题聚合), 但消费未闭环 |
| 阶段3 真实产出 | 执行→可证伪价值 | 🟡 execute 契约已通, 0 真实 mesh run |

### 5.3 对齐度评估结论

**resident 体系是愿景的"运行时骨骼"**: 它把愿景的 6 层架构全部落地为可运行的机制, 这是 9 个 WP 全部闭环的核心价值。

**最大战略缺口**: 阶段3 (真实产出) 的价值证明。契约 (execute.py 三方校验) 已 fail-closed 完成, 但"真实事件→真实 run→真实推理输出"的端到端样本仍缺。**没有这个样本, 愿景的"可证伪价值"承诺无法兑现。**

### 5.4 战略建议

1. **阶段3 价值样本是下一个里程碑**: 用户已在 pi 载体真实推理上验证过单点 (AetherForge key 打通), 下一个里程碑是把"订阅事件→自动执行→推理输出→结果回写"做成完整闭环样例。
2. **阶段2 消费闭环**: promote 已聚合 12 主题 retro 候选, 应让这些候选被"真实使用" (被引用/被合入), 而非只生成。

---

## 6. 长期运营 (Long-term Operations)

### 6.1 resident 运营指标现状

| 指标 | 值 | 判读 |
|---|---|---|
| 事件总数 | 2124 | 输入流持续 |
| sediment runs | 285 (失败 115) | 运行频繁, 失败率需归类 |
| 知识草稿 | 400 | 持续沉淀 |
| 角色水位 | 5 个全新鲜 (24 Aug 09:06) | 机械执行稳定 |
| 订阅层水位 | 23 Aug 17:52 旧 | 触发 status.py 误判 |
| ledger 链 | sequence 39, chain ok | 事件链完整 |

### 6.2 30 天展望

**无干预**: 
- 事件量继续增长, sediment 草稿持续积累 → **知识膨胀但无索引** (与通用复盘"知识 rot"风险一致)
- status.py 误判持续 → 人类要么忽视 degraded (脱敏), 要么误报故障 (狼来了)
- execute 0 真实 run → 执行模块沦为"契约摆设"

**有干预 (推荐)**:
- 修 status.py + 补 sediment 失败归类 → 人类信任体系
- 做 1 个真实执行闭环样例 → 阶段3 价值证明
- 知识草稿加索引/去重 (复用 memory 的 knowledge-funnel 思路) → 防知识 rot

### 6.3 长期运营战略决策

resident 体系需要**"运行稳态 + 价值证明"双轨**: 
- **稳态轨**: cron 已装, 水位幂等, 契约 fail-closed — 已达成, 只需修 status.py 一个缺陷。
- **价值轨**: 需要主动构造真实执行闭环, 否则体系"健康但无产出证明"。

---

## 7. 运维分析 (Maintenance)

### 7.1 resident 运维模式

| 运维活动 | 频率 | 自动化程度 |
|---|---|---|
| 五角色 daemon tick | 每 2min | 全自动 (cron) |
| 信号摄入 | 每 5min | 全自动 |
| 告警转发 | 每 5min (dry-run) | 半自动 (dry-run 水位推进) |
| 系统健康探测 | 每日 02:10 | 全自动 |
| 状态查看 | 按需 | 手动 (CLI/cockpit/MCP) |

### 7.2 运维陷阱 (本会话实证沉淀)

1. **status.py sub 误判**: 活性判定混入订阅层水位 → 健康误报。
2. **check-resident-bos 假失败**: worktree 子模块未 init → services=0 误报 (memory 实证)。
3. **cron python3 陷阱**: crond PATH 下 python3=3.9 无 datetime.UTC → 脚本须探测 3.11+ 绝对路径 (memory 实证)。
4. **crontab 被并发覆盖**: 其他 agent 装 cron 会清掉 resident 块 → 须重装 (memory 实证)。
5. **mktemp 残留**: `ci-local-failures.XXXXXX.json` 字面量残留阻塞 push (本会话实证)。

### 7.3 运维战略建议

1. **把 status.py 修复纳入下个迭代**: 它是 resident 体系唯一已知的"健康判定"缺陷。
2. **sediment 失败归类**: 115 次失败中, 有多少是事件格式问题 vs 规则求值失败 vs 目标写入失败? 归类后决定是否加自动重试。

---

## 8. 防腐分析 (Anti-Corruption)

### 8.1 resident 体系已建立的防腐机制

| 防腐类型 | 机制 | 状态 |
|---|---|---|
| 路由条件 fail-closed | AST 受限求值, 条件不匹配安全拒绝 | ✅ WP-C |
| 执行批准门 | 非 safe 动作须 --yes, 否则拒绝 | ✅ WP-G |
| binding 契约 | execute.py 读 run 文件构造完整 dict, 失败 fail-closed | ✅ Task #53 |
| 三方校验 | run + mesh + binding 必须一致 | ✅ |
| 订阅层水位隔离 | status.py 应排除 sub (缺陷待修) | 🟡 |
| BOS URI 合规 | 接口必须经 bos://resident/*, 禁止直连内部数据面 | ✅ CR-RESIDENT-BOS-01 |
| MOF 同步 | 角色 SSOT (roles.py) 与 MOF m1 零漂移 | ✅ CR-RESIDENT-MOF-SYNC-01 |
| 活性判定 | 角色水位新鲜 ≤30min 判 healthy | ✅ CR-RESIDENT-STATUS-01 |

### 8.2 未保护的风险面

| 风险 | 现状 | 建议 |
|---|---|---|
| 知识草稿 rot | 400 草稿无索引无去重 | 加知识索引 (复用 knowledge-funnel) |
| 执行产物无审计 | execute run 无列表视图 | 加 execute list |
| sediment 失败静默 | 115 次失败无归类 | alert 加失败归类 |

### 8.3 防腐战略建议

resident 体系的防腐已相当完备 (fail-closed 三件套 + 3 个 CR-RESIDENT check + BOS/MOF 合规)。**最大的防腐缺口不是机制, 而是"缺陷修复滞后"** (status.py) 和"价值盲区" (execute 无 run 列表)。防腐机制应覆盖"缺陷已知就修"的闭环, 而非只覆盖"新违规被拦"。

---

## 9. 约束分析 (Constraints)

### 9.1 resident 体系的硬约束

| 约束 | 来源 | 影响 |
|---|---|---|
| cron 无常驻进程 | 每 tick --once 启动退出 | 活性判据须用水位新鲜度非 pid (memory 实证) |
| 单用户全开放 | Q17 预留 domain/visibility | 资源默认全开放, 分层未启用 |
| 双载体 | pi + multica | 执行契约必须双兼容 |
| macOS-first | launchd/cron | 跨平台迁移成本 |
| Python 3.11+ | datetime.UTC 需要 | crond PATH 陷阱 |

### 9.2 软约束 (文化)

- **fail-closed 优先**: 批准门/binding 缺失时安全拒绝, 而非静默降级。
- **水位幂等**: 任何摄入必须可重放不丢。
- **规则声明式**: 路由/角色配置化, 不改代码。
- **BOS 合规**: 接口必须经 BOS, 不直连内部数据面。

### 9.3 张力点

| 张力 | 当前权衡 | 建议 |
|---|---|---|
| 自治 vs 价值证明 | 体系自转但无真实产出样本 | 主动构造闭环样例 |
| 可观测 vs 误报 | status.py 误报 degraded | 修缺陷, 保持单一信任入口 |
| 沉淀 vs 索引 | 400 草稿无索引 | 加索引防 rot |
| 契约严谨 vs 落地 | execute 三方校验导致 0 真实 run | 在契约内构造合法样例 (Task #53 已铺路) |

---

## 10. 综合评分

| 维度 | 评分 | 说明 |
|---|---|---|
| 场景覆盖 | **9/10** | R1-R6 六场景全落地, R4 价值证明待补 |
| 功能完整度 | **9/10** | 16 项接线全绿, 唯一缺口是 execute list 视图 |
| 用户旅程 | **8/10** | 人类/agent 双旅程清晰, status.py 误判减分 |
| 体验 | **7/10** | 三入口同源优秀, sediment 失败无归类减分 |
| 目标愿景对齐 | **8/10** | 6 层架构全落地, 阶段3 价值证明待补 |
| 长期运营 | **7/10** | 稳态达成, 价值轨未启动 |
| 运维 | **8/10** | 陷阱已全沉淀, status.py 缺陷待修 |
| 防腐 | **9/10** | fail-closed 三件套 + 3 check + BOS/MOF 合规 |
| 约束 | **8/10** | 约束清晰, 双载体兼容已证 |
| **Overall** | **8.0 / 10** | 机制完备, 价值证明是唯一硬缺口 |

---

## 11. 战略建议 (按优先级)

### 🔴 HIGH (立即)

1. **修 status.py sub 误判** (memory 已记录根因 + 修复方向): 活性判定只认角色水位, 排除 `resident-sub.json`。这是唯一影响人类信任的已知缺陷。
2. **构造 1 个真实执行闭环样例**: "订阅事件→execute→pi 推理→结果回写", 把 705 run 中 0 个真实 mesh run 的缺口补齐。Task #53 的 _resolve_run_binding 已铺路, 只需构造合法 work_packet 触发。

### 🟡 MEDIUM (本月)

3. **sediment 失败归类**: 115/400 失败需归类 (事件格式 vs 规则求值 vs 写入), 决定是否自动重试。
4. **execute run 列表**: `omo resident execute list`, 让执行闭环可见。
5. **知识草稿索引**: 400 草稿加索引/去重, 防知识 rot (复用 knowledge-funnel 思路)。

### 🟢 LOW (下季度)

6. **资源消费记录**: 六类资源从"可检索"到"被消费有记录"。
7. **domain/visibility 分层启用**: Q17 预留启用, 多租户/组织场景。

---

## 12. 反模式 (Anti-patterns to Avoid)

| 反模式 | 正确做法 |
|---|---|
| 为 R4 价值证明而放宽 execute 契约 | 契约 fail-closed 是防腐基石, 应构造合法样例而非绕过 |
| 因 status.py 误判而改健康判据为"宽松" | 应修缺陷 (排除 sub), 而非让判据容忍错误 |
| 新增更多角色/链路 (R7/R8...) | 先让 R1-R6 的价值可证, 再扩展 |
| 把 sediment 草稿当"产出证明" | 草稿只是阶段1, 阶段3 需要被消费的产物 |

---

## 13. 最终结论

**resident 体系是本会话交付的"运行时自治骨骼"**: 9 个 WP + F1-F7 全闭环, 五类角色 cron 常驻, 水位幂等, 契约 fail-closed, 16 项接线全绿。它把多常驻智能体愿景的 6 层架构全部落为可运行机制, 也把通用复盘中的"依赖人类注意力"战略风险在运行时域实质化解。

**两个硬缺口**:
1. **status.py 误判** — 机制小但影响人类信任 (立单项即可修)。
2. **阶段3 真实产出样本** — 契约已通但价值未证 (需主动构造闭环样例)。

**判断**: resident 体系的架构质量已到"可对外宣称达成"的水平。下一步不是加更多机制, 而是**证明价值 + 修复信任缺陷**——这符合"少做, 做深"的项目哲学。

— End of review —
