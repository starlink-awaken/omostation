# L4 Kernel MCP Server · 完整评估与设计方案

**2026-06-08 · 深度评估 · 19域覆盖 · 交互确认 · 约束闭环**

---

## 一、复杂度评估

### 1.1 问题规模

```
19 域 × 7 种类型 × 每域 N 个操作 = 真实复杂度

DocumentDomain (8域):
  _control/  9 文件 (STATE/MEMORY/signals/TIMELINE/STATUS/control-rules/PLANE_INDEX/CLAUDE.md/决策日志)
  _entities/ N 个实体文件
  _knowledge/ N 个知识文件
  _storage/ N 个资料文件
  _archive/ N 个归档文件
  CARDS/ (cockpit) 65 个卡片

ConfigDomain (3域):
  ~/.ai, ~/.agents, SharedConf → 各 N 个 YAML/JSON 文件

ToolDomain (2域):
  ~/bin, ~/ToolBox → 各 N 个脚本

StorageDomain (1域): df -h 磁盘操作
ModelDomain (2域): 模型文件 + SHA256
EngineDomain (2域): 进程 + 配置 + 日志
WorkspaceDomain (1域): 文件索引
```

**保守估计: 1000+ 个可操作实体**

### 1.2 核心挑战

| 挑战 | 复杂度 | 说明 |
|------|:---:|------|
| 域类型差异 | 中 | 7 种类型需要不同的读写策略 |
| 文件格式差异 | 中 | YAML frontmatter / 纯 Markdown / JSON / 二进制 |
| 交互确认 | **高** | 某些操作需要用户确认（修改 MEMORY/STATE/删除） |
| 内容理解 vs 结构化操作 | **高** | Agent 需要理解文件内容才能操作，不是简单 CRUD |
| 工作流编排 | 高 | 多步操作需要事务性保证 |
| 约束执行 | 中 | Schema 校验 + 信号发射 + 合规检查 |

### 1.3 关键洞察：不是"CRUD API"，是"领域语言"

```
错误思路: l4_state_read(domain) → 返回 YAML → Agent 解析 → Agent 修改 → l4_state_write(domain, data)
问题: Agent 需要理解 STATE.md 的语义才能正确修改

正确思路: l4_state_get_section(domain, "活跃事项") → 返回结构化数据
         l4_state_update_section(domain, "活跃事项", new_data) → 自动 merge
问题: 这需要预先定义每个域 STATE.md 的 section 结构

折中方案: Agent 通过 MCP 读取文件内容（结构化）→ 理解 → 修改 → MCP 写入（带校验）
         MCP 不做语义理解，只做结构化读写 + 校验
```

**这是 MCP Server 的正确定位**: 提供结构化的安全读写接口，语义理解由 Agent 完成。

---

## 二、交互确认模型

### 2.1 哪些操作需要确认

```
不需要确认 (安全操作):
  ✅ 读取任何文件 (l4_*_read)
  ✅ 搜索 (l4_search)
  ✅ 列出 (l4_*_list)
  ✅ 校验 (l4_validate)
  ✅ 健康检查 (l4_health)
  ✅ 发射 ℹ️ 信号 (l4_signal_emit ℹ️)

需要确认 (中等风险):
  ⚠️ 修改 STATE.md (l4_state_update)
  ⚠️ 修改 MEMORY.md (l4_memory_update)
  ⚠️ 修改 STATUS.md (l4_status_update)
  ⚠️ 追加时间线 (l4_timeline_append)
  ⚠️ 修改控制规则 (l4_rules_update)

必须确认 (高风险):
  🔴 删除实体 (l4_entity_delete)
  🔴 修改 CARDS (l4_cards_update)
  🔴 修改配置域文件 (l4_config_write)
  🔴 发射 🔴 信号 (l4_signal_emit 🔴)
  🔴 批量操作 (l4_batch_*)
```

### 2.2 确认机制设计

