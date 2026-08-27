# eCOS v5 · 产品分析报告

**2026-06-08 · 产品专家视角**

---

## 一、价值体系 — "为什么存在"

### 核心价值主张

```
            ┌──────────────────────────────────────┐
            │  让一个人就能运转一个完整的 AI 操作系统  │
            │  用户 → cockpit → 28 服务自动协作       │
            └──────────────────────────────────────┘
```

eCOS v5 不是一个工具集合，而是一个**个人 AI 操作系统的参考实现**。

### 三层价值递进

| 层级 | 价值 | 解决的问题 |
|------|------|-----------|
| **L4 自我层** | 价值锚点 | 我要做什么？优先级是什么？ → CARDS 目标追踪 |
| **L3 入口层** | 操作效率 | 怎么操作？ → cockpit 23 CLI 命令一键串联全栈 |
| **L2-I0-L1-L0** | 自动化 | 系统自己怎么维护自己？ → 28 服务 100% 健康自愈 |

### 与同类产品的差异化

| 对比维度 | 传统 DevOps | LangChain/LlamaIndex | eCOS v5 |
|---------|------------|---------------------|---------|
| 服务管理 | 手动 Docker/k8s | 不涉及 | 28 服务自动注册/发现/健康 |
| 知识管理 | 无 | RAG 向量库 | KOS + GBrain + Minerva 深度研究 |
| 治理 | CI/CD hooks | 无 | X1-X4 四维贯穿 + OMO 债务 |
| 目标驱动 | 无 | 无 | CARDS 优先级 + Phase 管理 |
| 统一入口 | kubectl/tmux | 各库独立 API | cockpit 单一 CLI |

---

## 二、产品体系 — "是什么"

### 金字塔产品架构

```
        ┌──────────────────────────────────┐
        │         L4 · 自我层 (12 域)        │  ← 用户价值
        │     CARDS + Vault + Personal      │     目标/知识/身份
        │         99% 数据消费               │
        ├──────────────────────────────────┤
        │        L3 · 统一入口 (cockpit)      │  ← 交互层
        │   CLI 23 · MCP 20 · Web :8090     │     唯一操作面
        ├──────────────────────────────────┤
        │      I0 · 服务网格 (agora)         │  ← 集成层
        │   38 MCP · 28 服务 · 60+ 路由      │     服务发现/代理
        ├──────────────────────────────────┤
        │     L2 · 引擎集群 (6 项目)          │  ← 能力层
        │ kairon(16包)+gbrain(67MCP)+omo+   │     知识/治理/决策
        │     metaos+aetherforge+compute    │
        ├──────────────────────────────────┤
        │      L1 · 运行时 (runtime)         │  ← 基础设施层
        │  Matrix·Scheduler·KEI·Cron        │     注册/监控/沙箱
        ├──────────────────────────────────┤
        │       L0 · 协议 (ecos)            │  ← 协议层
        │   MOF 130+ 模型 · SSB 签名         │     根定义/一致性
        └──────────────────────────────────┘
```

### 产品线划分

| 产品线 | 产品 | 定位 | 用户感知 |
|--------|------|------|---------|
| **控制面** | cockpit | 统一驾驶舱 | ⭐⭐⭐ 直接使用 |
| **集成面** | agora | 服务路由器 | ⭐⭐ 间接使用 |
| **引擎面** | kairon 16 包 | AI 工具箱 | ⭐⭐ 按需调用 |
| **治理面** | omo | 项目管理 | ⭐⭐⭐ 规划使用 |
| **决策面** | metaos | 编排引擎 | ⭐ 系统自动 |
| **运行时** | runtime | 守护进程 | ⭐ 系统自动 |
| **协议面** | ecos | 建模语言 | — 基础设施 |

---

## 三、功能体系 — "能做什么"

### MCP 工具拓扑 (按域)

```
bos://memory (记忆域)          bos://analysis (分析域)
├── kos         26 tools       ├── minerva     5 tools
├── kronos       9 tools       ├── ontoderive  5 tools
├── gbrain      67 tools       ├── codeanalyze  已集成
├── sot-bridge   6 tools       └── sophia      8 tools
└── iris         8 tools
                               bos://forge (能力域)
bos://omo (治理域)             ├── forge      70 tools
├── metaos      11 tools       ├── runtime    30 tools
├── eidos        7 tools       └── KEI sandbox
├── omo           已集成
└── protocols     已集成       bos://persona (人格域)
                               └── sot-bridge  已集成
```

