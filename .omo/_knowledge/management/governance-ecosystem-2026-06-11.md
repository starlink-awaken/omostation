# §19 omo 仓治理债生态圈 (Governance Debt Ecosystem) — Round 45 起步

> **状态**: 起步 (Round 45 P0)
> **作者**: 老王
> **定位**: §11-§18 八章的**生态圈扩** — 把"治理债"从"omo 仓内"演化为"omostation 跨仓"
> **目的**: 给 omostation owner 1 份清晰路线图 (短期/中期/长期 3 视角), 让治理债永动机跨仓扩
> **链接**: §11-§18 八章 + §19 生态圈路线图

---

## §19.0 一句话总结

§19 把 §11-§18 八章**生态化** — 短期 (1-3 Round) 守 §18 闭环, 中期 (4-6 Round) 跨仓 lint-metrics, 长期 (7-12 Round) §12.6 跨仓债 E1-E4 落地. §19 不引入新债, 只把"§11-§18 已有" 演化为 "§19 路线图".

## §19.1 §11-§18 八章 → §19 生态圈扩 (3 视角路线图)

### §19.1.1 短期 (1-3 Round, R45-R47)

**目标**: 守 §18 6 守门点 + §17 R0 优秀评分, 不引入新债.

| Round | 主题 | 状态 |
|-------|------|------|
| R45 | §18.8 候选 1: 集成 lint-metrics 到其他仓 (kairon meta-stub) | ✅ R45 实质化 (模板 docs/cross-repo-rollout-template-2026-06-11.md) |
| R46 | §18.8 候选 2: §12.5.1 步骤 4 加 §17 metrics 跨仓聚合报告 | ✅ R46 实质化 (--include-metrics flag, 2026-06-11) |
| R47 | §18.8 候选 3: ci-lint.yml 加 §17 metrics 输出 + §18 健康度趋势图 | 🔄 R47 进行中 (artifact + plot-metrics.py) |

**§15 节奏守门**: 短期不期待新债, 守住 §18 R0 优秀即可.

### §19.1.2 中期 (4-6 Round, R48-R50)

**目标**: 跨仓 lint-metrics 接入 — 让其他仓也走 §17 健康度评分.

| Round | 主题 | 状态 |
|-------|------|------|
| R48 | kairon (meta-stub) 接入 §12.2 + lint-metrics (Python) | 🔄 R48 探路中 (2026-06-11 probe) |
| R49 | metaos L2 集成 §12.2 + lint-metrics (Python, 需 metaos owner 配合) | 🔄 R49 探路中 (2026-06-11 probe) |
| R50 | gbrain §12.2.2 TypeScript 适配 + lint-metrics (TS, 需 gbrain owner 配合) | 🔄 R50 探路中 (2026-06-11 probe) |

**§15 节奏守门**: 中期期待"跨仓债"出现 (1-2 项), 走 §15 5 阶段流程.

### §19.1.3 长期 (7-12 Round, R51-R56)

**目标**: §12.6 跨仓债 E1-E4 落地 (需各仓 owner 配合, 推不动 §11.6 老债, 跨仓债类似).

| Round | 主题 | 候选 |
|-------|------|------|
| R51-R53 | runtime executor 接入 AppendOnlyLog | §19.8 |
| R54-R56 | §18 全景扩到多仓 (3-5 仓各 1 §18 副本) | §19.9 |

**§15 节奏守门**: 长期期待"跨仓债" + "债生态扩", 但**不能强推** — 需各仓 owner 主动.

## §19.2 §18.8 候选 1: 集成 lint-metrics 到其他仓 (R45)

**动机**: §18.8 候选 1 提到"集成 lint-metrics 到其他仓", 但**需各仓 owner 配合**.

**实施路径**:
- R45 P0: 给 kairon 仓 (meta-stub) 写 1 份 `Makefile` + `tools/audit.sh` 模板 (Python)
- kairon owner 拿到后 `cp tools/audit.sh /path/to/kairon/` + 加 `.github/workflows/audit.yml`
- §12.2 5 步接入清单适用于任何 Python 仓, kairon 是 P0 试点

**§15 节奏**: R45 实质化后, 跨仓债发现率从 0 → 1 (新债预期 kairon 接入时漂出).

**§19 候选**: 留 §19.5 R48 跟进.

## §19.3 §18.8 候选 2: §12.5.1 步骤 4 加 §17 metrics 跨仓聚合 (R46 ✅)

**动机**: §12.5.1 (R26 起步) 3 步骤全实质化 (步骤 1-3 R27-R28), 步骤 4 (§17 metrics 跨仓聚合) 留候选.