```
方案 A: MCP tool 返回 confirmation_required → Agent 再次调用 confirm
方案 B: MCP tool 接受 --confirm 参数 → 一次调用完成
方案 C: MCP tool 接受 --dry-run → 预览变更 → 确认 → 执行

推荐: 方案 A (安全) + 方案 C (预览)

示例:
  Agent: l4_state_update("vault", data)
  MCP:   返回 { status: "confirmation_required",
                 preview: { changes: [...], affected_files: [...] },
                 confirmation_id: "abc-123" }

  Agent: l4_confirm("abc-123")
  MCP:   返回 { status: "ok", written_files: [...] }
```

### 2.3 交互流程图

```
Agent 意图: 更新 @学习进化 STATE.md

  l4_state_read("vault")
  → 返回当前 STATE (结构化)

  Agent 理解 → 构建变更

  l4_state_update("vault", new_data, dry_run=true)
  → 返回 { preview: { before/after diff }, confirmation_id }

  Agent 展示 diff 给用户 / 自行判断

  l4_confirm(confirmation_id)
  → 执行写入
  → Schema 校验
  → 发射信号: "✅ STATE.md updated"
  → 返回 { status: "ok" }
```

---

## 三、完整 MCP Tool 矩阵

### 3.1 按域类型分类 (42 tools)

```
═══════════════════════════════════════════════════════════════
DocumentDomain 操作 (20 tools)
───────────────────────────────────────────────────────────────
读 (7):
  l4_domain_state_read(domain)           → STATE.md 结构化
  l4_domain_memory_read(domain)          → MEMORY.md 结构化
  l4_domain_signals_list(domain, limit)  → 信号列表
  l4_domain_timeline_list(domain, limit) → 时间线
  l4_domain_status_read(domain)          → 三态判定
  l4_domain_rules_read(domain)           → 控制规则
  l4_domain_entrypoint_read(domain)      → CLAUDE.md

写 (7):
  l4_domain_state_update(domain, data, dry_run)     → 确认流程
  l4_domain_memory_update(domain, data, dry_run)    → 确认流程
  l4_domain_signal_emit(domain, type, msg)          → 信号发射
  l4_domain_timeline_append(domain, event)          → 追加事件
  l4_domain_status_update(domain, status, reason)   → 确认流程
  l4_domain_rules_update(domain, rules, dry_run)    → 确认流程
  l4_domain_entrypoint_inject(domain)               → Schema 注入

搜索/校验 (6):
  l4_domain_search(domain, keyword, max)            → 全文搜索
  l4_domain_validate(domain)                        → Schema 校验
  l4_domain_freshness(domain)                       → X2 新鲜度
  l4_domain_kems_check(domain)                      → KEMS 面完整性
  l4_domain_files_list(domain, plane, pattern)      → 文件列表
  l4_domain_file_read(domain, path)                 → 读取任意文件

═══════════════════════════════════════════════════════════════
CARDS 操作 (5 tools)
───────────────────────────────────────────────────────────────
  l4_cards_list(domain, priority, status)           → 卡片列表
  l4_cards_get(card_id)                             → 卡片详情
  l4_cards_check(card_id)                           → 合规检查
  l4_cards_search(keyword)                          → 全文搜索
  l4_cards_update(card_id, data, dry_run)           → 确认流程

═══════════════════════════════════════════════════════════════
ConfigDomain 操作 (4 tools)
───────────────────────────────────────────────────────────────
  l4_config_list(domain)                            → 配置列表
  l4_config_read(domain, path)                      → 读取配置
  l4_config_write(domain, path, data, dry_run)      → 确认流程
  l4_config_validate(domain, path)                  → Schema 校验

═══════════════════════════════════════════════════════════════
ToolDomain 操作 (3 tools)
───────────────────────────────────────────────────────────────
  l4_tools_list(domain)                             → 脚本列表
  l4_tools_check(domain, name)                      → 可执行检查
  l4_tools_register(domain, name, path)             → 注册脚本

═══════════════════════════════════════════════════════════════
StorageDomain 操作 (2 tools)
───────────────────────────────────────────────────────────────
  l4_storage_usage(domain)                          → df -h
  l4_storage_mount_check(domain)                    → 挂载状态

═══════════════════════════════════════════════════════════════
ModelDomain 操作 (2 tools)
───────────────────────────────────────────────────────────────
  l4_models_list(domain)                            → 模型列表
  l4_models_checksum(domain, path)                  → SHA256

═══════════════════════════════════════════════════════════════
EngineDomain 操作 (3 tools)
───────────────────────────────────────────────────────────────
  l4_engine_process_check(domain, name?)            → 进程检查
  l4_engine_config_read(domain, path?)              → 配置读取
  l4_engine_logs_read(domain, path, lines)          → 日志读取

═══════════════════════════════════════════════════════════════
全域操作 (3 tools)
───────────────────────────────────────────────────────────────
  l4_domains_list(type?)                            → 域列表
  l4_health(domain?)                                → 健康聚合
  l4_dashboard()                                    → 全域 DASHBOARD
```

