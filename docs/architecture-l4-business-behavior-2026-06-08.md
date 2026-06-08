# L4 域业务行为体系 · 战略设计

**2026-06-08 · 长期演进 · 从管理面到业务面**

---

## 一、现状诊断

### 1.1 已完成的

```
✅ 域注册 (DomainRegistry — 21域)
✅ 域类型 (7种 — document/config/tool/...)
✅ KEMS 六面读写 (KemsPlane)
✅ Schema 校验 (KemsValidator)
✅ 健康聚合 (DomainHealth)
✅ 信号总线 (SignalBus)
✅ 域生命周期 (DomainLifecycle)
✅ CLAUDE.md 注入 (ClaudeInjector)
✅ 插件框架 (PluginRegistry + DocumentKemsPlugin)
✅ MCP Server (43 tools)
✅ 全层连接 (L0-L4 + I0 + X1-X4)
```

### 1.2 缺失的

```
❌ 每个域的日常业务流程 (daily_checkin 只在插件中定义，未真正运行)
❌ 跨域协作场景 (研究→归档→信号→CARDS 的自动化链路)
❌ 域特定业务逻辑 (不同域有不同的"业务"——家庭域管日程、工作域管项目)
❌ Agent 可调用的高级业务操作 (当前 MCP tools 是底层 CRUD)
❌ 业务规则引擎 (control-rules.md 是静态文档，未执行)
```

---

## 二、战略设计：四层业务模型

```
┌─────────────────────────────────────────────────────────────┐
│               L4 业务行为四层模型                             │
│                                                             │
│  第4层 · 场景编排 (Scenario Orchestration)                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 跨域协作场景 · 端到端自动化 · 事件驱动链               │    │
│  │ 例: 研究完成→Vault归档→CARDS更新→信号发射→DASHBOARD   │    │
│  └─────────────────────────────────────────────────────┘    │
│                         ↑ 组合                               │
│  第3层 · 业务流程 (Business Process)                         │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 每个域的标准化业务流程 · 可调度 · 可追踪               │    │
│  │ 例: daily_checkin, weekly_review, knowledge_ingest   │    │
│  └─────────────────────────────────────────────────────┘    │
│                         ↑ 组合                               │
│  第2层 · 业务动作 (Business Action)                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 域特定的原子操作 · 有明确输入输出 · 可独立执行          │    │
│  │ 例: state_review, signal_respond, entity_register    │    │
│  └─────────────────────────────────────────────────────┘    │
│                         ↑ 组合                               │
│  第1层 · 基础操作 (Primitive)                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ KEMS 六面读写 · Schema 校验 · 信号发射 · 健康检查      │    │
│  │ ✅ 已完成 (KemsPlane + KemsValidator + SignalBus)     │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 各层现状与目标

| 层 | 现状 | 目标 | 差距 |
|----|------|------|:---:|
| 第1层 基础操作 | ✅ 完成 | — | — |
| 第2层 业务动作 | ⚠️ 14 actions 已定义, 但仅 DocumentDomain | 7 种域类型各有 actions | 6 种类型 × ~5 actions |
| 第3层 业务流程 | ⚠️ 3 workflows 已定义, 未运行 | 每个域有 3-5 个标准流程 | 21 域 × 3 流程 |
| 第4层 场景编排 | ❌ 无 | 5-10 个跨域协作场景 | 全新 |

---

## 三、第2层：每种域类型的业务动作

### 3.1 DocumentDomain (8域) — ✅ 已有 14 actions

```
已有: state_review, memory_update, signal_respond, timeline_log,
      status_evaluate, knowledge_index, knowledge_search, knowledge_categorize,
      entity_register, entity_review, entity_update,
      storage_archive, storage_cleanup,
      cross_domain_sync, cross_domain_notify
```

### 3.2 ConfigDomain (3域) — 🔜 需要新增

```
ConfigDomainPlugin:
  actions:
    config_audit          → 扫描所有配置文件, 检查格式/权限/新鲜度
    config_diff           → 对比两个版本的配置差异
    config_backup         → 备份当前配置到 _archive/
    config_restore        → 从备份恢复配置
    config_validate_all   → 批量 Schema 校验
```

### 3.3 ToolDomain (2域) — 🔜 需要新增

```
ToolDomainPlugin:
  actions:
    tool_inventory        → 扫描所有脚本, 生成清单报告
    tool_health_check     → 检查脚本可执行性 + shebang + 依赖
    tool_deprecation_scan → 检测长期未使用的脚本
    tool_sync_ecos_link   → 与 ecos-link 注册表同步
```

### 3.4 EngineDomain (3域) — 🔜 需要新增

```
EngineDomainPlugin:
  actions:
    engine_health_check   → 检查进程 + 配置 + 日志
    engine_restart        → 安全重启引擎
    engine_config_rotate  → 配置轮转 + 备份
    engine_log_analyze    → 日志异常检测
```

### 3.5 StorageDomain/ModelDomain/WorkspaceDomain — 🔜 需要新增

```
StorageDomainPlugin:
  actions: disk_monitor, cleanup_stale, mount_check

ModelDomainPlugin:
  actions: model_inventory, checksum_verify, model_cleanup

WorkspaceDomainPlugin:
  actions: workspace_index, file_search, stale_project_detect
```

---

## 四、第3层：每个域的标准业务流程

### 4.1 DocumentDomain 标准流程

```
daily_checkin (每日):
  state_review → signal_respond → status_evaluate → timeline_log
  耗时: ~2min · 触发: 定时 (09:00)

