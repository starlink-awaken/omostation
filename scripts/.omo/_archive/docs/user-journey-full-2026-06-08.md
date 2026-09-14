# eCOS v5 · 用户旅程全景分析

**2026-06-08 · 产品视角 · 完整版**

---

## 一、用户画像

eCOS v5 的目标用户是**个人知识工作者 + AI Agent 协同者**。系统同时服务人类和 AI Agent。

| 画像 | 角色 | 核心诉求 | 使用频率 |
|------|------|---------|---------|
| **研究员** | 深度调研者 | Minerva 深度研究 + Vault 知识归档 | 每周 3-5 次 |
| **管理者** | 项目/目标追踪 | CARDS 优先级 + Phase 管理 + OMO 债务 | 每日 1-2 次 |
| **运维者** | 系统健康维护 | Agora 服务健康 + Runtime 自愈监控 | 被动 (自动) |
| **开发者** | 代码维护 | CodeAnalyze AST 理解 + Forge 工具集市 | 按需 |
| **AI Agent** | 自动执行者 | cockpit MCP 20 工具 + metaos 决策门控 | 持续 |
| **生活管理者** | 家庭/工作域管理 | Family + Work-Guozhuan/Work-Weijian 域 | 每周 1-2 次 |

---

## 二、完整场景覆盖矩阵

### 场景分类与覆盖评估

```
场景 · 研究分析
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ 单主题深度研究        minerva 5 Super Tools 全链路
  ✅ 多源知识搜索          kos 26 MCP tools (语义+全文)
  ✅ 事实核查与验证        ontoderive 5 tools + sophia 8 tools
  ✅ 知识图谱推导          eidos 实体关系 + impact 分析
  ✅ 代码理解              codeanalyze AST 扫描
  ✅ 政策/资讯追踪         政策情报简报 (每周一/三/五)
  ⚠️ 批量研究             无工作流自动串联 (需手动逐个执行)
  ❌ 协作研究              无多人共享机制

场景 · 知识管理
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ 自动归档              minerva VaultSink → @学习进化
  ✅ 知识检索              vault_search (7 域) + kos 语义搜索
  ✅ 知识摄取              kronos RSS/GZH/文件 管线
  ✅ 知识索引              vault-index-sync (每日)
  ✅ 方法论萃取            vault-method-digest (每周)
  ✅ 洞察生成              eureka-weekly-insight
  ⚠️ 知识图谱可视化        无图形界面 (仅 CLI 文本)
  ❌ 外部知识源对接        无 API 插件系统

场景 · 项目管理
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ CARDS 目标追踪        P0-P3 优先级 + 6 状态流转
  ✅ OMO Phase 管理        46 阶段追踪
  ✅ 债务管理              omo debits (0 债务健康度)
  ✅ 每日上下文            cockpit context (Phase + Cards + 约束)
  ✅ 定时模板维护          30 scheduled skills 自动化
  ⚠️ 甘特图/时间线         无可视化
  ❌ 外部日历同步          无 iCal/Google Calendar 集成

场景 · 系统治理
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ 服务健康监控          28 服务, 15s 心跳, 100% 健康率
  ✅ 端口注册管理          port-registry + INTERFACE.yaml
  ✅ 安全审计              KEI 沙箱 + Agora JWT + OMO 约束
  ✅ 协议一致性            mof-validate + SSB 签名链
  ✅ 代码冻结检测          code_freeze 自动阻断
  ✅ 断路器保护            Agora circuit breaker (CLOSED/OPEN)
  ⚠️ 告警通知              无邮件/推送 (仅 JSONL 日志)
  ❌ 监控仪表板            cockpit dashboard 未完成

场景 · Agent 协作
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ Agent 上下文注入       metaos cards_context → planning prompt
  ✅ 决策门控              metaos gate (红/黄/绿灯)
  ✅ 免疫监控              immune monitor (3 级: WARN/FREEZE/MELTDOWN)
  ✅ MCP 工具调用          280+ tools 通过 Agora Mesh
  ✅ 任务编排              runtime executor DAG 8 Phase
  ✅ 工具动态加载/卸载      lifecycle manager (idle timeout)
  ⚠️ Agent 记忆持久化      无跨会话状态保持
  ❌ 多 Agent 对话         无群聊/协商机制

场景 · 数据同步
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ 跨域状态同步          kos-daily-ontology-sync (本体 CRUD)
  ✅ 时间线更新            timeline-daily-sync (信号→事件)
  ✅ 索引刷新              vault-index-sync + refresh-knowledge-index
  ✅ 服务发现同步          agora discover + bootstrap
  ✅ BOS URI 注册          136 条路由自动映射
  ⚠️ iCloud 同步           仅单机 (无多设备 sync)
  ❌ 外部 Git 同步          无自动仓库同步

场景 · 开发工具
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ MCP 工具集市          forge 70 tools marketplace
  ✅ 工具安装/卸载          forge market (install/remove/list)
  ✅ 代码分析              codeanalyze AST + 依赖图
  ✅ AST/语法理解          codeanalyze MCP tools
  ⚠️ 插件开发文档           无 SDK 入门指南
  ❌ 可视化依赖图           无 D3/Mermaid 输出

场景 · 个人生活
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ 家庭维护              family-weekly-maintenance (周一 8am)
  ✅ 卫健工作              卫健/良乡 EMR 报告
  ✅ 国转工作              公众号存档 + 内容采集
  ✅ 平台看板              pingtai-kanban (每日更新)
  ⚠️ 健康/运动追踪          无 (个人域空白)
  ❌ 社交/日程管理          无
```

