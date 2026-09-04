---
status: planned
lifecycle: plan
owner: governance-team
last_updated: 2026-07-31
review-state: metadata-only
metadata-migrated-at: 2026-07-31
type: ephemeral
---
# MOF/M4 模型驱动体系治理优化方案（战略 + 架构 + 落地规划）

> 日期: 2026-07-25
> 状态: 提案（待 D1–D4 决策签核后进入 Round 执行）
> 范围: `projects/ecos/src/ecos/ssot/mof/`（YAML 轨）、`projects/model-driven/`（Python 轨）、`bin/mof/` 与 `ecos/ssot/tools/mof-*` 工具层、`.omo/_truth/registry/mof-capabilities.yaml`
> 依据: 2026-07-25 双轨深度架构分析（本文件 §2 诊断）

## 1. 摘要

MOF/M4 体系已是 workspace 中治理成熟度最高的子系统（5-check 自反入门禁、59 项回归、Health Score 历史 100/100、8 阶段争议被制度性封禁）。当前风险不在"散架"，而在三类结构性漂移：

1. **治理注册面自身漂移** —— 治理系统没守住自己的注册表（`mof-capabilities.yaml` 路径/统计 stale）
2. **双轨同步成本隐性化** —— YAML/Python 双 SSOT 靠字符串锚和阈值对齐，值级语义无全绿门
3. **接口层半建** —— CLI 弃用未拆、MCP 面标称与实现不符、codegen 名不副实、X1-X4 门禁硬编码浅启发式

本方案给出 3 个 Phase、9 个 deliverable、4 个决策点，全部映射到现有 Round playbook（AGENTS.md §10）与 GaC 门禁，不引入新流程。

## 2. 诊断（证据摘要）

| # | 问题 | 证据 | 性质 |
|---|------|------|------|
| Q1 | `mof-capabilities.yaml` 漂移 | tool path 指向 `bin/mof-*` 旧路径（实际 `bin/mof/`）；model_stats 1177 vs 实际 1419 节点、46 vs 58 schema | P71 类 A 声明/执行鸿沟 |
| Q2 | MOF 工具双层并存 | `bin/mof/` 脚本 vs `ecos/ssot/tools/mof-*.py`（30+），mof-scan/mof-enforce 命名重叠，边界靠惯例 | 架构债 |
| Q3 | M2 双真源 | ecos `m2/*.yaml`（58）与 model-driven `m2_lifecycle.py`（25 dataclass），值级（state_machine 转移合法性）只靠阈值 | 双轨同步风险 |
| Q4 | CLI 弃用未拆 | `model-driven cli.py:220` 每次运行打弃用警告但功能完整 | 双入口冗余 |
| Q5 | MCP 面半建 | `MCPServer` 非协议实现；M1 标称 41 tools vs 代码 28；agora 目录 `mcp_endpoint` 为空 | 声明/实现不符 |
| Q6 | `tool_generate` 名不副实 | 名义 codegen，实际 YAML/JSON 模板输出 | 能力虚标 |
| Q7 | X1-X4 门禁硬编码浅启发式 | `gates.py:242-278` 强制所有 transition 过浅评估器，误拦风险；治理逻辑渗入引擎层 | 架构张力 |
| Q8 | OMOBridge 直接写 `.omo/` | 与".omo 变更须走 broker"红线张力（虽有 fcntl 锁）；已见测试残留 debt | 合规缝隙 |
| Q9 | 文档数字失真 | model-driven 内 ARCHITECTURE/CAPABILITY-MAP 的工具数/类型数/测试数与实际不符 | SSOT 纪律残留 |

## 3. 战略目标与北极星

**北极星（12 周）**：MOF/M4 体系达到"**注册面零漂移、双轨单真源、接口声明=实现**"，且全部改进通过既有门禁可验证、不回退 Health Score。

三条战略主线：

- **S1 守自（Self-governance）**：治理系统先治理自己。注册面、文档数字、工具清单纳入机器校验，消灭"守门人无人守"区。
- **S2 收敛（Convergence）**：每个事实只有一个真源。双轨处明确方向并机制化，重叠工具层并轨。
- **S3 诚实（Honesty）**：接口声明与实现对齐——做不到的降级声明（冻结/弃用），做得到的补齐实现。与 P73/P78 实证主义一致。

## 4. 治理原则（不可违反）

- **P52**：不直接改 m3.yaml 字段语义、不改 model-driven 引擎核心；扩展走 M3 扩展机制与 ADR。
- **P72**：不过载历史路径——8 阶段不复活（ADR-0146 永久封禁），本方案任何条目不得触及 `LifecycleStage` 枚举。
- **P74**：每个 deliverable 走 governance-agent profile + workflow run，留 evidence；新增检查进 `diff_checks` 覆盖。
- **Round 纪律**（AGENTS.md §10）：每 Phase 按 R-patch/R-feature 类型走 7 步闭环，Health Score delta ≥ 0。
- **ADR-0203**：落地执行时每轮先 `start` 再改文件。

## 5. 分阶段落地规划

