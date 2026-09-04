---
status: planned
lifecycle: plan
owner: governance-team
last_updated: 2026-07-31
review-state: metadata-only
metadata-migrated-at: 2026-07-31
type: ephemeral
---
# L2 引擎层统一治理优化方案（kairon / gbrain / omo / omo-debt / family-hub）

> 日期: 2026-07-26
> 状态: 提案（待 D1–D4 决策签核后进入 Round 执行）
> 范围: `projects/kairon/`、`projects/gbrain/`、`projects/omo/`、`projects/omo-debt/`、`projects/family-hub/` + workspace 侧注册/引用面
> 依据: 2026-07-25/26 L2 五项目双路深度架构分析（本文件 §2 诊断）
> 姊妹方案: [`2026-07-25-mof-m4-governance-optimization-plan.md`](2026-07-25-mof-m4-governance-optimization-plan.md)、[`2026-07-25-metaos-governance-optimization-plan.md`](2026-07-25-metaos-governance-optimization-plan.md)

## 1. 摘要

L2 引擎层五个项目分析完毕，呈现**鲜明的两极**：

- **工程本体普遍健康**：gbrain 测试与源码 1:1（各 ~16 万行）+ 16 项 verify 门禁；omo 630 passed/0 failed + 29 个 mutation surface 收口 28 个；kairon 本地 1200+ 测试通过、单一 BOS 出口零直接 import。
- **治理投影普遍失真**：kairon CI 在 main 上永红（独立 checkout 必挂）；gbrain registry 标 dormant 实际当天还在交付；omo 两个 CLI 子命令是断链死命令；注册面/文档/债务账本全面落后于代码现实 1-6 周。

核心战略判断：**workspace 的治理成熟度分层断裂**——元模型层（M0/L0 MOF-M4）有 5-check 自反门禁和 Health Score，而 L2 项目层的 CI、文档、注册面、债务账本没有等效守门。本方案的主线是把 M0/L0 已验证的"自反守门"模式下沉到 L2 项目层，同时按项目分级处置执行债。

3 个 Phase、16 个 deliverable（8 个跨切 + 8 个项目专项）、4 个决策点，与已发布的 MOF/M4、metaos 两方案并轨不重复建设。

## 2. 诊断（证据摘要）

### 2.1 跨项目系统性模式（同一家族的声明/执行鸿沟）

| 模式 | kairon | gbrain | omo | 既有案例 |
|------|--------|--------|-----|---------|
| CI 失真 | **main 永红**（跨仓 path 依赖 + py3.10-3.12 过期矩阵 + ci.yml.bak 残留） | 根仓 workflow 是 no-op 占位 | — | metaos CI 假绿（ignore 双向漂移） |
| 注册面漂移 | `projects-capabilities.yaml` 残留 kairon.agent-runtime/agora 陈旧条目；M1/run-all.sh 还写"31 包"（实际 16） | registry 标 dormant 实际活跃；submodule 口径过期 | registry src_files 173→150、子命令 39→58、计数命令指向已删除文件 | mof-capabilities.yaml 漂移；metaos 3 处漂移 |
| 文档数字失真 | INTERFACE.yaml "25 包 1810 tests"（实际 16 包 ~3237）；ARCHITECTURE.md MCP"碎片化" vs 已统一 FastMCP | ops 计数三处不一（代码 75 vs 70 vs 67）；测试数 888 vs 实际 732 | ARCHITECTURE.md 声称 4 个模块全不存在；INTERFACE.yaml "10 tools/28 子命令"（实际 19/~40） | model-driven 文档数字失真 |
| 债务账本失真 | 6 个 OMO-DEBT 实体 active 积压 + 仓内台账 2026-06 起未更新 | DEBT-GBRAIN-OPERATIONS-TS 实质已修复（4514→23 行）但未走关闭流程 | 7 项 P0 seed 已清零（正面案例） | — |
| 指针/端点失真 | iris 3 个 BOS 入口 unimplemented | agora-services.json 5433 endpoint 错位 + healthy:true/instances:[] 假阳性；3131 三处硬编码未入 port-registry | runtime import 不存在的 `omo.omo_state_schema` | model-driven agora endpoint 空 |
| 死代码/双轨 | `src/kairon/__init__.py` 幽灵包名列表；根 tests/ e2e 2299 行不进任何门禁 | tests/ 与 test/ 双目录；memu-brain.db 二进制入库 | `omo predict`/`omo cache` 断链死命令；pyproject 挂 model-driven 零 import；omo 内嵌 debt vs omo-debt 外设双轨 | model-driven CLI/MCP 半建 |