---

## 三、逐旅程详细分析

### 旅程 A: 清晨启动 (每日)

```
触发: 自然 (开机即自动)
  │
  09:00 → cockpit workspace context
  │     ├─ Phase 信息: 当前阶段 46, 目标, 进度
  │     ├─ CARDS 活跃: P0 卡列表 (按优先级排序)
  │     └─ 约束检查: Code Freeze 状态
  │
  09:05 → cockpit status
  │     ├─ Agora 服务: 28/28 healthy ✅
  │     ├─ OMO 债务: 0 debt, 100% 健康
  │     └─ 研究统计: 现有研究报告数
  │
  09:10 → 选择今日 P0 CARDS
  │     └─ cockpit cards → 彩色卡片列表 (P0=红/P1=黄)
  │
  09:15 → 开始第一项研究任务
         └─ cockpit research ask "主题"
```

**体验评分**: ⭐⭐⭐⭐ 流畅，信息密度高，自动化程度高

**缺失**: 无"早安仪表板"一键汇总 (需手动跑 3 个命令)

---

### 旅程 B: 深度研究 (按需)

```
触发: cockpit research ask "DeepSeek V4 架构分析"
  │
  ├─ [0s-3s]   cockpit 接收指令
  │           ├─ OMO Phase 规则注入
  │           └─ CARDS P0 上下文注入
  │
  ├─ [3s-180s] minerva 引擎执行 (三级降级)
  │           ├─ minerva (180s timeout, 首选)
  │           │  ├─ Search → KOS 语义搜索
  │           │  ├─ Draft  → ontoderive 导出
  │           │  ├─ Check  → sophia 验证
  │           │  └─ Audit  → eidos 校验
  │           │
  │           ├─ ollama 降级 (120s timeout)
  │           │  └─ 本地 LLM 代理回复 (⚠️ 降级提示)
  │           │
  │           └─ 缓存降级 (即时)
  │              └─ 纯文本本地回答 (❌ 无真实研究)
  │
  ├─ [研究完成]
  │  ├─ SQLite 持久化 (data.db)
  │  ├─ gbrain Postgres 持久化
  │  └─ vault_sink → @学习进化 归档
  │
  └─ 返回结果 → cockpit CLI 展示
     ├─ 全文 Markdown
     ├─ 来源计数
     ├─ 耗时统计
     └─ 归档路径
```

**体验评分**: ⭐⭐⭐⭐ 完整闭环，降级优雅

**缺失**: 无流式输出 (等待 180s 无中间反馈)

---

### 旅程 C: 系统诊断 (按需)

```
触发: cockpit governance drift-check
  │
  ├─ 端口冲突检测
  │  ├─ 8080: agora vs kairon → ontoderive→8081 ✅
  │  ├─ 9090: ecos vs omo → omo→9091 ✅
  │  └─ 7430: agora vs cockpit → cockpit→8090 ✅
  │
  ├─ 硬编码路径检查
  │  └─ 当前: 27→18 处 (9 处已修复 ✅)
  │
  ├─ 服务健康扫描
  │  ├─ agora health → 28/28
  │  ├─ runtime matrix → SOTI 健康分
  │  └─ OMO debt → 0 债务
  │
  ├─ MOF 一致性
  │  └─ mof-validate → YAML schema 检查
  │
  └─ 输出: 诊断报告 (JSON/Text)
```

**体验评分**: ⭐⭐⭐ 功能全但入口分散 (需跑多个命令)

**缺失**: 无单命令"一键体检" (cockpit 应聚合)

---

### 旅程 D: 知识消费 (日常)

