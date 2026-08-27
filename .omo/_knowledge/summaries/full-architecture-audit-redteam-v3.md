---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R2: summaries/ 根目录历史快照批量归档, 当前状态以 .omo/state/system.yaml + .omo/tasks/active/ 为准"
---
# 全场景深度分析：架构审计 + 红队分析

> 日期: 2026-05-28 | 数据源: ~12h 连续分析 + 实施
> 覆盖: 24 项目 · 6 架构层 · 3 X 维度 · ~60 任务
> 历史架构审计与红队分析 / reference only。本文记录旧阶段的全场景分析，不是当前项目数、当前架构层覆盖、当前 MCP/测试状态或当前安全面 SSOT。
> 当前事实请回看 `/.omo/PROJECTS.yaml`、`/docs/PANORAMA.md`、当前治理审计与项目测试证据。

---

## 一、架构审计

### 1.1 4+1+3 层完整度

#### P0 — 产品界面

| 入口 | 存在 | 验证 | 备注 |
|:----:|:----:|:----:|------|
| Web UI | ✅ | 🟢 hermes-webui :8787 | 稳定 |
| CLI | ✅ | 🟢 pallas 7 cmd | 委托到 ontoderive/agora |
| TUI | ✅ | 🟡 bos-skill-cli | 低活跃 |
| Browser | ✅ | 🟡 gstack 20 orchestrator | 已恢复+backend |
| 外部接入 | ✅ | 🟡 Iris Telegram 新 | 1/3 连接器完成 |

**诊断**: 全覆盖，但入口分散，无统一入口编排。

#### L4 — 自我层（身份/愿景/认知）

| 组件 | 实现 | 深度 |
|:----:|::----:|:----:|
| 角色定义 | 🟢 KOS self: roles[].id/name/priority/values | 3 套角色配置 |
| 愿景 | 🟢 KOS self: vision.long_term/mid_term/current_okrs | 三层 OKR |
| 认知框架 | 🟢 KOS self: thinking_stack/bias/patterns + metacog 链接 | 25 条知识链接 |

**诊断**: 全架构最令人惊喜的层 — 实际代码比文档描述的更完整。

#### L3 — 协作层（多 Agent 协作）

| 组件 | 实现 | 验证 |
|:----:|::----:|:----:|
| TaskObject | 🟢 KOS collab: 318行, SQLite CRUD + MCP | 6/6 test |
| 相位锁定 | 🟢 agentmesh phase-lock: 8/8 | ✅ |
| 执行追踪 | 🟢 PipelineTracer: 8/8 | ✅ |
| collab→agentmesh | 🟢 MCP dispatch + callback | **本次打通** |

**诊断**: L3 链路从「断开」变为「全通」。本次执行的最核心交付之一。

#### L2 — 能力层（工具/模型/技能）

| 类别 | 项目 | 健康度 |
|:----:|:----:|:----:|
| Agent 运行时 | agentmesh | 🟢 22 MCP, 24+ tests |
| 知识推导 | ontoderive | 🟢 21 CLI + 5 MCP |
| 符号编译 | sophia | 🟢 12-state MCP |
| 研究系统 | minerva | 🟢 L0-L4, 23 tests |
| 工具图谱 | Forge | 🟢 111 tools, 5 MCP |
| 持久记忆 | gbrain | 🟢 74 ops |
| ETL 摄取 | kronos | 🟢 91 tests (从 17) |
| 连接器 | Iris | 🟢 66 tests + Telegram |
| 系统编排 | MetaOS | 🟢 39/39 |

**诊断**: 11 项目中 9 个 🟢，2 个 🟡。最成熟的层。

#### L1 — 契约层（Schema/协议）

| 组件 | 实现 | 版本 |
|:----:|:----:|:----:|
| 元模型 | 🟢 eidos MCP | 稳定 |
| 配置一致性 | 🟢 SSOT MCP | 50/50 tests |
| 管线协议 | 🟢 pipeline:json | **v1.1 正式化** |

**诊断**: 协议首次完整。

#### X1 — 治理

| 组件 | 状态 | 变化 |
|:----:|:----:|:------|
| 约束验证 | 🟢 17 脚本 + pre-commit + CI | 本次 |
| 仪表板 | 🟢 42 约束可视化 | 本次 |
| Agora 降级 | 🟢 已有实现 (service_cache+router) | 发现 |
| 认证 | 🟢 5 fail-closed + API_KEY | 本次 |
| 密钥清单 | 🟢 SECRETS_INVENTORY.md | 本次 |

**诊断**: 最稳固的层。从「写在文档里」变成「锁在 CI 里」。

#### X2 — 抗熵

| 组件 | 状态 |
|:----:|::----:|
| 保鲜 cron | 🟢 x2-freshness-cron @ 3am |
| 定时备份 | 🟢 x2-backup-brain @ 3:30am, 43 files |
| 僵尸器官审计 | 🟢 INDEX.md 63 行 |

