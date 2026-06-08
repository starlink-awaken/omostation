# L4 域业务行为体系 · 跨域场景完整设计

**2026-06-08 · 战略设计 · 含 12 个跨域场景**

---

## 跨域场景全景图

```
                     @驾驶舱 (cockpit)
                     DASHBOARD · CARDS · 跨域信号
                         ↕          ↕
    ┌────────┬───────────┼──────────┼───────────┬────────┐
    │        │           │          │           │        │
    ▼        ▼           ▼          ▼           ▼        ▼
 @学习进化  @个人      @家庭生活   @卫健委    @国转中心  @公共
 Vault    Personal    Family    Work-WJ    Work-GZ   Shared
 知识库   自我管理    生活管理   项目管理   政策跟踪   共享知识
    │        │           │          │           │        │
    └────────┴───────────┴──────────┴───────────┴────────┘
                         │
                    Config/Tool/Storage/Model 域
                    基础设施支撑
```

---

## 场景 1: 研究完成 → 全链自动化

```
触发: minerva 研究完成

Step 1 · vault: knowledge_categorize
  └─ 按主题分类 (ai-tech / methodology / industry-report)

Step 2 · vault: VaultSink 写入
  └─ _storage/ 对应子目录

Step 3 · vault: knowledge_index
  └─ 更新 INDEX.md

Step 4 · cockpit: 检查相关 CARDS
  └─ 搜索是否有与研究主题相关的任务卡片

Step 5 · cockpit: 更新 CARDS 状态
  └─ 如相关 CARDS 状态为 "planned" → 建议更新为 "in_progress"

Step 6 · cockpit: 跨域信号
  └─ SignalBus.emit("✅", "研究归档: {topic}", cross_domain=True)

Step 7 · personal: 自我审查
  └─ 检查研究结果是否影响个人目标

Step 8 · DASHBOARD 更新
  └─ cockpit aggregate_health → 刷新
```

**MCP 调用链**: 8 步, 涉及 3 域, 可通过 `l4_workflow_run("research_to_archive")` 一键触发。

---

## 场景 2: 信号 → 诊断 → 修复 → 验证 闭环

```
触发: KemsValidator 发现 violation (定时或手动)

Step 1 · 域: SignalBus.emit("⚠️", "Schema violation: {detail}")
  └─ 写入域 signals.md

Step 2 · cockpit: aggregate_signals (定时 cron 或手动)
  └─ 聚合所有域最近信号

Step 3 · cockpit: detect_patterns
  ├─ 单域单次 ⚠️ → 信息级
  ├─ 单域连续 ⚠️ → 升级为 🔴
  └─ 多域同时 ⚠️ → 系统性风险 → 紧急通知

Step 4 · cockpit: 自动创建 DEBT 卡片
  └─ CardsPlane → 创建 DEBT-L4-xxx
  └─ 优先级: 单域=P2, 多域=P0

Step 5 · Agent: 收到信号 → 进入域 → 修复
  └─ l4-kernel MCP tools → 修正 Schema 违规

Step 6 · 域: l4_domain_validate → 通过 ✅

Step 7 · cockpit: SignalBus.emit("✅", "Schema violation resolved")

Step 8 · cockpit: 关闭 DEBT 卡片
  └─ CardsPlane → status=resolved

Step 9 · DASHBOARD 更新
```

**自动化程度**: Step 1-4 自动, Step 5 Agent 介入, Step 6-9 自动。

---

## 场景 3: 周度全局治理

```
触发: 每周一 09:00 cron

Step 1 · 所有 DocumentDomain: weekly_review 流程
  ├─ state_review
  ├─ memory_update
  ├─ entity_review
  ├─ knowledge_index
  ├─ storage_cleanup
  └─ status_evaluate

Step 2 · cockpit: aggregate_health
  └─ 聚合所有域健康度

Step 3 · cockpit: generate_dashboard
  └─ 写入 @驾驶舱/_control/DASHBOARD.md

Step 4 · cockpit: cards_review
  └─ 扫描所有 CARDS, 检查逾期/阻塞

Step 5 · cockpit: cross_domain_notify
  └─ 向所有域发射周报信号

Step 6 · personal: goal_tracking
  └─ 检查个人目标与周度进展的偏差

Step 7 · work-weijian/work-guozhuan: project_review
  └─ 项目进展审查

Step 8 · runtime: OMO debt 注册
  └─ 如有违规 → 写入 debt registry

Step 9 · DASHBOARD 最终版
```

**MCP 调用链**: `l4_workflow_run("weekly_governance")` — 9 步, 涉及 7+ 域。

---

## 场景 4: 域创建 → 初始化 → 注册 全链路