### Phase 0 — 守自止血（Week 0–2，R-patch 型，1–2 ADR）

目标：修复注册面与文档漂移，并把这些面纳入机器守门（治本，非一次性清扫）。

| Deliverable | 内容 | 验证 |
|---|---|---|
| P0-1 注册表修复 | 修正 `mof-capabilities.yaml` 工具路径（`bin/mof/`）与 model_stats；过期字段改为指针或加 `as_of` 标记 | `mof-manage validate`（若无校验能力则一并补齐，见 P0-2） |
| P0-2 注册表漂移门 | 新增 `bin/mof/check-mof-capabilities-drift.py`：比对注册表 path 存在性、stats 与实测计数，接入 gac-local-gate（CI-only 或 strict） | gate 新增 check 全绿；故意注入漂移可检出（测试用例） |
| P0-3 文档数字收口 | model-driven 内文档中的工具数/类型数/测试数全部指针化到 registry 或 `as_of` 快照 | `doc-ssot-lint` 通过；diff review |
| P0-4 MCP 口径对齐 | M1 `MCPTOOL-MODEL-DRIVEN.yaml` 的 41 tools 与代码 28 对齐（改声明为实际值 + TODO 指针） | `mof-schema-validate` 通过 |

退出标准：P0-2 漂移门上线并全绿；`m4-health-score --compare` delta ≥ 0。

### Phase 1 — 双轨收敛（Week 2–8，R-feature 型，3+ ADR）

目标：消灭双真源与工具层重叠，每个事实单真源。

| Deliverable | 内容 | 验证 |
|---|---|---|
| P1-1 M2 单真源决策与实施（依赖 D3） | 推荐方向：**ecos `m2/*.yaml` 为唯一 SSOT**，model-driven `m2_lifecycle.py` 改为从 YAML 生成（生成器入 ecos 工具链，生成物头标 DO NOT edit + 溯源指针，与 mof-bridge-sync 同范式）。25 个 Python-only schema 先迁 YAML 再切生成 | `mof-bootstrap` 5-check 全绿；model-driven 测试全绿；新旧 schema diff 为空 |
| P1-2 值级校验全绿 | `mof-validate` 对 state_machine 转移合法性从阈值通过改为 strict（先修现网违例，再切 strict） | mof-validate strict 0 err；回归测试 |
| P1-3 工具层并轨 | 清点 `bin/mof/` vs `ecos/ssot/tools/mof-*` 全部工具，按"ecos 工具 = 模型面 / bin 工具 = workspace 门面 wrapper"规则定边界；重叠项（mof-scan/mof-enforce）保留一处实现、另一处薄 wrapper；注册表同步更新 | 注册表漂移门（P0-2）覆盖新边界；命名冲突清单归零 |
| P1-4 CLI 处置（依赖 D1） | 推荐：删除 `model-driven` 独立 CLI（cockpit adapter 已是消费面），或降级为仅 `--help` 打印迁移指引 | cockpit 侧引用测试全绿；无 import 残留 |

退出标准：M2 单一真源 + 生成链入门禁；工具层零命名冲突；health delta ≥ 0。

### Phase 2 — 引擎治理边界与接口诚实（Week 8–12，R-meta 型，3–4 ADR）

目标：治理逻辑从引擎硬编码转为声明式配置，接口声明=实现。

| Deliverable | 内容 | 验证 |
|---|---|---|
| P2-1 X1-X4 门禁外置 | `gates.py:242-278` 的硬编码全局评估改为读取声明式配置（gate policy YAML，注册进 `governance-checks.yaml` 体系）；评估器启发式规则显式化并可按 transition 类型裁剪；保留 `register_check` 逃生口 | 现有 transition 行为快照对比无意外变化；误拦用例入库回归 |
| P2-2 OMOBridge 合规化 | `.omo/` 写入改走注册 broker 路径（omo CLI/MCP 或显式登记的 audited path）；清理测试残留 debt（如 DEBT-20260723142431） | ssot-guardian 无 direct_omo_io 违规；残留 debt closeout |
| P2-3 MCP 面对齐（依赖 D2） | 推荐：**显式冻结**——agora 目录条目标 `status: frozen` + M1 节点声明真实 2 工具面；若决定接通，则 `MCPServer` 28 工具经 FastMCP 全量暴露并登记 endpoint（工作量 +1 周） | agora 目录与实际一致；doctor/integrations 报告无矛盾 |
| P2-4 codegen 正名（依赖 D4） | 推荐：`tool_generate` 改名/降级声明为"模板投影"，能力地图同步；真 codegen 管线单独立项（出本方案范围） | 文档与实现对齐；能力地图 drift check |

退出标准：引擎层无硬编码治理策略；`.omo/` 写入全部经 audited path；接口声明=实现。

## 6. 决策点（需签核后才进入对应 Phase）