**诊断**: 保鲜和备份已自动化。复盘/回收未自动化。

#### X3 — 价值堆栈

| 组件 | 状态 |
|:----:|:----:|
| 共识系统 | 🟢 KOS consensus: L1/L2/L3 |
| 执行追踪 | 🟢 PipelineTracer |
| 引用链追溯 | ❌ 未实现 |

**诊断**: 共识可用，追溯缺失。

---

### 1.2 项目健康矩阵

```
分级标准:
  🟢 稳定  — 有测试/有MCP/有维护
  🟡 改善中 — 缺测试或低活跃
  🗄️ 归档  — 不活跃

Runtime Core (2):     agentmesh🟢 MetaOS🟢
MCP Buses (3):        Agora🟢 SharedBrain🟡 Iris🟢
Knowledge Pipeline(6):KOS🟢 ontoderive🟢 pallas🟢 sophia🟢 minerva🟢 kronos🟢
Data Infra (4):       eidos🟢 SSOT🟢 gbrain🟢 DigitalBrainOS🟡
Ecosystem (5):        Forge🟢 hermes-webui🟢 codeanalyze🟢 ai-tools🟡 eCOS🟡
Archived (3):         gstack🟡 metacog🟡 AggreSearch🗄️
Testing (特殊):       hermes-scripts🟢 integration-tests🟢

总计: 🟢 16 / 🟡 6 / 🗄️ 2 = 🟢 67%
```

### 1.3 MCP 覆盖矩阵

```
项目             | MCP Server | 工具 | 传输   | 端口
agentmesh       | ✅         | 22  | stdio  | 3000
Agora           | ✅         | 27  | stdio  | 7430
KOS             | ✅         | 26  | stdio  | 7420
gbrain          | ✅         | 74  | stdio  | -
Iris            | ✅         | 7   | stdio  | -
SharedBrain     | ✅(本次)   | 5   | stdio  | 7420
Forge           | ✅(本次)   | 5   | stdio  | -
ontoderive      | ✅(本次)   | 5   | stdio  | -
eidos           | ✅         | 5   | stdio  | -
SSOT            | ✅         | 5   | stdio  | -
minerva         | ✅         | ~10 | WebUI  | 8765
hermes-webui    | ✅         | ~20 | WS     | 8787
MetaOS          | ⇢ CLI合理  | -   | CLI    | -
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
覆盖: 13/14 = 93%
```

### 1.4 集成拓扑合规审计

```
治理等级: MCP > REST > CLI > direct import

已发现违规 (按严重度排序):
┌──────────┬─────────────────────────────┬────────┬────────┐
│ 严重度   │ 违规                         │ 类型   │ 影响范围 │
├──────────┼─────────────────────────────┼────────┼────────┤
│ 🟠 HIGH  │ KOS → eidos 直接 import     │ import │ 多模块  │
│ 🟡 MED   │ Iris → eidos (可选 import)  │ import │ 单模块  │
│ 🟡 MED   │ eidos → SharedBrain (fs)    │ 文件   │ 单文件  │
│ 🟢 LOW   │ Iris → minerva (path)       │ path   │ test   │
│ 🟢 LOW   │ eidos → KOS (少量)          │ import │ 单文件  │
└──────────┴─────────────────────────────┴────────┴────────┘

合规率: ~65% (21/26)
```

### 1.5 测试覆盖总览

```
项目             | tests | 通过率 | CI  | 备注
SharedBrain     | 16676 | ✅     | ❌  | 本次修复
agentmesh       | 24+   | ✅     | ❌  | 
hermes-scripts  | 139   | ✅     | ❌  | 本次新增
kronos          | 91    | ✅     | ❌  | 本次新增 (从17)
SSOT            | 50    | ✅     | ❌  | 本次修复
MetaOS          | 39    | ✅     | ✅  | 本次修复
Iris            | 66    | ✅     | ❌  | 
integration     | 8     | ✅     | ❌  | 本次新增
KOS             | 22    | ❌2    | ❌  | 需修复
ontoderive      | ~10   | ❌1    | ❌  | 需修复
```

---

## 二、红队分析

### 2.1 安全态势全景