```
触发: cockpit domains init 或 MCP l4_domain_create

Step 1 · l4-kernel: DomainLifecycle.create()
  ├─ 创建 KEMS 六面目录
  ├─ 生成标准控制面文件
  └─ 注册到 DomainRegistry

Step 2 · l4-kernel: ClaudeInjector.inject()
  └─ 向 CLAUDE.md 注入 Schema 约束

Step 3 · l4-kernel: SignalBus.emit("ℹ️", "域创建完成")

Step 4 · cockpit: 跨域通知
  └─ SignalBus.emit("ℹ️", "新域注册: {name}", cross_domain=True)

Step 5 · ecos: M1 节点创建
  └─ 在 m1/domain/ 下创建 DOMAIN-{id}.yaml

Step 6 · runtime: L0-registry 更新
  └─ 如需

Step 7 · agora: 服务注册
  └─ 如域有 MCP server

Step 8 · cockpit: CARDS 初始化
  └─ 创建域的初始 CARDS 卡片

Step 9 · DASHBOARD 更新
```

---

## 场景 5: 个人目标 → 工作项目 → 家庭生活 三域对齐

```
触发: 每周日 或 cockpit personal goal_tracking

Step 1 · personal: self_review
  └─ 审查个人目标进展

Step 2 · personal: 读取 P0 CARDS
  └─ 检查个人域 P0 任务

Step 3 · work-weijian: project_review
  └─ 审查工作项目进展

Step 4 · work-guozhuan: project_review
  └─ 审查国转中心项目

Step 5 · family: family_maintenance
  └─ 审查家庭事项

Step 6 · cockpit: cross_domain_scan
  ├─ 检测三域之间是否有时间冲突
  ├─ 检测是否有未对齐的优先级
  └─ 生成对齐建议

Step 7 · cockpit: cards_review
  └─ 全局 CARDS 优先级重排

Step 8 · personal: goal_tracking
  └─ 更新个人目标

Step 9 · DASHBOARD 更新
```

**独特价值**: 这是纯人工难以做到的——同时审视个人、工作、家庭三个域的目标冲突。

---

## 场景 6: 知识消费 → 方法论提取 → 跨域分享

```
触发: Agent 或用户手动

Step 1 · vault: knowledge_search
  └─ 搜索特定主题

Step 2 · vault: knowledge_categorize
  └─ 对搜索结果分类

Step 3 · vault: method_extraction
  ├─ 从 _storage/灵感顿悟/ 中提取可方法论化的经验
  ├─ 从 _knowledge/40-lessons/ 中查找相关教训
  └─ 生成方法论草案

Step 4 · vault: knowledge_index
  └─ 更新索引

Step 5 · shared: knowledge_share
  └─ 将方法论写入 @公共 域

Step 6 · cockpit: cross_domain_notify
  └─ 通知相关域有新方法论

Step 7 · personal: entity_review
  └─ 更新个人知识图谱

Step 8 · DASHBOARD 更新
```

---

## 场景 7: CARDS 驱动的工作流

```
触发: cockpit cards_review 或每日 cron

Step 1 · cockpit: scan_cards (P0)
  └─ 获取所有 P0 卡片

Step 2 · cockpit: 分析卡片依赖
  ├─ 哪些卡片有 parent 关系
  ├─ 哪些卡片跨域
  └─ 哪些卡片阻塞

Step 3 · 为每个 P0 卡片确定执行域
  ├─ domain=meta → cockpit 域
  ├─ domain=family → family 域
  └─ domain=work → work-weijian 域

Step 4 · 对应域: state_review
  └─ 检查域状态是否支持卡片执行

Step 5 · 对应域: signal_respond
  └─ 响应相关信号

Step 6 · cockpit: cards_review 汇总
  └─ 生成今日行动清单

Step 7 · cockpit: SignalBus.emit("ℹ️", "今日 P0 行动清单已生成")

Step 8 · DASHBOARD 更新
```

---

## 场景 8: 政策跟踪 → 机会识别 → 项目启动

```
触发: policy-weekly-brief cron (周一/三/五)

Step 1 · kronos: 抓取政策源 (gov.cn, moe.gov.cn, ...)

Step 2 · work-guozhuan: opportunity_scan
  ├─ 对比新政策与现有项目
  ├─ 识别机会窗口
  └─ 生成机会评估

Step 3 · work-guozhuan: SignalBus.emit("🔴" 或 "ℹ️")
  └─ 如有高价值机会 → 紧急信号

Step 4 · cockpit: cards_review
  └─ 如有新机会 → 创建 CARDS 卡片

Step 5 · cockpit: cross_domain_notify
  └─ 通知相关域 (如涉及卫健委)

Step 6 · work-weijian: project_review
  └─ 评估是否影响现有项目

Step 7 · personal: self_review
  └─ 评估个人是否参与

Step 8 · DASHBOARD 更新
```