### 2.2 项目分级

| 项目 | 体量 | 本体成熟度 | 主要风险 | 处置级别 |
|------|------|-----------|---------|---------|
| kairon | 16 包 ~152K LOC | 中高（架构收敛正确） | **CI 永红 = 无安全网**；文档严重过期；e2e 摆设；债务积压 | P0 止血优先 |
| gbrain | ~164K src + ~155K test | **高**（L2 标杆） | 治理投影滞后代码 1-6 周；1 个稳定失败测试；端口/端点失真 | P1 投影对齐 |
| omo | 139 模块 ~45K LOC | 高（收口真实） | 死命令 + 文档漂移 + god-package + debt 双轨 | P1 修面子 + P2 结构 |
| omo-debt | 18 文件 | 中 | 与 omo 内嵌 debt 双轨，唯一消费者是每日 cron | P2 双轨收敛决策 |
| family-hub | 单文件 MCP + React | 低活跃 | 层归属 L2/X 三处口径不一；pyproject 占位符 | P2 轻量收口 |

### 2.3 关键实证摘录

- **kairon CI 永红根因**：`packages/kairon-pipeline/pyproject.toml:35` `bus-foundation = {path = "../../../bus-foundation"}` 跨仓 path 依赖，独立 checkout `uv sync` 必挂；test-codeanalyze 矩阵含 py3.10-3.12 但根 `requires-python>=3.13`。
- **gbrain 稳定红灯**：`test/source-id-tx-regression.test.ts` 的 `delete_page handler scopes to ctx.sourceId` 稳定复现失败。
- **omo 死命令**：`cli.py:561,663` import 不存在的 `omo.bridge_utils`，`omo predict`/`omo cache` 必然 ImportError。
- **gbrain 边界现状**：与 kairon/kos 的检索重叠靠"分层叙事 + GbrainBridge 同步桥 + agora 记忆脊聚合搜索"三支柱维持，自洽但本质冗余——本方案不动这个架构，只要求把三支柱声明对齐到代码。

## 3. 战略目标与北极星

**北极星（12 周）**：L2 引擎层达到"**CI 全部真绿、注册面零漂移、宣称=实现、债务账本诚实**"，且守门机制化（不是一次性清扫）。

三条战略主线：

- **S1 安全网优先（Safety Net First）**：kairon CI 永红是全 L2 最危险的问题——152K LOC 的项目没有可用的 CI 等于裸奔。P0 一切为止血让路。
- **S2 自反守门下沉（Push Self-Reflex Down）**：把 M0/L0 已验证的模式（drift 门、宣称对账、投影守护）以**统一门禁扩展**的方式覆盖 L2，而非每项目各建一套——与 MOF/M4 方案 P0-2、metaos 方案 P1-4 共用同一扇门。
- **S3 分级处置（Tiered Treatment）**：gbrain/omo 本体健康只需投影对齐；kairon 需止血+清债；omo-debt/family-hub 需定位收敛。不搞一刀切。

## 4. 治理原则（不可违反）

- 子模块内先修复、主仓走 worktree+PR 更新 pointer（AGENTS.md §6）。
- ADR 先占号；每 deliverable 一个 PR（单 lane）；P74 全程留 evidence。
- gbrain vs kairon/kos 的检索分层架构不在本方案改动范围（§2.3），只修声明。
- omo broker 收口成果不回退：任何新写面必须 brokered + 注册 mutation-surfaces。
- 与 MOF/M4、metaos 方案并轨项直接扩展其机制，不新建并行门禁。

## 5. 跨切 Deliverable（X 系列，贯穿三 Phase）