**总计: ~280+ MCP 工具，5 域覆盖**

### 能力矩阵

| 能力 | 实现 | 可用性 |
|------|------|--------|
| 知识搜索 | KOS 26 tools (语义+全文) | ✅ |
| 深度研究 | Minerva 5 tools (多轮) | ✅ |
| 本体推导 | Ontoderive 5 tools | ✅ |
| 代码理解 | Codeanalyze AST | ✅ |
| 知识摄取 | Kronos + Eidos 管线 | ✅ |
| 知识持久化 | GBrain 67 tools (PG) | ✅ |
| 工具集市 | Forge 70 tools (install/list) | ✅ |
| 服务发现 | Agora 28 service registry | ✅ |
| 健康监控 | Runtime 15s心跳 + 自愈 | ✅ |
| 安全沙箱 | KEI sys.addaudithook | ✅ |
| 任务编排 | Runtime executor + DAG | ✅ |
| 决策门控 | MetaOS gate + immune | ✅ |
| 项目管理 | OMO debt/phase/goal | ✅ |
| Cron 调度 | 30 L4 定时技能 | ✅ |
| SSB 签名 | ecos signature chain | ✅ |
| MOF 建模 | ecos 130+ YAML models | ✅ |

---

## 四、运营体系 — "怎么运转"

### 日常运营节奏

```
09:00 ─ cockpit workspace context    # 查看本日目标/优先级
09:15 ─ cockpit status                # 检查全栈健康
10:00 ─ Agora health check            # 28 服务自动探测
12:00 ─ L4 scheduled skills (自动)    # GZH/Policy/Vault
14:00 ─ Minerva deep research         # 深度研究任务
16:00 ─ MOF consistency scan          # 模型一致性审计
18:00 ─ CARDS check / Phase review   # 目标进展检查
23:00 ─ Cross-domain sync (自动)     # KOS+GBrain 同步
```

### 自动化运营管线

```
定时技能 (cron_service, 30 jobs)
  │
  ├── 每日 (10): KOS本体 · 跨域同步 · Forge维护 · 平台看板 · 时间线
  ├── 每周一 (8): KOS健康 · Forge报告 · Vault刷新 · 技能审查 · 周报
  ├── 每周一/三/五 (2): 政策简报 · 重点扫描
  ├── 每周三/五 (3): 维护综合 · 周末检查 · 三医汇总
  ├── 每半月/月 (2): EMR报告
  └── 季度 (1): metaos 全局审计

被动监控 (runtime matrix, 15s)
  │
  └── 28 服务 → 心跳 → 过期检测 → auto_heal → OMO 债务注册
```

### 健康指标体系

| 指标 | 当前值 | 目标 | 监控 |
|------|--------|------|------|
| 服务健康率 | 100% | >95% | runtime scheduler |
| 债务健康度 | 100% | >90% | omo debt registry |
| MOF 一致性 | — | 100% | mof-validate |
| 端口冲突 | 3 组 | 0 | port-registry |
| 硬编码路径 | 27→18 处 | 0 | grep audit |

### 治理四平面

```
.omo/_control/     ← 控制面: 人类修改 goals/state
.omo/_truth/       ← 事实面: SSOT tasks/standards
.omo/_knowledge/   ← 知识面: 引用事实面 (相对路径)
.omo/_delivery/    ← 交付面: 运行证据 logs/evidence
```

---

## 五、用户旅程 — "怎么用"

### 旅程 1: 新用户初始化

```
1.  git clone → uv sync (8 项目)
    ↓
2.  ecos-link install → 38 CLI 工具
    ↓
3.  cockpit quickstart → 环境检测
    ↓
4.  agora init → 服务注册引导
    ↓
5.  cockpit dashboard → Web 可视化
    ↓
6.  首次 research → Minerva 深度研究
```

### 旅程 2: 日常研究