weekly_review (每周):
  state_review → memory_update → entity_review → knowledge_index
  → storage_cleanup → status_evaluate → cross_domain_sync
  耗时: ~10min · 触发: 定时 (周一 09:00)

knowledge_ingest (按需):
  knowledge_categorize → knowledge_index → cross_domain_sync → timeline_log
  耗时: ~1min · 触发: minerva 研究完成

domain_audit (按需):
  validate_structure → check_freshness → cross_domain_notify → status_evaluate
  耗时: ~2min · 触发: cockpit domains check
```

### 4.2 域特定流程 (各域不同)

```
@驾驶舱 (cockpit):
  cards_review:    scan_cards → check_compliance → signal_respond → status_evaluate
  cross_domain_scan: aggregate_signals → detect_patterns → notify_affected

@学习进化 (vault):
  knowledge_curation: search_stale → categorize → index → cross_domain_sync
  method_extraction: scan_storage → extract_patterns → create_methodology → signal

@个人 (personal):
  self_review: state_review → entity_review → signal_respond → status_evaluate
  goal_tracking: scan_cards → check_progress → update_state → signal

@家庭生活 (family):
  family_maintenance: entity_review → storage_cleanup → timeline_log
  weekly_planning: state_review → memory_update → signal_respond

@卫健委 (work-weijian):
  project_review: state_review → entity_review → status_evaluate
  report_generation: knowledge_index → cross_domain_sync → timeline_log

@国转中心 (work-guozhuan):
  opportunity_scan: knowledge_search → cross_domain_notify → signal_respond
  policy_tracking: knowledge_categorize → knowledge_index → status_evaluate
```

---

## 五、第4层：跨域协作场景

### 5.1 研究→归档→CARDS 自动化链路

```
触发: minerva 研究完成
  ↓
1. vault: knowledge_categorize → 分类研究结果
2. vault: knowledge_index → 更新知识索引
3. vault: SignalBus.emit("✅", "研究归档完成")
4. cockpit: CardsPlane.check_compliance → 检查相关 CARDS
5. cockpit: SignalBus.emit("ℹ️", "CARDS 状态更新")
6. cockpit: cross_domain_notify → 通知相关域
  ↓
DASHBOARD 自动更新
```

### 5.2 信号→诊断→修复 自动化链路

```
触发: KemsValidator 发现 violation
  ↓
1. 域: SignalBus.emit("⚠️", "Schema violation")
2. cockpit: aggregate_signals → 跨域信号聚合
3. cockpit: detect_patterns → 检测是否为系统性风险
4. cockpit: SignalBus.emit("🔴", "多域 Schema 违规") [如果多域]
5. cockpit: cards_create → 自动创建 DEBT 卡片
6. runtime: l4-domain-health-scan → 定时扫描确认修复
  ↓
DASHBOARD 状态变更
```

### 5.3 周度全局治理 自动化链路

```
触发: 每周一 09:00 cron
  ↓
1. 所有 DocumentDomain: weekly_review 流程
2. cockpit: aggregate_health → 全域健康聚合
3. cockpit: generate_dashboard → DASHBOARD 生成
4. cockpit: cross_domain_notify → 通知所有域
5. cockpit: cards_review → CARDS 状态审查
6. runtime: OMO debt 注册 → 如有违规
  ↓
DASHBOARD 邮件/通知
```

---

## 六、实施路线

### Phase 1 · 补齐业务动作 (2周)

```
目标: 7 种域类型各有 Plugin
├── DocumentKemsPlugin  ✅ 已有
├── ConfigDomainPlugin  🔜 5 actions
├── ToolDomainPlugin    🔜 4 actions
├── EngineDomainPlugin  🔜 4 actions
├── StorageDomainPlugin 🔜 3 actions
├── ModelDomainPlugin   🔜 3 actions
└── WorkspaceDomainPlugin 🔜 3 actions

总计: ~25 个新 actions
```

### Phase 2 · 域特定流程 (2周)

```
目标: 每个 DocumentDomain 有 3-5 个标准流程
├── cockpit: cards_review, cross_domain_scan
├── vault: knowledge_curation, method_extraction
├── personal: self_review, goal_tracking
├── family: family_maintenance, weekly_planning
├── work-weijian: project_review, report_generation
├── work-guozhuan: opportunity_scan, policy_tracking
└── shared: entity_sync, knowledge_share

总计: ~15 个域特定流程
```

### Phase 3 · 跨域场景编排 (2周)

```
目标: 5-10 个跨域协作场景
├── 研究→归档→CARDS 链路
├── 信号→诊断→修复 链路
├── 周度全局治理 链路
├── 域创建→初始化→注册 链路
└── CARDS→Phase→DASHBOARD 链路

总计: ~5 个场景, 每个含 5-8 步
```

### Phase 4 · 自动化执行 (长期)

```
目标: 场景自动触发
├── cron 定时触发 (已完成部分)
├── 信号驱动触发 (SignalBus + detect_patterns)
├── Agent 触发 (MCP tools)
└── 事件驱动触发 (minerva publish → vault archive → CARDS update)

总计: 4 种触发方式
```

---

## 七、关键设计原则

1. **渐进式**: 第1层→第2层→第3层→第4层，逐层构建
2. **插件化**: 每种域类型的业务逻辑封装在 Plugin 中
3. **可编排**: 流程可组合成场景，场景可嵌套
4. **信号驱动**: 所有状态变更通过 SignalBus，形成闭环
5. **Agent 友好**: MCP tools 暴露业务动作，Agent 可组合调用
6. **向后兼容**: 新流程不破坏现有 KEMS 结构