| # | 内容 | 覆盖项目 | 验证 |
|---|------|---------|------|
| X1 统一注册面漂移门扩展 | MOF/M4 方案 P0-2 的漂移门扩展覆盖：`project-registry.yaml`（活跃度口径、src_files、子命令计数）、`projects-capabilities.yaml`（死条目）、`phase-scope.yaml`（死路径）、submodule_policy（分支名）、M1 指针（SVC/MCPTOOL source_file 存在性、BOSROUTE 重复检测） | 全部 + MOF/M4 + metaos | 注入漂移可检出；现有 3+3+4 处已识别漂移修复后全绿 |
| X2 宣称对账范式 | 各项目 INTERFACE.yaml/ARCHITECTURE.md/CAPABILITY-MAP 中的包数、测试数、ops 数、工具数全部指针化到 registry 或生成快照；禁手工维护统计数字 | 全部 | doc-ssot-lint 扩展规则 |
| X3 端口注册表收口 | 3131（gbrain HTTP）三处硬编码默认值（cockpit `GBRAIN_PORT`、kairon `GBRAIN_MCP_URL`、gbrain `serve.ts`）登记入 `protocols/port-registry.yaml` 并改 env 引用；修 agora-services.json 5433 错位 + healthy 假阳性 | gbrain + cockpit + kairon + agora | port-governance deck 通过 |
| X4 债务账本诚实化 | 三批处置：kairon 6 个 active OMO-DEBT 实体逐一 triage（修/关闭/降级）；DEBT-GBRAIN-OPERATIONS-TS 走正式关闭流程；kairon 仓内 `.omo` 台账 2026-06 旧账批量核销（已被演进消化的关闭，仍真实的转 OMO 实体） | kairon + gbrain | debt dashboard 活跃数真实；system.yaml 同步 |

## 6. 分阶段落地规划

### Phase 0 — 止血：恢复安全网（Week 0–2，R-patch 型，1–2 ADR）

| Deliverable | 项目 | 内容 | 验证 |
|---|---|---|---|
| P0-1 kairon CI 修复（依赖 D1） | kairon | 消除 kairon-pipeline 跨仓 path 依赖（推荐：改 optional extra + CI 内按 workspace 布局注入，或 vendor 最小接口）；test-codeanalyze 矩阵删 py3.10-3.12；删 ci.yml.bak | kairon-ci 在独立 checkout 连续 3 次绿 |
| P0-2 gbrain 红灯修复 | gbrain | 修 `source-id-tx-regression.test.ts` 的 delete_page sourceId 作用域失败 | `bun test` 该文件全绿 |
| P0-3 omo 死命令处置 | omo | `omo predict`/`omo cache`：或补 `omo.bridge_utils` 实现，或移除命令注册（推荐移除——无消费者实证，补实现属为死代码续命） | CLI 全子命令可 `--help` 无 ImportError |
| P0-4 omo 虚假依赖清理 | omo + runtime | pyproject 移除 model-driven 依赖（零 import 实证）；runtime `adapters/omo.py` 的 `omo.omo_state_schema` 引用修正为真实模块 | uv sync 通过；runtime adapter 测试绿 |
| P0-5 metaos 方案 P0 联动 | metaos | metaos 方案 Phase 0（5 红测试 + CI 假绿）与本方案同期执行，共享"CI 诚实化"ADR 叙事 | 见 metaos 方案 |

退出标准：L2 所有项目 CI 真绿（kairon 连续 3 次、gbrain 红灯清零、metaos ignore 归零）。

### Phase 1 — 对齐：投影=现实（Week 2–6，R-feature 型，2–3 ADR）

| Deliverable | 项目 | 内容 | 验证 |
|---|---|---|---|
| P1-1 跨切 X1 落地 | 全部 | 统一漂移门扩展上线，修复全部已识别注册面漂移（§2.1 注册面行） | 漂移门全绿 |
| P1-2 跨切 X2 落地 | 全部 | kairon INTERFACE.yaml 重写（16 包/实际测试数/删除 sot-bridge 等幽灵 CLI）；gbrain ops 计数统一（75，文档改生成或指针）；omo ARCHITECTURE.md 删 4 个不存在模块的声称、INTERFACE.yaml 数字对齐；kairon ARCHITECTURE.md MCP 描述对齐 FastMCP 现实 | X2 规则通过 |
| P1-3 跨切 X3 落地 | gbrain 系 | 3131 入 port-registry + 三处改 env；agora-services.json 修正 | 端口 deck 通过 |
| P1-4 跨切 X4 落地 | kairon + gbrain | 债务 triage 与账本核销 | debt 活跃数=真实 |
| P1-5 kairon e2e 入门禁 | kairon | 根 `tests/` e2e（2299 行）接入 pytest testpaths 或 CI job；不能跑的标记原因并修 | e2e 进 CI 且绿，或带 ADR 锚的显式豁免 |
| P1-6 kairon 仓库卫生 | kairon | 删幽灵包名列表、仓根运行产物（agora.db/microkernel.db/derivation logs/临时报告）gitignore 化、`dist/` 产物出库；iris 3 个 unimplemented BOS 入口：实现或标 frozen | git ls-files 无产物；BOS 注册表无 unimplemented |
| P1-7 omo M1/注册表对齐 | omo | registry src_files/子命令计数改指针；M1 侧 omo 相关节点核对 | X1 门覆盖 |