**总计: 42 个 MCP tools，覆盖 19 域全部操作**

### 3.2 覆盖场景矩阵

```
场景                    Agent 直读目录   MCP 工具      覆盖率
─────────────────────  ──────────────  ────────────   ─────
查看域状态              ✅              l4_domain_state_read   100%
查看最新信号            ✅              l4_domain_signals_list 100%
搜索知识库              ⚠️ (需grep)     l4_domain_search       100%
更新 STATE              ⚠️ (可能违规)   l4_domain_state_update 100%
发射信号                ⚠️ (格式不一)   l4_domain_signal_emit  100%
Schema 校验             ❌ (无)         l4_domain_validate     100%
健康检查                ❌ (无)         l4_health              100%
CARDS 操作              ⚠️ (可能违规)   l4_cards_*             100%
配置读写                ⚠️ (格式风险)   l4_config_*            100%
跨域搜索                ❌ (需手动)     l4_domain_search        100%
全域 DASHBOARD          ❌ (无)         l4_dashboard           100%
信号模式检测            ❌ (无)         l4_health              100%
确认/回滚               ❌ (无)         dry_run + confirm      100%
───────────────────────────────────────────────────────────────
综合覆盖率:                                    95%+ ✅
```

---

## 四、工作流引擎

### 4.1 预定义工作流

```python
# l4_kernel/workflows.py (新增)

L4_WORKFLOWS = {
    # ── 每日启动工作流 ──
    "daily_startup": {
        "name": "每日启动",
        "steps": [
            {"tool": "l4_dashboard", "description": "获取全域 DASHBOARD"},
            {"tool": "l4_domain_signals_list", "domain": "cockpit", "limit": 10},
            {"tool": "l4_cards_list", "priority": "P0", "description": "查看今日 P0 任务"},
            {"tool": "l4_health", "description": "全域健康检查"},
        ],
    },
    
    # ── 域审计工作流 ──
    "domain_audit": {
        "name": "域审计",
        "steps": [
            {"tool": "l4_domain_validate", "domain": "{{domain}}"},
            {"tool": "l4_domain_freshness", "domain": "{{domain}}"},
            {"tool": "l4_domain_kems_check", "domain": "{{domain}}"},
            {"tool": "l4_domain_signals_list", "domain": "{{domain}}", "limit": 20},
        ],
    },
    
    # ── 研究→归档工作流 ──
    "research_to_vault": {
        "name": "研究结果归档",
        "steps": [
            {"tool": "l4_domain_state_read", "domain": "vault", "description": "读取当前状态"},
            {"tool": "l4_domain_search", "domain": "vault", "keyword": "{{topic}}"},
            {"tool": "l4_domain_state_update", "domain": "vault", "dry_run": True},
            {"tool": "l4_domain_signal_emit", "domain": "vault", "type": "✅", "msg": "研究归档: {{topic}}"},
        ],
    },
    
    # ── 域创建工作流 ──
    "domain_create": {
        "name": "创建新域",
        "steps": [
            {"tool": "l4_domains_list", "description": "检查域是否已存在"},
            # 创建域需要人工确认路径
            {"action": "confirm", "message": "确认创建域 {{name}} 在路径 {{path}}?"},
            {"tool": "l4_domain_init", "name": "{{name}}", "type": "{{type}}", "path": "{{path}}"},
            {"tool": "l4_domain_entrypoint_inject", "domain": "{{id}}"},
            {"tool": "l4_domain_signal_emit", "domain": "{{id}}", "type": "ℹ️", "msg": "域创建完成"},
        ],
    },
    
    # ── CARDS 合规检查工作流 ──
    "cards_compliance": {
        "name": "CARDS 合规检查",
        "steps": [
            {"tool": "l4_cards_list", "description": "获取活跃卡片"},
            {"tool": "l4_cards_check", "card_id": "{{card_id}}"},
            {"tool": "l4_domain_signal_emit", "domain": "cockpit", "type": "{{signal_type}}", "msg": "{{msg}}"},
        ],
    },
}
```