**实施路径**:
- 改 `omo audit-rollout` 加 `--include-metrics` flag
- 跑 `omo logs audit --metrics` 各仓 + 聚合成 `audit-rollout-<date>-metrics.json`
- 跨仓聚合报告 + 健康度评分, 让"跨仓债" + "跨仓健康度"可比较

**§15 节奏**: R46 实质化后, 跨仓健康度报告可对比 (omostation R0 vs kairon R?).

**R46 P0 ✅实质化** (2026-06-11):
- `projects/omo/src/omo/omo_audit_rollout.py` 加 `--include-metrics` flag
- `_run_logs_metrics()` 跨仓跑 `omo logs audit --metrics` (优先 venv python →兜底 uv run)
- `aggregate_baselines(..., include_metrics=True)`聚合 `health_grade` + `debt_density`
- `render_rollout_table()` 加健康度列 (✅ R0 / ⚠️ R1-R2 / ❌ R3+)
- 退出码 3 = R3+ 危急, 报告仍生成
- 实测: omostation 仓 ✅ R0 (density=0.0000, 1535 locked drift 全历史锁)

## §19.4 §18.8 候选 3: ci-lint.yml 加 §17 metrics 输出 + 健康度趋势图 (R47)

**动机**: R43 P0 加 omo-lint-metrics job, 但**没接 §17 metrics 报告输出到 ci-lint.yml 的 artifacts**.

**实施路径**:
- ci-lint.yml 加 `actions/upload-artifact` 上传 §17 metrics JSON
- 月度 cron 跑时累积 `audit-rollout-<date>-metrics.json` + ci-lint run 的 metrics JSON
- 健康度趋势图 (`scripts/plot-metrics.py` ~50 行) 渲染 drift count / density / grade 趋势

**§15 节奏**: R47 实质化后, 跨多 Round 健康度可视化 (趋势图).

## §19.5 §19 候选 4: kairon 接入 §12.2 + lint-metrics (R48, P0+)

**动机**: §12.2 5 步接入清单 (Python) 适用于 kairon (Python 仓), kairon 是 §12.8 跨仓债 E4 留仓.

**实施路径**:
- R48 P0: 给 kairon 仓写 1 份接入模板 (`kairon/scripts/audit-baseline.sh` + `.github/workflows/audit.yml`)
- kairon owner 拿到后接入, 跨仓聚合自动扩 1 仓
- §12.6 跨仓债 E4 实质化 (1/4)

**§15 节奏**: R48 实质化后, §12.6 E4 治本.

## §19.6 §19 候选 5: metaos L2 集成 §12.2 + lint-metrics (R49)

**动机**: metaos 是 L2 编排引擎 (11 MCP tools), 与 omo 仓同 Python — §12.2 5 步接入适用.

**实施路径**:
- R49 P0: 需 metaos owner 配合, 在 metaos 仓加 `tools/audit.sh` + `.github/workflows/audit.yml`
- metaos owner 接入后, 跨仓聚合自动扩 1 仓 (omostation + kairon + metaos)
- §12.6 跨仓债 (metaos) 实质化 (1/4 → 2/4)

**§15 节奏**: R49 实质化需 owner 配合, 推不动时退回到 R48 + 文档化.

## §19.7 §19 候选 6: gbrain §12.2.2 TypeScript 适配 (R50)

**动机**: gbrain 是 TS 仓 (真仓非 meta-stub), §12.2.2 TypeScript 适配示例已写 (R23), 但**实际接入**待 R50.

**实施路径**:
- R50 P0: gbrain owner 拿到 §12.2.2 TS 模板后接入
- gbrain lint-metrics 走 zod schema 校验 (替换 Pydantic)
- 跨仓聚合扩 1 仓 (omostation + kairon + metaos + gbrain = 4 仓)
- §12.6 跨仓债 (gbrain) 实质化 (1/4 → 2/4)

**§15 节奏**: R50 实质化需 gbrain owner 配合, 推不动时退回到 R49 + 文档化.

## §19.8 §19 候选 7: runtime executor 接入 AppendOnlyLog (R51-R53)

**动机**: runtime 是 L1 运行时, executor 跑 agent (含 subprocess 进程), 与 omo 仓同 Python — 5 步接入适用.

**实施路径**:
- R51: runtime 仓接入基线
- R52: runtime cron 跑 audit-rollout
- R53: runtime lint-metrics 集成
- §12.6 跨仓债 (runtime) 实质化 (1/4 → 2/4 → 3/4)

**§15 节奏**: R51-R53 实质化需 owner 配合, 推不动时分阶段退.

## §19.9 §19 候选 8: §18 全景扩多仓 (R54-R56)

**动机**: §18 是 omo 仓内全景图. 跨仓接入后, §18 需扩为"多仓全景" — 1 份文档覆盖 5 仓治理.