---

## 场景 9: 配置变更 → 影响分析 → 回滚准备

```
触发: ConfigDomain config_audit 或手动

Step 1 · ai-config/agents-config: config_audit
  └─ 扫描所有配置文件

Step 2 · 域: config_diff
  └─ 对比当前与上次备份

Step 3 · 域: config_backup
  └─ 变更前自动备份

Step 4 · cockpit: cross_domain_scan
  └─ 分析配置变更的影响范围
  ├─ 哪些域引用了这个配置
  └─ 哪些流程会受影响

Step 5 · 受影响域: state_review
  └─ 检查域状态

Step 6 · cockpit: SignalBus.emit("⚠️", "配置变更: {detail}")
  └─ 跨域通知

Step 7 · DASHBOARD 更新
```

---

## 场景 10: 存储告警 → 清理 → 归档

```
触发: StorageDomain disk_monitor 或定时

Step 1 · shareddisk/sharedwork: disk_monitor
  └─ 检查磁盘使用率

Step 2 · 域: SignalBus.emit("⚠️" 或 "🔴")
  └─ 使用率 >80% → ⚠️, >95% → 🔴

Step 3 · 所有 DocumentDomain: storage_cleanup
  ├─ 清理 _storage/ 过期文件
  ├─ 归档 _archive/ 旧版本
  └─ 压缩大文件

Step 4 · cockpit: aggregate_health
  └─ 更新存储健康度

Step 5 · DASHBOARD 更新
```

---

## 场景 11: Agent 会话 → 上下文注入 → 执行 → 归档

```
触发: Agent 启动新会话

Step 1 · cockpit: workspace_context
  ├─ Phase 目标
  ├─ P0 CARDS
  ├─ 最近 signals
  └─ DASHBOARD 摘要

Step 2 · metaos: cards_context
  └─ P0 卡片注入 Agent prompt

Step 3 · Agent: 执行任务
  └─ 通过 l4-kernel MCP tools 操作域

Step 4 · 域: 记录操作
  ├─ signals.md: 操作信号
  ├─ TIMELINE.md: 时间线事件
  └─ STATE.md: 状态更新

Step 5 · cockpit: 会话结束
  ├─ cards_review: 更新 CARDS
  ├─ aggregate_health: 更新健康度
  └─ SignalBus.emit("ℹ️", "会话完成")

Step 6 · DASHBOARD 更新
```

---

## 场景 12: 灾难恢复 → 域重建 → 数据恢复

```
触发: 域数据丢失或 corruption

Step 1 · l4-kernel: DomainLifecycle.validate()
  └─ 发现域结构异常

Step 2 · l4-kernel: SignalBus.emit("🔴", "域结构异常: {domain}")

Step 3 · l4-kernel: 从模板重建 KEMS 骨架
  └─ init_domain_kems() — 仅创建缺失文件, 不覆盖已有

Step 4 · l4-kernel: ClaudeInjector.inject()
  └─ 重新注入 Schema 约束

Step 5 · l4-kernel: DomainLifecycle.validate()
  └─ 确认修复

Step 6 · l4-kernel: SignalBus.emit("✅", "域结构恢复完成")

Step 7 · cockpit: cross_domain_notify
  └─ 通知相关域

Step 8 · DASHBOARD 更新
```

---

## 场景依赖矩阵

```
场景          涉及域数  自动化程度  Agent介入  MCP tool
─────────────────────────────────────────────────────
1. 研究→归档    3        高         否         8步
2. 信号→修复    2+       中         是         9步
3. 周度治理     7+       高         否         9步
4. 域创建       4+       高         否         9步
5. 三域对齐     4        中         是         9步
6. 知识消费     3        中         是         8步
7. CARDS驱动   3+       高         否         8步
8. 政策跟踪     4        中         是         8步
9. 配置变更     2+       中         是         7步
10. 存储告警    3+       高         否         5步
11. Agent会话   3+       高         是         6步
12. 灾难恢复    1+       高         否         8步
```

---

## 实施优先级

| 优先级 | 场景 | 理由 |
|:---:|------|------|
| P0 | 场景 11 (Agent 会话) | 每次 Agent 调用都触发, 最高频 |
| P0 | 场景 3 (周度治理) | 已有时基, 只需编排 |
| P0 | 场景 1 (研究→归档) | minerva 已有触发点 |
| P1 | 场景 2 (信号→修复) | 核心治理闭环 |
| P1 | 场景 7 (CARDS 驱动) | 目标驱动核心 |
| P1 | 场景 4 (域创建) | 域生命周期完整性 |
| P2 | 场景 5/6/8/9/10/12 | 锦上添花 |