| # | 决策 | 选项 | 推荐 | 影响 |
|---|------|------|------|------|
| D1 | model-driven CLI 处置 | A 删除 / B 保留静默 / C 降级为迁移指引 | **A（删除）**，cockpit 已是唯一人类入口（ARCHITECTURE.md §3 单入口原则） | Phase 1 工作量 ±3 天 |
| D2 | MCP 面 | A 冻结（声明 2 工具）/ B 全量接通 agora（28 工具 + endpoint） | **A（冻结）**——当前无 agent 侧消费实证；接通留待有真实路由需求 | Phase 2 工作量 ±1 周 |
| D3 | M2 真源方向 | A YAML 为 SSOT + Python 生成 / B Python 为 SSOT + YAML 生成 / C 维持双轨加锚 | **A**——与"声明侧 YAML、执行侧投影"全局方向一致；B 与 mof-bridge-sync 现有方向冲突 | Phase 1 主工作量 |
| D4 | codegen | A 降级声明为模板投影 / B 立项真 codegen 管线 | **A**——真管线无当前需求方 | 仅声明变更 |

## 7. 度量与门禁（KPI）

| 指标 | 基线（2026-07-25） | 目标（12 周） | 测量 |
|---|---|---|---|
| M4 Health Score | 历史 100/100 | 全程 delta ≥ 0，结束 = 100 | `bin/mof/m4-health-score.py --compare` |
| 注册表漂移项 | ≥3（Q1） | 0，且由漂移门机器守住 | P0-2 check |
| M2 真源数 | 2（YAML + Python dataclass） | 1 + 生成链 | bootstrap check_3/5 |
| 值级校验 | 阈值通过 | strict 0 err | `mof-validate --strict` |
| 接口声明符合度 | 41≠28、endpoint 空 | 声明 = 实现 | mof-schema-validate + doctor |
| 工具命名冲突 | ≥2（mof-scan/enforce） | 0 | 注册表清单 diff |

每 Phase 结束跑 Round playbook 三闸门：G-Tests（`tests/integration/m4_metamodel/run_all.py`）、G-Reflex（`mof-bootstrap.py all`）、G-Health（delta ≥ 0）。

## 8. 风险与回滚

| 风险 | 等级 | 缓解 / 回滚 |
|---|---|---|
| P1-1 生成链切换破坏 model-driven 消费方（cockpit/l4-kernel import dataclass） | 高 | 生成物保持相同模块路径与符号名；切换 PR 带消费方全量测试；回滚 = revert + 恢复手写文件 |
| P2-1 门禁外置改变 transition 行为 | 中 | 先做行为快照（现有 transition 矩阵全量录制），外置后 diff 为空才允许合入 |
| D3 选 A 的迁移量超预期 | 中 | 25 个 schema 分批迁移（每批 ≤8 个），每批独立 PR 独立验证 |
| 多 agent 并发改 SSOT 漂移 | 中 | 全程 worktree + PR（gac-worktree.sh），ADR 先占号（next-adr-id.py --claim） |
| 治理面变更触发 P74 沉默告警 | 低 | 新增 check 同步注册 `diff_checks`，走 mof-model-change workflow |

## 9. 执行纪律与时间线

```
Week 0-2   Phase 0（R-patch）: P0-1..P0-4  → ADR-02xx（注册面守自）
Week 2-8   Phase 1（R-feature）: P1-1..P1-4 → ADR-02xx（M2 单真源）+ ADR-02xx（工具并轨）+ ADR-02xx（CLI）
Week 8-12  Phase 2（R-meta）: P2-1..P2-4   → ADR-02xx（门禁外置）+ ADR-02xx（OMOBridge）+ ADR-02xx（接口诚实）
```

每 deliverable 一个 PR（每 PR 单 lane），ADR 先占号，执行顺序严格依赖决策点签核（D1/D2/D3/D4）。

## 10. 本方案的边界（明确不做）

- 不触碰 `LifecycleStage` 7 阶段枚举（ADR-0146 永久封禁）
- 不建真 codegen 管线（D4 选 A 后的遗留项，单独立项）
- 不改 m3.yaml 既有字段语义（P52）
- 不引入新治理流程/新门禁框架——全部复用 Round playbook + gac-local-gate
- MCP 全量接通不在本方案（D2 选 A 冻结）

## 11. 下一步

1. 签核 D1–D4（建议全选推荐项，一轮决策会即可）
2. Phase 0 按 Round playbook 起 `mof-model-change` / `project-doc-change` run 执行
3. 首个 ADR 占号：`python3 bin/adr/next-adr-id.py --session <session> --claim`

---

## as_of: 2026-07-27（P0-D 附录·防脱钩锚点）

> 本子方案作为 master plan (`2026-07-27-integrated-governance-optimization-master-plan.md`) 的战术附件。
> **as_of 基线**: 2026-07-27。此后 workspace 持续演进, 本方案的"现状描述"可能已脱钩。
> **执行前必须**: 对照 master plan §P0 已落地项核实（三把锁接线 / 4 空 type / 44 dead entry 清理 / bus optional extra）, 勿凭本子方案的旧状态判断。
> **已变化项**（P0 后）: 见 master plan + gac-local-gate DEFAULT_POLICY（drift/doc-claims/layer-call-direction 已接）+ projects-capabilities.yaml（44 dead 已清）。