### 4.2 工作流执行

```
Agent 调用:
  l4_workflow_run("daily_startup")

MCP 返回 (流式):
  Step 1/4: l4_dashboard... ✅
    { dashboard_data }
  Step 2/4: l4_domain_signals_list(cockpit)... ✅
    3 条最近信号
  Step 3/4: l4_cards_list(P0)... ✅
    5 个 P0 卡片
  Step 4/4: l4_health... ✅
    健康率 84.2%

  → 返回完整报告
```

---

## 五、约束闭环

### 5.1 三层约束模型

```
┌──────────────────────────────────────────────────────────┐
│  第一层: MCP 入口约束 (强制)                              │
│  - 所有写操作必须经过 l4_*_update 工具                   │
│  - 自动注入 frontmatter 标准字段                         │
│  - 自动补时间戳                                          │
│  - dry_run 预览 → confirm 确认 → 执行                   │
├──────────────────────────────────────────────────────────┤
│  第二层: Schema 校验 (写入时)                             │
│  - 每次写入后自动运行 KemsValidator                      │
│  - 发现 violation → 写入 signals ⚠️                     │
│  - 严重 violation → 拒绝写入 + 返回修复建议              │
├──────────────────────────────────────────────────────────┤
│  第三层: 事后扫描 (定时)                                  │
│  - l4-scheduler 定时扫描                                 │
│  - 发现偏离 → signals 信号 → Agent 自愈                  │
│  - 持续偏离 → 升级 STATUS ALERT → OMO debt              │
└──────────────────────────────────────────────────────────┘
```

### 5.2 约束力对比

```
操作方式              约束力    Schema校验   确认流程   信号记录   回滚能力
───────────────────── ──────── ─────────── ────────── ────────── ────────
Agent 直读目录          ⭐        ❌           ❌          ❌          ❌
CLAUDE.md 引导          ⭐⭐      ❌           ❌          ❌          ❌
l4-kernel Python API    ⭐⭐⭐⭐   ✅           ❌          ⚠️手动      ❌
l4-kernel MCP Server    ⭐⭐⭐⭐⭐ ✅           ✅          ✅自动      ✅dry_run
```

---

## 六、实施计划

| Phase | 内容 | 文件 | 预估 |
|-------|------|------|------|
| P1 | `mcp_server.py` 核心 (42 tools) | l4_kernel/mcp_server.py | 500行 |
| P2 | `workflows.py` 工作流引擎 | l4_kernel/workflows.py | 200行 |
| P3 | `confirm.py` 确认/回滚机制 | l4_kernel/confirm.py | 100行 |
| P4 | cockpit 集成 (MCP proxy) | cockpit 配置 | 50行 |
| P5 | 测试 (每个 tool 1-2 个 test) | tests/ | ~60 tests |

**预估总代码量: ~1000 行 · 60+ tests · 覆盖 19 域 · 42 tools · 6 工作流**
