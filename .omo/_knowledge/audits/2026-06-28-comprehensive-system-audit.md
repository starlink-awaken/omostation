# omostation 全面功能分析与深度研究

> **日期**: 2026-06-28 | **范围**: 17 项目全量审计 | **方法**: 4 组 subagent 并行深挖
> **审计维度**: 治理健康 + 代码质量 + 架构依赖 + 功能缺口 + 文档配置 + 运维可观测

---

## 0. 总览仪表盘

<json-render>{"root":"d","elements":{"d":{"type":"Box","props":{"flexDirection":"column","padding":1},"children":["h","grid","divider","sev"]},"h":{"type":"Heading","props":{"text":"审计发现总览","level":"h2"},"children":[]},"grid":{"type":"Box","props":{"flexDirection":"row","gap":2},"children":["c1","c2","c3","w1","w2"]},"c1":{"type":"Card","props":{"title":"Critical","padding":1},"children":["cl"]},"cl":{"type":"List","props":{"items":["C1: nucleus 顶层 import 断裂","C2: 517KB 运行日志入库","C3: observability .env 明文密钥","C4: GaC Stage 1 未绑定","C5: 无数据库迁移框架","C6: 130 文件未提交","C7: omo governance 70分","C8: MOF state-bridge 77项失同步","C9: MOF schema 9项错误"]},"children":[]},"c2":{"type":"Card","props":{"title":"Warning","padding":1},"children":["wl"]},"wl":{"type":"List","props":{"items":["W1: 3项目 lint 失败","W2: 173个 God Module >500行","W3: 3项目测试极少(14-17)","W4: eidos↔kos 循环依赖","W5: omo 子模块 dirty 20文件","W6: gbrain detached HEAD","W7: nucleus 迁移未完成(11文件)","W8: 381处 broad except","W9: bus-foundation/omo-debt 无 MCP","W10: 3个集成断裂点","W11: X3 规则仅4%","W12: c2g/observability 无 CI"]},"children":[]},"c3":{"type":"Card","props":{"title":"Info","padding":1},"children":["il"]},"il":{"type":"List","props":{"items":["I1: GaC 13/13 全绿","I2: 0 dead code (kairon/omo)","I3: 7 TODO 标记(低债)","I4: BOS 100服务全覆盖","I5: 无硬编码 API key","I6: 子模块 17/17 一致"]},"children":[]},"w1":{"type":"Card","props":{"title":"通过项","padding":1},"children":["pl"]},"pl":{"type":"List","props":{"items":["gac-healthcheck 13/13 ✅","gac-drift 0 drift ✅","gac-validate 0 error ✅","ssot-guardian ✅","gac-m1-sync 0 drift ✅","F401/F811 0 violations ✅"]},"children":[]},"w2":{"type":"Card","props":{"title":"修复优先级","padding":1},"children":["rl"]},"rl":{"type":"List","props":{"ordered":true,"items":["P0: 提交130文件+omo指针","P1: omo governance→100","P2: MOF schema 9项修复","P3: nucleus 2处顶层import","P4: trace_log.jsonl 移出git","P5: God Module 拆分(渐进)","P6: 低测试项目补测试","P7: GaC Stage 1 绑定"]},"children":[]},"divider":{"type":"Divider","props":{"title":"分维度详情"},"children":[]},"sev":{"type":"Box","props":{"flexDirection":"column","gap":1},"children":["s1","s2"]},"s1":{"type":"StatusLine","props":{"text":"GaC 体系闭环生效 (13/13 全绿, 0 drift)","status":"success"},"children":[]},"s2":{"type":"StatusLine","props":{"text":"治理就绪度 73/100 (B级) — 闭环纪律+治理评分拖累","status":"warning"},"children":[]}}}</json-render>

---

## 1. 治理健康维度

### 1.1 通过项 (5/8 工具全绿)

| 工具 | 结果 |
|------|------|
| gac-healthcheck.py | ✅ 13/13 全绿 (core/gac-validate/gac-drift/ADR/M2/doc-ssot/hygiene/registry/legacy/bootstrap/executor/m1-drift) |
| gac-drift.py | ✅ 0 drift, 118 rules |
| gac-validate.py --gate | ✅ 0 error, 0 warning |
| ssot-guardian.py | ✅ SSOT 一致性通过 |
| gac-m1-sync.py --diff | ✅ 0 drift, 118↔118 同步 |