退出标准：X1–X4 全绿；INTERFACE/ARCHITECTURE 类文档无手工统计数字。

### Phase 2 — 结构收敛（Week 6–12，R-meta 型，3–4 ADR）

| Deliverable | 项目 | 内容 | 验证 |
|---|---|---|---|
| P2-1 omo god-package 拆分 | omo | 139 模块扁平包按领域分目录（state/audit/lint/debt/task/workflow 已有 `_shared`+`workflow` 先例）；复用 `.claude/skills/omo-srp-refactor` 既有规划；纯移动不改行为 | 全部 import 回归测试绿；god-module lint 通过 |
| P2-2 debt 双轨收敛（依赖 D3） | omo + omo-debt | 推荐：omo-debt 保持"领域外设"定位但明确边界——omo 内嵌 debt 管生命周期/状态，omo-debt 只管评分维度（honesty/legacy）；文档与 BOS 注册对齐此切分；若评估后无差异化价值则归档 omo-debt | 双入口叙事单源；cron 消费路径验证 |
| P2-3 gbrain 结构债决策（依赖 D2） | gbrain | ADR-0156 三栈拆分（core/vector/bos）启动 vs 冻结的正式决策；冻结则先把 postgres-engine/pglite-engine 双 4500 行巨头的 god-module 拆分收尾（operations.ts 已示范路径） | ADR 落定；god-module check 无新增违规 |
| P2-4 family-hub 收口（依赖 D4） | family-hub | 层归属统一（registry L2 vs README X vs layers 块 X，推荐统一 L2 dormant）；pyproject 占位符描述补全；`src/family_hub` 空壳包补或删 | registry/文档一处口径 |
| P2-5 cockpit↔omo API 摩擦治理 | omo + cockpit | cockpit adapter 的 `omo_cockpit_bridge` fallback 重实现评估：omo 侧恢复稳定 API 面或 cockpit 侧正式接管（二选一，消除"被迫 fallback"状态） | adapter 无 fallback 分支或有正式 owner 声明 |

退出标准：结构债均有 ADR 落定的处置路径；无"被迫 fallback"类灰色接线。

## 7. 决策点（需签核后才进入对应 Phase）

| # | 决策 | 选项 | 推荐 | 影响 |
|---|------|------|------|------|
| D1 | kairon-pipeline 跨仓依赖 | A optional extra + CI workspace 布局注入 / B vendor 最小接口进 kairon / C 反向移入 bus-foundation 独立发布 | **A**——改动最小且保持单真源；B 产生副本债务；C 超出本方案范围 | Phase 0 关键路径 |
| D2 | gbrain 三栈拆分 | A 启动 ADR-0156 Phase 3 / B 冻结，先收尾 god-module 拆分 | **B**——ADR-0156 自己标注需 freeze 开发 1-2 月（STRAT-P76 风险项）；当前 ADR-0237 协作黑板方向正活跃，不宜冻结式大拆 | Phase 2 方向 |
| D3 | omo vs omo-debt | A 边界澄清保持双轨 / B omo-debt 归档并入 omo 内核 | **A 先行**（6 周评估期）：若评分维度（honesty/legacy）在 omo 内核无对等能力则保留；评估结论为无差异化价值则转 B | Phase 2 工作量 ±1 周 |
| D4 | family-hub 归属 | A 统一 L2 dormant / B 归档 / C 激活 | **A**——有活跃测试新增（29+15 quest MCP 测试），不够归档标准；BOS persona 域接线真实 | 仅口径变更 |

## 8. 与既有方案的并轨矩阵

| 机制 | MOF/M4 方案 | metaos 方案 | 本方案 | 并轨方式 |
|------|-----------|-----------|--------|---------|
| 注册面漂移门 | P0-2 新建 | P1-4 扩展 | X1 扩展 | **同一扇门**，注册清单进 SSOT，三方案共享 |
| 宣称对账 | P0-3 文档数字收口 | P0-5 失真防复发门 | X2 | 同一范式，doc-ssot-lint 统一承载 |
| CI 诚实化 | — | P0-2 ignore 对账 | P0-1/P0-2/P0-5 | 共享 ADR 叙事"L2 CI 诚实化" |
| 债务账本 | — | — | X4 | 首批覆盖 kairon/gbrain，范式可推广 |

执行顺序建议：三方案 Phase 0 可全并行（不同子模块零文件冲突）；X1 漂移门依赖 MOF/M4 P0-2 先建门，故 X1 排在本方案 Phase 1。

## 9. 度量与门禁（KPI）