**实施路径**:
- R54: §18 扩"§18.10 多仓对比"段 (omostation vs kairon vs metaos vs gbrain vs runtime)
- R55: §18 加 §18.11 跨仓健康度 dashboard (5 仓 R0-R5 评分对比)
- R56: §18 完整化 (1 份文档覆盖 5 仓治理全景)

**§15 节奏**: R54-R56 实质化需 5 仓 owner 配合, 推不动时退回到 R53.

## §19.10 §11-§18 vs §19 关系

| 章节 | 视角 | 形式 | §19 生态圈扩 |
|------|------|------|---------------|
| §11 | omo 仓内实现 | 代码 + 注释 | §19.5 R48 跨仓扩 |
| §12 | 跨仓契约 | 4 不变量 + 5 步 | §19.5-§19.9 跨仓实施 |
| §13 | lint 工具 | 7 规则 | §19.5 R48 lint-metrics 扩 |
| §14 | CI/CD | 6 守门点 | §19.5 R48 ci-lint 扩 |
| §15 | 治理债流程 | 5 阶段 | §19 节奏守门 |
| §16 | 实战案例 | 2 案例 (P3-X / P3-Y) | §19.5-§19.9 跨仓案例 |
| §17 | 度量 | 4 维度 | §19.3 R46 + §19.4 R47 |
| §18 | 全景图 | 5 视角 | §19.10 §18 扩多仓 |
| **§19** | **生态圈路线图** | **3 视角 12 Round** | **§11-§18 跨仓扩** |

**§19 = §11-§18 的"未来扩"** — 不引入新内容, 指引短期/中期/长期 12 Round 跨仓扩.

## §19.11 Round 45+ 候选 (本节填充)

- [x] §19.0 起步 (本 commit)
- [x] §19.1 §11-§18 八章 → §19 生态圈路线图 (3 视角 12 Round)
- [x] §19.2 §18.8 候选 1: 集成 lint-metrics 到其他仓 (R45)
- [x] §19.3 §18.8 候选 2: §12.5.1 步骤 4 加 §17 metrics 跨仓聚合 (R46)
- [x] §19.4 §18.8 候选 3: ci-lint.yml 加 §17 metrics 输出 + 趋势图 (R47)
- [x] §19.5 §19 候选 4: kairon 接入 §12.2 + lint-metrics (R48, P0+)
- [x] §19.6 §19 候选 5: metaos L2 集成 (R49)
- [x] §19.7 §19 候选 6: gbrain §12.2.2 TypeScript 适配 (R50)
- [x] §19.8 §19 候选 7: runtime executor 接入 AppendOnlyLog (R51-R53)
- [x] §19.9 §19 候选 8: §18 全景扩多仓 (R54-R56)
- [x] §19.10 §11-§18 vs §19 关系
- [x] §19.11 Round 45+ 候选
- [x] R46 ✅ `--include-metrics` flag 实质化 (2026-06-11, omo_audit_rollout.py)
- [x] R47 🔄 ci-lint artifact + plot-metrics.py (2026-06-11, worker 并行)
- [x] R48 🔄 kairon 探路中 (.omo/_delivery/kairon-probe-2026-06-11.md)
- [x] R49 🔄 metaos 探路中 (.omo/_delivery/metaos-probe-2026-06-11.md)
- [x] R50 🔄 gbrain 探路中 (.omo/_delivery/gbrain-probe-2026-06-11.md)

---

**§19 章节总览** (Round 46-47 实质化中):

| 子节 | 主题 | 状态 |
|------|------|------|
| §19.0 | 一句话总结 | ✅ Round 45 |
| §19.1 | 3 视角路线图 (短期/中期/长期 12 Round) | ✅ Round 45 |
| §19.2 | R45 §18.8 候选 1 (lint-metrics 跨仓) | ✅ Round 45 |
| §19.3 | R46 §18.8 候选 2 (§17 metrics 跨仓聚合) | ✅ Round 45 |
| §19.4 | R47 §18.8 候选 3 (健康度趋势图) | ✅ Round 45 |
| §19.5 | R48 §19 候选 4 (kairon 接入) | ✅ Round 45 |
| §19.6 | R49 §19 候选 5 (metaos L2 集成) | ✅ Round 45 |
| §19.7 | R50 §19 候选 6 (gbrain TS 适配) | ✅ Round 45 |
| §19.8 | R51-R53 §19 候选 7 (runtime 接入) | ✅ Round 45 |
| §19.9 | R54-R56 §19 候选 8 (§18 全景扩多仓) | ✅ Round 45 |
| §19.10 | §11-§18 vs §19 关系 | ✅ Round 45 |
| §19.11 | Round 45+ 候选 | ✅ Round 45 |
| **总** | **§19 12 子节** | ✅ 起步 |