### 1.2 问题项 (3/8 工具失败)

| # | 严重性 | 问题 | 影响 |
|---|--------|------|------|
| C6 | 🔴 Critical | **130 文件未提交** | 闭环纪律维度 10/20, 违反 CR-GOV-CLOSED-LOOP-01, 阻断 post-commit 知识萃取 |
| C7 | 🔴 Critical | **omo governance = 70.0** (目标 100) | 治理评分维度 0/15, X4 一致性门禁失败 |
| C8 | 🔴 Critical | **MOF state-bridge 77 项失同步** | M1 only: 8 (6 IMPORTED ghost + 1 nop + 1 auto-discovery), .omo only: 69 (含大量 OPC-P6-SELF-EVOLUTION-nop-* 时间戳文件) |
| C9 | 🔴 Critical | **MOF schema 9 项错误** | 7 个 MODEL-BREW-* 节点 type=ModelDefinition 无 M2 schema, 2 个 WORKFLOW-* 节点缺 workflow_name |
| W-drift | 🟠 Warning | **drift=5 在阈值边界** | 任何新增 drift 将突破 ≤5 阈值 |

---

## 2. 代码质量维度

### 2.1 Lint 状态

| 项目 | 结果 | 明细 |
|------|------|------|
| kairon | ✅ Clean | 0 errors |
| omo | ✅ Clean | 0 errors |
| ecos | ✅ Clean | 0 errors |
| agora | ✅ Clean | 0 errors |
| cockpit | ✅ Clean | 0 errors |
| runtime | ✅ Clean | 0 errors |
| c2g | ✅ Clean | 0 errors |
| aetherforge | ✅ Clean | 0 errors |
| **bus-foundation** | ❌ **6 errors** | I001×2 (import排序), W293×3, W291×1 (5 auto-fixable) |
| **metaos** | ❌ **1 error** | F823: `sys` referenced before assignment (cli/__init__.py:189) |
| **l4-kernel** | ❌ **1 error** | F401: `datetime.timedelta` unused (contract_monitor.py:18) |

### 2.2 类型检查 (kairon mypy)

- **86 errors / 56 files** (out of 613 source files, ~14% error rate)
- 主要类型: `attr-defined` (动态模块属性, ~15), `no-any-return` (~3), `no-untyped-def` (~1)
- 阻塞因素: `test_basic` 模块重名 (kairon-lib-events vs health-profile), minerva/sophia 的 `explicit_package_bases` 配置缺失

### 2.3 God Module (173 files >500 lines, 10 files >1000 lines)

| # | 行数 | 文件 | 项目 |
|---|:----:|------|------|
| 1 | 1352 | `agora/mcp/resolver/services.py` | agora |
| 2 | 1351 | `cockpit/commands/research.py` | cockpit |
| 3 | 1280 | `kairon/forge/asset_cli.py` | kairon |
| 4 | 1198 | `ecos/l0/ssot/cli.py` | ecos |
| 5 | 1131 | `kairon/kos/indexer/engine.py` | kairon |
| 6 | 1107 | `omo/omo_cards.py` | omo |
| 7 | 1067 | `omo/omo_worker_promotion.py` | omo |
| 8 | 1042 | `omo-debt/cli.py` | omo-debt |
| 9 | 1025 | `omo/omo_audit.py` | omo |
| 10 | 980 | `aetherforge/lifecycle/lifecycle_manager.py` | aetherforge |

> 建议: 按 CR-ENG-SRP-INCREMENTAL-01 渐进拆分 (纯函数先→核心后, 每步 import+test 验证)

### 2.4 测试覆盖

| 覆盖等级 | 项目 | 测试文件数 |
|----------|------|:---------:|
| 优秀 | kairon | 2649 |
| 良好 | agora | 213 |
| 良好 | omo | 179 |
| 中等 | cockpit | 89 |
| 中等 | ecos | 64 |
| 中等 | runtime | 50 |
| 低 | metaos | 43 |
| 低 | aetherforge | 43 |
| 低 | l4-kernel | 31 |
| 低 | c2g | 26 |
| **极低** | **bus-foundation** | **17** |
| **极低** | **family-hub** | **17** |
| **极低** | **omo-debt** | **14** |

### 2.5 其他代码质量