```
触发: cockpit research "调研主题"
  ↓
1.  cockpit 接收指令 → L4 CARDS 注入目标上下文
    ↓
2.  agora 路由 bos://analysis/minerva/research
    ↓
3.  minerva 启动深度研究 (5 Super Tools)
    │   ├─ Search → KOS 语义搜索
    │   ├─ Draft  → ontoderive 导出
    │   ├─ Fact-check → sophia 验证
    │   └─ Audit  → eidos 校验
    ↓
4.  gbrain 持久化研究结果 (PG)
    ↓
5.  VaultSink → 自动归档到 @学习进化
    ↓
6.  cockpit 返回完整研究报告
```

### 旅程 3: 系统治理

```
触发: cockpit workspace context
  ↓
1.  OMO 读取当前 Phase 目标
    ↓
2.  CARDS 读取活跃 P0 卡片
    ↓
3.  Agora health → 28 服务 100%
    ↓
4.  MetaOS gate → 决策门控检查
    ↓
5.  Runtime matrix → SOTI 健康评分
    ↓
6.  OMO debt → 债务权重归零确认
    ↓
7.  输出: 阶段总览 + 风险提示 + 建议行动
```

### 旅程 4: 知识沉淀 (自动)

```
Minerva 研究完成
  ↓
1.  minerva/sinks/vault_sink → 自动写入
    ↓
2.  @学习进化/_storage/ → 分类归档
    │   ├── 知识订阅/技术资讯 (ai-tech)
    │   ├── 灵感顿悟 (methodology)
    │   └── 资料库/报告 (industry-report)
    ↓
3.  vault-index-sync (定时) → INDEX.md 更新
    ↓
4.  vault-method-digest (定时) → 方法论语取
    ↓
5.  eureka-weekly-insight → 洞察生成
```

### 旅程 5: 工作区维护

```
每日 04:00 cron 触发
  ↓
1.  kos-daily-ontology-sync → 本体重建
    ↓
2.  kos-kuabu → 跨域同步
    ↓
3.  forge-daily-maintenance → 版本追踪
    ↓
4.  vault-index-sync → 目录维护
    ↓
5.  timeline-daily-sync → 时间线更新
    ↓
09:00 → cockpit context → 可阅读维护简报
```

---

## 六、产品健康度评估

### 优势

| 维度 | 评分 | 说明 |
|------|------|------|
| 架构完整性 | ⭐⭐⭐⭐⭐ | 7 层架构完整落地，5 BOS 域覆盖全栈 |
| 自动化程度 | ⭐⭐⭐⭐ | 28 服务自愈, 30 定时技能, 15s 健康心跳 |
| 统一入口 | ⭐⭐⭐⭐⭐ | cockpit 23 CLI + MCP + Web |
| 知识闭环 | ⭐⭐⭐⭐ | ingest → index → search → persist → vault |
| 工具生态 | ⭐⭐⭐⭐⭐ | 280+ MCP tools, forge 70 tools marketplace |

### 改进空间

| 问题 | 影响 | 优先级 |
|------|------|--------|
| 端口冲突 3 组 | 双服务同时启动即挂 | 🔴 |
| 硬编码路径 18 处 | 环境迁移不可靠 | 🔴 |
| ecos 237MB 未提交变更 | 开发进度阻塞 | 🟡 |
| Makefile 6/8 缺失 | 新成员上手慢 | 🟡 |
| kairon 测试缺口 1,809 | 测试不可信 | 🟡 |
| 8 项目 8 套 venv | 磁盘 2.5GB+ | 🟢 |

---

## 七、战略建议

### 短期 (本月)
1. 解决端口冲突 — 统一分配，消除启动失败风险
2. 提交 ecos 未完成变更 — 解除 MOF 模型开发阻塞
3. 继续 kairon 测试补齐 — 修复 1,809 测试偏差

### 中期 (下季度)
1. cockpit Web Dashboard 完善 — 目前仅 CLI 可用
2. 用户引导体验 — `cockpit quickstart` → 自动安装全栈
3. 移动端接入 — Obsidian Vault + CARDS mobile

### 长期
1. 多人协作 — agora federation
2. 插件市场 — forge marketplace 对外开放
3. 知识公域 — Vault → 可发布方法论