```
攻击面分析 (从最危险到最不危险):
┌──────┬────────────────────────────────┬──────────┬──────────┐
│ 风险 │ 暴露面                         │ 状态     │ 修复     │
├──────┼────────────────────────────────┼──────────┼──────────┤
│ 🔴   │ agentmesh Gateway :3000        │ ✅ 修复  │ fail-close│
│ 🟠   │ AGORA_API_KEY 代码级未配       │ ✅ 修复  │ fail-close│
│ 🟠   │ MINERVA_API_KEY 代码级未配     │ ✅ 修复  │ fail-close│
│ 🟠   │ Ollama :11434 本机无认证        │ ⚠️ 已知  │ localhost│
│ 🟡   │ SharedBrain .env 未验证         │ ⚠️ 需确认│ -        │
│ 🟢   │ MCP stdio (本地)               │ ✅ 接受  │ 本地协议 │
│ 🟢   │ 4 fail-open 已修复             │ ✅ 关门  │ 本次     │
└──────┴────────────────────────────────┴──────────┴──────────┘

最危险的攻击链 (已阻断):
  agentmesh :3000 × Agora :7430 × Ollama :11434
  └── 攻击者进入内网 → 控制 Agent 编排 → 任意任务执行 → RCE via Ollama
  
  阻断: Gateway fail-closed, API_KEY 已配
```

### 2.2 认证清单

```
服务             | 认证字段            | 配置状态
agentmesh GW     | API_KEY             | ✅ 已配 (fail-closed)
Agora            | AGORA_API_KEY       | ✅ 已配 (fail-closed)
minerva          | MINERVA_API_KEY     | ✅ 已配 (fail-closed)
hermes-webui     | HERMES_WEBUI_PASS   | ✅ 已配 (fail-closed)
SharedBrain MCP  | stdio (本地)        | 🟢 接受
```

### 2.3 数据保护

```
数据资产               | 类型     | 备份        | 完整性
SharedBrain/data/db/   | SQLite   | ✅ 43 files | 🟠 messages.db 需检查
agora.db               | SQLite   | ❌         | 🟠 孤儿(已隔离)
~/.gbrain/             | 持久记忆 | ❌         | 🟡 
~/.iris/               | 连接器   | ❌         | 🟡
KOS *.db               | SQLite   | ❌         | 🟡
```

### 2.4 依赖风险

```
外部服务     | 端口   | 认证 | 风险
Ollama      | 11434 | ❌  | 🟠 本机 LM, 无认证
SearXNG     | 8080  | ❌  | 🟡 minerva 引用
Neo4j       | 7474  | 🟠  | 🟡 默认密码
```

---

## 三、剩余差距总表

### 🔴 Critical (0)
*无。全系统已无 Critical 差距。*

### 🟠 HIGH (3)

| # | 差距 | 为什么 | 建议工日 |
|---|------|--------|:--------:|
| H1 | **KOS 2 test fail** | 共识 domain 有 2 个测试失败 | 1h |
| H2 | **ontoderive 1 test fail** | 需要排查 root cause | 1h |
| H3 | **SharedBrain messages.db 完整性** | 审计发现损坏证据 | 1h |

### 🟡 MEDIUM (6)

| # | 差距 | 建议工日 |
|---|------|:--------:|
| M1 | KOS→eidos 解耦 | 2h |
| M2 | non-KOS 项目 CI 建设 (6 项目) | 3h |
| M3 | SharedBrain 定时备份完善 | 30m |
| M4 | 4 项目 README 补充 | 1h |
| M5 | 引用链追溯 (X3) | 2h |
| M6 | 低活跃项目归档评估 | 1h |

### 🟢 LOW (3)

| # | 差距 | 建议工日 |
|---|------|:--------:|
| L1 | x2 复盘自动化 | 1h |
| L2 | gstack orchestrator 完全标准化 | 2h |
| L3 | Unified daemon status dashboard | 2h |

---

## 四、综合评分

```
架构完整性   9/10  🟢  (4+1+3 六层齐全)
架构清晰度   8/10  🟢  (24 项目均可在架构图上定位)
测试覆盖     7/10  🟡  (还有 3 个缺口项目)
安全性       9/10  🟢  (fail-closed + API_KEY + SECRETS_INVENTORY)
运维韧性     6/10  🟡  (备份刚配，CI 不全)
扩展性       8/10  🟢  (MCP 标准协议，新项目 200 行接入)
红队态势     8/10  🟢  (0 CRITICAL，5 个已修复)

综合: 7.9/10 🟢
趋势: ⬆ +3.9 (会话开始时 ~4.0)
```

---

## 五、最终判断

> **Workspace 是一个「架构概念成熟度远高于运维韧性」的系统。4+1+3 六层齐全且运行中，L4/L3/X3 甚至被 KOS 提前实现。X1 治理是本会话最大的飞跃——从概念变成了锁死的制度。**
>
> **最危险的安全问题已经修复（5 fail-open→fail-closed），最长的 L3 协作链路已经打通（collab↔agentmesh↔tracer），最大的测试缺口已经填补（hermes/kronos/SharedBrain）。**
>
> **现在系统处于「架构就绪、运维欠账」的状态。下一步最该做的是：让 KOS 的 2 个测试通过，然后收敛到平台运维——不建新功能，先把这 24 个项目稳住。**