| 维度 | 状态 | 明细 |
|------|------|------|
| Dead code (F401/F811) | ✅ 0 violations | kairon + omo 全清 |
| TODO/FIXME 标记 | ✅ 7 处 (低债) | 3/7 为 nucleus 迁移标记 |
| `__import__()` 模式 | 🟠 10 处 | 6 处在源码 (omo/metaos), 4 处在测试 |
| Deprecated imports | ✅ 0 处 | 无 `import imp` / `from distutils` |
| Broad except | 🟠 381 处 | ecos 137 (最差), agora 67, cockpit 56, omo 41 |

---

## 3. 架构与依赖维度

### 3.1 Critical 架构问题

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| C1 | **nucleus 顶层 import** (import 时断裂) | `kairon/eidos/dream_engine.py:27`, `kairon/eidos/unified_memory_api.py:37` | 导入这两个模块时 ImportError, nucleus 包已废弃 |
| C2 | **517KB 运行日志入库** | `agora/src/trace_log.jsonl` (tracked, 非 .gitignore) | 仓库膨胀, merge 噪音 |
| C3 | **observability/.env 明文密钥** | POSTGRES_PASSWORD, NEXTAUTH_SECRET, SALT | .env 在 .gitignore 内但磁盘明文 |

### 3.2 Warning 架构问题

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| W4 | **eidos↔kos 循环依赖** | eidos/storage.py → kos.search, kos/*.py → eidos.memory_graph | 全部 lazy import (无 import-time cycle), 但架构异味 |
| W5 | **omo 子模块 dirty** | 20 文件未提交 (16 .omo + 4 docs), 根指针落后 2 commits | 违反强制闭环原则 |
| W6 | **gbrain detached HEAD** | eval-run 分支, 非 main | 分叉风险 |
| W7 | **nucleus 迁移未完成** | 11 文件 (2 顶层 + 9 lazy) | eidos 7 + ontoderive 1 + aetherforge/swarm 9 (全 lazy+type:ignore) |
| W8 | **端口硬编码** | omo_dashboard.py:9190, omo_health.py DEFAULT_SERVICE_PORTS | 默认值非 env 驱动 |
| W9 | **c2g/observability 无 CI** | 无 .github/workflows/ | 变更无自动验证 |
| W10 | **SQL 列名插值** | cockpit/omo/runtime/aetherforge/kairon (5 处) | 值已参数化, 标识符 f-string (低风险 code smell) |

### 3.3 子模块状态

| 子模块 | 状态 | 问题 |
|--------|------|------|
| omo | ⚠️ dirty + 指针落后 | 20 未提交, HEAD 领先根指针 2 commits |
| gbrain | ⚠️ detached HEAD | eval-run 分支, 非 main |
| 其余 15 | ✅ clean | 无异常 |

---

## 4. 功能缺口维度

### 4.1 MCP 工具覆盖缺口

| 项目 | MCP 工具数 | 状态 |
|------|:---------:|------|
| agora | 141 | ✅ Hub (代理全部) |
| kairon (7 包) | 80 | ✅ codeanalyze 31 + iris 12 + kronos 9 + minerva 8 + sophia 8 + forge 7 + ontoderive 5 |
| ecos | 34 | ✅ |
| runtime | 32 | ✅ |
| omo | 21 | ✅ |
| l4-kernel | 8 | ✅ |
| aetherforge | 6 | ✅ |
| cockpit | 5 | 🟠 偏低 (L3 入口) |
| c2g | 3 | 🟠 偏低 |
| metaos | 2 | 🟠 偏低 |
| **bus-foundation** | **0** | ❌ 纯 Python API, 无 MCP 暴露 |
| **omo-debt** | **0** | ❌ CLI only, 无法经 Agora 查询 |

### 4.2 集成断裂点

| 断裂 | 现状 | 影响 |
|------|------|------|
| **family-hub → gbrain** | 无连接 | 家庭 quest 数据孤立在本地 SQLite, 不入知识库 |
| **omo-debt → GaC** | 无直接集成 | 债务评分引擎未接入 118 条 GaC 规则链 |
| **observability → omo alerts** | 单向 (项目→Langfuse) | Langfuse trace 异常不反馈到 OMO 告警系统 |

### 4.3 GaC 规则维度失衡

| 维度 | 规则数 | 占比 | 状态 |
|------|:------:|:----:|------|
| X4 一致性 | 58 | 49% | ✅ 充分 |
| X1 审计 | 29 | 25% | ✅ 充分 |
| X2 抗熵 | 26 | 22% | ✅ 充分 |
| **X3 价值** | **5** | **4%** | ❌ 严重不足 (roadmap T2.5 已标注) |

### 4.4 未完成功能

| # | 功能 | 来源 | 状态 |
|---|------|------|------|
| F1 | GaC Stage 1 执行绑定 (4 tasks) | roadmap-v1.md | 全部 pending |
| F2 | aetherforge CLI swarm 命令 | aetherforge/cli.py:13 | TODO |
| F3 | metaos cycle detection | workflow_parser.py:57 | "暂时简单实现" |
| F4 | 无数据库迁移框架 | 全项目 | ad-hoc ALTER TABLE |

### 4.5 安全审计

| 检查项 | 状态 | 明细 |
|--------|------|------|
| 源码硬编码 API key | ✅ 0 处 | 全部 `os.environ.get()` |
| 源码 SQL 注入 (值) | ✅ 全参数化 | `?` 占位 |
| SQL 列名插值 | 🟠 5 处 | 标识符 f-string (可控来源, 低风险) |
| observability .env | 🔴 明文密钥 | .gitignore 内但磁盘暴露 |

---

## 5. 文档与配置维度

### 5.1 文档覆盖

| 文档类型 | 覆盖率 | 缺失 |
|----------|:------:|------|
| AGENTS.md | 17/17 | 无缺失 |
| ARCHITECTURE.md | 17/17 | 无缺失 |
| CLAUDE.md | 13/17 | aetherforge, omo-debt, family-hub, observability |
| BOUNDARY.md | 1/17 | 仅 kairon |
| CALLCHAIN.md | 1/17 | 仅 kairon |

### 5.2 BOS URI 覆盖

- 100 声明式服务 (9 域) → 100 有实现引用 (0 孤儿)
- 代码中 337 unique bos:// URI → 多余的 237 为测试 fixture (`bos://test/*`, `bos://nonexistent/*`)
- 真实服务 URI 与声明一致

### 5.3 CI 覆盖

| 项目 | CI workflows | 状态 |
|------|:-----------:|------|
| kairon | ✅ | 有 |
| omo | ✅ | 有 |
| ecos | ✅ | 有 |
| agora | ✅ | 有 |
| cockpit | ✅ | 有 |
| runtime | ✅ | 有 |
| metaos | ✅ | 有 |
| l4-kernel | ✅ | 有 |
| aetherforge | ✅ | 有 |
| bus-foundation | ✅ | 有 |
| omo-debt | ✅ | 有 |
| family-hub | ✅ | 有 |
| **c2g** | ❌ | 无 (部分被根仓 c2g-gc-weekly/c2g-radar-daily 覆盖) |
| **observability** | ❌ | 无 (Docker-only) |

---

## 6. 修复优先级排序

### P0: 立即修复 (阻断核心流程)

| # | 问题 | 修复方案 | 预估工作量 |
|---|------|---------|-----------|
| 1 | 130 文件未提交 | 逐批 commit + bump omo 指针 | 30min |
| 2 | omo governance = 70 | 跑 `omo governance` 诊断 6 项, 修复失败项 | 1h |
| 3 | MOF schema 9 项错误 | 补 ModelDefinition M2 schema 或重 type, 补 workflow_name | 30min |

### P1: 本周修复 (架构风险)

| # | 问题 | 修复方案 | 预估工作量 |
|---|------|---------|-----------|
| 4 | nucleus 顶层 import (C1) | 改为 lazy/TYPE_CHECKING 或移除 nucleus 依赖 | 1h |
| 5 | trace_log.jsonl 入库 (C2) | `git rm --cached` + 加入 .gitignore | 5min |
| 6 | observability .env 明文密钥 (C3) | 轮换密钥 + 确认 .env.example 有占位符 | 15min |
| 7 | 3 项目 lint 失败 | `ruff check --fix` + 手动修 F823 | 10min |
| 8 | omo 子模块 dirty | commit 20 文件 + bump 根指针 | 15min |
| 9 | MOF state-bridge 77 失同步 | 归档 69 .omo-only nop 文件, 清理 8 M1-only ghost | 2h |

### P2: 本月改进 (技术债)

| # | 问题 | 修复方案 | 预估工作量 |
|---|------|---------|-----------|
| 10 | God Module 拆分 (10 个 >1000 行) | 按 CR-ENG-SRP-INCREMENTAL-01 渐进拆分 | 3-5 天 |
| 11 | 低测试项目补测试 | bus-foundation/family-hub/omo-debt 补核心路径测试 | 2-3 天 |
| 12 | mypy 86 errors | 修类型标注 + 模块重名 | 1-2 天 |
| 13 | broad except 清理 | 381 处 → 逐项目细化异常类型 | 2-3 天 |
| 14 | GaC Stage 1 执行绑定 | PreToolUse hook + MCP 内嵌 check + CI gate | 3-5 天 |
| 15 | X3 规则补全 | 从 5 → 20+ 规则 (覆盖 L1/L3 层 + 价值流) | 1-2 天 |

### P3: 长期演进

| # | 问题 | 修复方案 |
|---|------|---------|
| 16 | nucleus 迁移完成 | 11 文件 → 0 (移除全部 lazy import) |
| 17 | eidos↔kos 循环依赖 | 提取公共接口包或反转依赖方向 |
| 18 | 数据库迁移框架 | 引入 alembic (SQLite/Postgres) |
| 19 | 集成断裂修复 | family-hub→gbrain, omo-debt→GaC, observability→omo |
| 20 | gbrain detached HEAD | checkout main + 确认 eval 分支已合并 |
| 21 | c2g/observability CI | 添加基础 CI workflow |
| 22 | bus-foundation/omo-debt MCP | 暴露核心查询接口到 Agora mesh |

---

## 7. 架构成熟度评估

<json-render>{"root":"m","elements":{"m":{"type":"Box","props":{"flexDirection":"column","padding":1},"children":["h","t"]},"h":{"type":"Heading","props":{"text":"架构成熟度评分","level":"h2"},"children":[]},"t":{"type":"Table","props":{"columns":[{"header":"维度","key":"dim","width":20},{"header":"评分","key":"score","width":10},{"header":"等级","key":"grade","width":8},{"header":"说明","key":"note","width":40}],"rows":[{"dim":"协议层 (L0 ecos)","score":"90","grade":"A","note":"MOF M3→M2→M1 完整, SSB 签名链, 9 项 schema 错误待修"},{"dim":"治理面 (L2 omo)","score":"75","grade":"B","note":"GaC 体系闭环, 但 governance=70, 130 文件未提交"},{"dim":"知识引擎 (L2 kairon)","score":"80","grade":"A-","note":"16 包完整, 但 nucleus 残留 + eidos↔kos 循环"},{"dim":"入口层 (L3 cockpit)","score":"85","grade":"A","note":"CLI+Web+MCP 三入口, 15 API routers, God Module 待拆"},{"dim":"织层 (I0 agora)","score":"85","grade":"A","note":"BOS 100 服务, 141 MCP tools, trace_log 入库待修"},{"dim":"运行时 (L1 runtime)","score":"80","grade":"A-","note":"KEI 沙箱, Matrix, 50 测试, Cron 完整"},{"dim":"编排引擎 (L2 metaos)","score":"70","grade":"B","note":"门控+免疫, 但 F823 lint + 43 测试 + __import__"},{"dim":"自我层 (L4 l4-kernel)","score":"85","grade":"A","note":"28 域, 42 MCP, 1 F401 待修"},{"dim":"横切框架 (X)","score":"65","grade":"B-","note":"bus-foundation 无 MCP, omo-debt 无 MCP, 集成断裂 3 处"},{"dim":"文档与配置","score":"80","grade":"A-","note":"AGENTS.md 17/17, BOUNDARY/CALLCHAIN 仅 kairon"},{"dim":"CI/CD","score":"75","grade":"B","note":"15/17 项目有 CI, c2g/observability 缺失"},{"dim":"可观测性","score":"60","grade":"C+","note":"Langfuse 单向, 无反馈到 omo alerts, .env 明文"}],"headerColor":"blue"}}}}</json-render>

**综合评分**: **77/100 (B+)** — 核心架构稳固, GaC 体系闭环, 主要短板在治理执行 (未提交文件 + governance 70) 和横切框架集成断裂。

---

*全面功能分析与深度研究 · 2026-06-28 · 4 组 subagent 并行审计 · 9 Critical + 12 Warning + 6 Info*