| 指标 | 基线（2026-07-26） | 目标（12 周） | 测量 |
|---|---|---|---|
| L2 CI 状态 | kairon 永红 / metaos 假绿 / gbrain 根仓 no-op | 全部真绿且本地≡CI | 各仓 CI 连续 3 次 |
| 注册面漂移项 | ≥10 处（§2.1 已识别） | 0 且机器守住 | X1 门 |
| 手工统计数字文档 | ≥6 处 | 0（全指针化） | X2 规则 |
| 活跃债务失真 | kairon 6 + gbrain 1（假活跃） | 活跃=真实 | debt dashboard |
| 断链/死代码 | omo 2 死命令 + kairon 幽灵包名 + gbrain 双 tests 目录 | 0 | CLI 冒烟 + 结构检查 |
| 端口硬编码 | 3131×3 处 | 0（入 registry + env） | port deck |
| 稳定失败测试 | gbrain 1 + metaos 5 | 0 | 各仓测试 |

## 10. 风险与回滚

| 风险 | 等级 | 缓解 / 回滚 |
|---|---|---|
| P0-1 kairon CI 修复牵出更多跨仓 path 依赖 | 高 | 先全仓 grep `path = "../../../"` 摸底再动手；每修一处独立 PR；回滚=revert |
| P2-1 omo god-package 拆分破坏 bin/ 同进程 import（agent-workflow.py sys.path 注入是最硬耦合） | 高 | 拆分前先建 import 契约测试（23 个 bin 脚本 + cockpit adapter 的 import 面快照）；纯移动+re-export 兼容层；分目录分批 PR |
| X4 债务核销误关真实债务 | 中 | triage 逐项留证据；关闭需 owner 确认；批量核销先 dry-run 清单评审 |
| D2 选 B 后 god-module 双巨头继续膨胀 | 中 | god-module check strict 守新增；拆分排入下一 Round |
| 多 agent 并发（gbrain 当日仍在交付 ADR-0237 系列） | 中 | 子模块内操作前核 git log；registry 类修复走主仓 worktree+PR |

## 11. 执行纪律与时间线

```
Week 0-2   Phase 0（R-patch）: P0-1..P0-5  → ADR-02xx（L2 CI 诚实化，与 metaos P0 共享）
Week 2-6   Phase 1（R-feature）: P1-1..P1-7 → ADR-02xx（统一漂移门扩展）+ ADR-02xx（L2 宣称对账）
Week 6-12  Phase 2（R-meta）: P2-1..P2-5   → ADR-02xx（omo 结构）+ ADR-02xx（debt 双轨）+ ADR-02xx（gbrain 结构决策）
```

每 deliverable 一个 PR（单 lane），ADR 先占号（`bin/adr/next-adr-id.py --session <s> --claim`），子模块内先合再更新主仓 pointer。

## 12. 本方案的边界（明确不做）

- 不动 gbrain vs kairon/kos 检索分层架构（三支柱维持，仅修声明）
- 不启动 gbrain 三栈拆分实施（D2 推荐冻结，仅做决策与 god-module 收尾）
- 不改 omo broker 收口机制与 mutation-surfaces 体系（已是标杆，只修其周边失真）
- 不为无消费者的能力补实现（omo predict/cache 推荐移除而非补实现）
- metaos 专项按 metaos 方案执行，本方案仅引用联动（P0-5）

## 13. 下一步

1. 签核 D1–D4（建议全选推荐项）
2. Phase 0 立即启动：kairon CI 修复（P0-1）是全 L2 最高优先——152K LOC 项目恢复安全网
3. 与 MOF/M4、metaos 两方案的 Phase 0 并行推进（零文件冲突）
4. 三方案全部签核后，可考虑设立"L2 治理 Round"系列统一跟踪（复用 Round playbook §10）

---

## as_of: 2026-07-27（P0-D 附录·防脱钩锚点）

> 本子方案作为 master plan (`2026-07-27-integrated-governance-optimization-master-plan.md`) 的战术附件。
> **as_of 基线**: 2026-07-27。此后 workspace 持续演进, 本方案的"现状描述"可能已脱钩。
> **执行前必须**: 对照 master plan §P0 已落地项核实（三把锁接线 / 4 空 type / 44 dead entry 清理 / bus optional extra）, 勿凭本子方案的旧状态判断。
> **已变化项**（P0 后）: 见 master plan + gac-local-gate DEFAULT_POLICY（drift/doc-claims/layer-call-direction 已接）+ projects-capabilities.yaml（44 dead 已清）。