```
触发: cockpit vault search "方法论" --domain vault
  │
  ├─ @学习进化 全目录扫描 (rglob *.md)
  ├─ 关键词匹配 (大小写不敏感)
  ├─ 结果 10 条限制 (防止过载)
  │  ├─ path: 相对路径
  │  ├─ title: 一级标题
  │  └─ snippet: 关键词前后 80 字符
  │
  └─ 跨域搜索: --domain personal/work-weijian 等
```

**体验评分**: ⭐⭐⭐ 搜索可用但较原始

**缺失**: 无全文语义搜索 (KOS 26 tools 未在此使用)

---

### 旅程 E: 自动维护 (透明)

```
后台持续运行 (用户不可见)
  │
  每日 02:00 → vault-index-sync       (INDEX.md 更新)
  每日 03:00 → timeline-daily-sync    (时间线更新)
  每日 04:00 → kos-daily-ontology-sync(本体重建)
  每日 04:00 → kos-kuabu              (跨域同步)
  每日 05:00 → forge-daily-maintenance(版本追踪)
  每日 06:00 → metaos-daily-health    (健康巡检)
  每日 07:00 → pingtai-kanban         (平台看板)
  每日 10:00 → gzh-daily-fetch        (公众号抓取)
  │
  每周一 07:00 → forge-weekly-report
  每周一 08:00 → monday-vault-comprehensive
  每周一 09:00 → kos-weekly-health-check
  每周一 10:00 → eureka-weekly-insight
  每周一 11:00 → kronos-rss-weekly
  每周一 14:00 → skills-weekly-review
  │
  每 15 秒 → runtime scheduler 心跳
  │          ├─ 28 服务健康探测
  │          ├─ 过期检测 → auto_heal
  │          └─ OMO 状态写入
```

**体验评分**: ⭐⭐⭐⭐⭐ 完全透明，零用户干预

---

## 四、场景覆盖率总览

| 场景域 | 覆盖数 | 缺口 | 覆盖率 |
|--------|--------|------|--------|
| 研究分析 | 6/8 | 批量研究, 协作 | 75% |
| 知识管理 | 6/8 | 可视化, 外部对接 | 75% |
| 项目管理 | 5/7 | 甘特图, 日历同步 | 71% |
| 系统治理 | 6/8 | 告警通知, 仪表板 | 75% |
| Agent 协作 | 6/8 | 记忆持久化, 多Agent | 75% |
| 数据同步 | 5/7 | iCloud 同步, Git 同步 | 71% |
| 开发工具 | 4/6 | SDK 文档, 可视化 | 67% |
| 个人生活 | 4/6 | 健康追踪, 社交 | 67% |
| **总计** | **42/58** | **16 缺口** | **72%** |

---

## 五、优先级矩阵 (价值 vs 成本)

```
高价值 ┤  可视化知识图谱      流式研究输出
       │  告警推送通知         一键体检
       │                        ┌────────────────
       │  批量研究工作流         │ 多 Agent 对话
       │  外部 API 插件          │
       │                        │
       │  甘特图/时间线          │ iCloud 同步
低价值 ┤  iCal 日历同步          │ SDK 文档
       │  社交/健康追踪          │ Git 仓库同步
       │
       └──────────────────────────────────────────
         低成本                    高成本
```

**推荐优先实现 (低成本+高价值)**:
1. 流式研究输出 (LLM streaming)
2. 一键体检命令 (`cockpit health --full`)
3. 批量研究工作流 (串联多主题)

---

## 六、竞品对标

| 功能 | eCOS v5 | Notion AI | LangChain | AutoGPT |
|------|---------|-----------|-----------|---------|
| 服务发现 | ✅ 28 服务 100% | ❌ | ❌ | ❌ |
| 知识归档 | ✅ 自动 VaultSink | ✅ 手动 | ❌ | ❌ |
| 目标追踪 | ✅ CARDS + Phase | ✅ 数据库 | ❌ | ❌ |
| Agent 决策 | ✅ MetaOS gate | ❌ | ✅ Agent | ✅ Agent |
| 治理体系 | ✅ X1-X4 四维 | ❌ | ❌ | ❌ |
| 研究深度 | ✅ 5 Super Tools | ⚠️ AI 写作 | ⚠️ RAG | ⚠️ 单链 |
| 多设备 | ❌ | ✅ | ❌ | ❌ |
| 可视化 | ⚠️ 部分 | ✅ | ❌ | ❌ |
| 外部集成 | ⚠️ 有限 | ✅ API | ✅ 生态 | ⚠️ 单工具 |
