---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# 代码质量基线 — Phase 16 完成后

> 日期: 2026-06-03
> 范围: kairon 33 包
> 工具: ruff 0.15.15 (target-version: py313, line-length: 120)
> 历史代码质量基线 / reference only。本文记录 Phase 16 收口时的质量快照，不是当前包数量、当前 lint 状态、当前测试分布或当前硬编码风险 SSOT。
> 当前质量与项目事实请回看 `/.omo/PROJECTS.yaml`、对应项目 CI/测试结果与当前治理审计证据。

---

## 执行摘要

| 指标 | 值 | 评价 |
|------|-----|------|
| ruff errors (全量) | **0** | 🟢 优秀 |
| 零测试包 | **2** / 33 | 🟡 可接受 |
| 硬编码绝对路径 | **0** | 🟢 优秀 |
| sys.path.insert 残留 | **12 文件** | 🟡 需清理（主要在测试） |
| except ImportError 残留 | **~70 处** | 🟡 技术债务 |
| Python 版本目标 | 3.13+ | 🟢 一致 |

**总体评价: A-** — 代码质量相比 2026-05-21 的审计（ontoderive 1,307 errors, kos 5,263 errors）有**质的飞跃**。

---

## 1. Ruff 检查结果

### 全量统计

```bash
$ cd projects/kairon && ruff check packages/ --statistics
# 结果: 0 errors (所有包)
```

### 逐包统计

| 包 | Errors | 状态 |
|----|:------:|:----:|
| agent-hub | 0 | 🟢 |
| agent-runtime | 0 | 🟢 |
| agora | 0 | 🟢 |
| codeanalyze | 0 | 🟢 |
| core-models | 0 | 🟢 |
| cron-service | 0 | 🟢 |
| ecos | 0 | 🟢 |
| eidos | 0 | 🟢 |
| engine-core | 0 | 🟢 |
| eu-pricing | 0 | 🟢 |
| forge | 0 | 🟢 |
| gc-engine | 0 | 🟢 |
| iris | 0 | 🟢 |
| kairon-assistant | 0 | 🟢 |
| kairon-voice | 0 | 🟢 |
| kaironcloud-billing | 0 | 🟢 |
| kos | 0 | 🟢 |
| kronos | 0 | 🟢 |
| llm-gateway | 0 | 🟢 |
| metaos | 0 | 🟢 |
| minerva | 0 | 🟢 |
| observability | 0 | 🟢 |
| ontoderive | 0 | 🟢 |
| pontus | 0 | 🟢 |
| shared-lib | 0 | 🟢 |
| sharedbrain-bridge | 0 | 🟢 |
| sharedbrain-standalone | 0 | 🟢 |
| sophia | 0 | 🟢 |
| ssot | 0 | 🟢 |
| symphony-protocol | 0 | 🟢 |
| wksp | 0 | 🟢 |

**历史对比** (DEBT-ANALYSIS.md 2026-05-21):

| 包 | 2026-05-21 | 2026-06-03 | 改善 |
|----|:----------:|:----------:|:----:|
| ontoderive | 1,307 | 0 | ✅ 清零 |
| kos | 5,263 | 0 | ✅ 清零 |
| minerva | 955 | 0 | ✅ 清零 |
| sophia | 121 | 0 | ✅ 清零 |

---

## 2. 测试覆盖率

### 测试分布

| 包 | 测试文件数 | 状态 |
|----|:----------:|:----:|
| ontoderive | 50 | 🟢 |
| minerva | 34 | 🟢 |
| kos | 24 | 🟢 |
| eidos | 19 | 🟢 |
| agora | 49 | 🟢 |
| codeanalyze | 13 | 🟢 |
| ecos | 12 | 🟢 |
| forge | 11 | 🟢 |
| iris | 10 | 🟢 |
| kronos | 9 | 🟢 |
| ssot | 11 | 🟢 |
| shared-lib | 25 | 🟢 |
| ... | ... | ... |

### 零测试包

| 包 | 说明 | 风险 |
|----|------|------|
| **sharedbrain-standalone** | 分解残留包 | 中 — 用途待确认 |
| **wksp** | Workspace CLI | 低 — 工具包 |

**建议**: sharedbrain-standalone 若保留，应补充最小测试基线（至少 3-5 个核心功能测试）。

---

## 3. 路径与可移植性

### 硬编码绝对路径

```bash
grep -r "/Users/xiamingxing/" packages/ --include="*.py" -l
# 结果: 无匹配 ✅
```

**历史对比**: ../design/INSIGHTS-AND-ROADMAP.md (2026-05-23) 列出以下文件含硬编码路径：
- `eidos/src/eidos/pipeline/__init__.py`
- `eidos/src/eidos/pipeline/presets.py`
- `eidos/src/eidos/mcp_server.py`
- `kos/kos/commands/ingest.py`
- `gateway/bin/*`

**当前状态**: 上述文件在 kairon packages 中**不再包含 `/Users/xiamingxing/` 硬编码路径**。✅ 已清理。

### sys.path.insert 残留

```bash
grep -r "sys.path.insert" packages/ --include="*.py" -l
```

**存在位置**:

| 文件 | 次数 | 说明 | 需清理 |
|------|:----:|------|:------:|
| `eidos/tests/*.py` (6 个文件) | 6 | 测试文件插入 `src/` 路径 | 🟡 低优 |
| `metaos/src/metaos/onboard.py` | 1 | 运行时插入路径 | 🔴 建议修复 |
| `metaos/src/metaos/metaos.py` | 1 | 运行时插入路径 | 🔴 建议修复 |
| `metaos/src/metaos/dashboard.py` | 1 | 运行时插入路径 | 🔴 建议修复 |
| `metaos/src/metaos/scenarios/test_07_coverage.py` | 1 | 运行时插入路径 | 🔴 建议修复 |

**分析**: 测试文件中的 `sys.path.insert` 是常见模式（用于 `pytest` 不通过 pip 安装时的路径解析），风险较低。但 **metaos 源文件中的 4 处插入**是运行时债务，影响可分发性。

---

## 4. 适配器模式债务

```bash
grep -r "except ImportError" packages/ --include="*.py" -c | sort -t: -k2 -nr | head -15
```

**分布**:

| 文件/包 | 次数 | 说明 |
|---------|:----:|------|
| `kronos/tests/test_basic.py` | 14 | 测试适配器 |
| `shared-lib/tests/test_events.py` | 9 | 测试适配器 |
| `engine-core/src/engine_core/worker_dispatcher.py` | 9 | **运行时适配器** |
| `agora/src/agora/mcp_tools.py` | 9 | **运行时适配器** |
| `engine-core/src/engine_core/lifecycle_manager.py` | 8 | **运行时适配器** |
| `ontoderive/engine/core/pipeline.py` | 7 | **运行时适配器** |
| `sophia/tests/test_compiler.py` | 6 | 测试适配器 |
| `kos/src/kos/indexer/engine.py` | 6 | **运行时适配器** |
| `kronos/src/kronos/fetch_router.py` | 5 | **运行时适配器** |
| `engine-core/src/engine_core/hatcher_core.py` | 5 | **运行时适配器** |

**分析**: 
- 测试文件的适配器模式风险低（仅在测试环境运行）
- **运行时适配器**（engine-core, agora, ontoderive, kos, kronos）共 ~49 处，是 ../design/INSIGHTS-AND-ROADMAP.md 中识别的核心债务
- 这些 `try/except ImportError` 将集成失败从编译时推迟到运行时，开发期友好但运维期不友好

**INSIGHTS-AND-ROADMAP.md 建议的演进路径**:
```
try/except → Protocol/ABC 协议 → 可选安装的依赖包
```

**当前进度**: 仍停留在第一阶段（try/except）。Protocol/ABC 重构尚未开始。

---

## 5. 与历史审计的对比

| 维度 | 2026-05-21 (DEBT-ANALYSIS) | 2026-06-03 (当前) | 变化 |
|------|---------------------------|-------------------|------|
| ruff errors (kos) | 5,263 | 0 | ✅ 清零 |
| ruff errors (ontoderive) | 1,307 | 0 | ✅ 清零 |
| ruff errors (minerva) | 955 | 0 | ✅ 清零 |
| ruff errors (sophia) | 121 | 0 | ✅ 清零 |
| 零测试项目 | 3 (SharedBrain 210万行, Forge, pallas) | 2 (sharedbrain-standalone, wksp) | ✅ 大幅改善 |
| 硬编码路径 | 多处 | 0 | ✅ 清零 |
| 适配器模式 | 未量化 | ~70 处 | 🟡 首次量化 |

---

## 6. 风险矩阵

| 风险 | 当前状态 | Phase 17 影响 |
|------|----------|---------------|
| ruff 回归 | 低 — 全绿 | 需保持 CI 强制 |
| 零测试包膨胀 | 低 — 仅 2 个 | 新增包必须含测试 |
| 硬编码路径回潮 | 低 — 已清零 | PR review 中检查 |
| sys.path.insert (运行时) | 中 — metaos 4 处 | 影响可分发性 |
| 适配器模式 | 中 — ~49 处运行时 | 运行时故障隐患 |

---

## 7. 建议

### P0（Phase 17 前）
1. **保持 ruff 零错误**: CI 中 `ruff check packages/` 必须强制通过
2. **补充 sharedbrain-standalone 测试**: 至少 3-5 个核心测试

### P1（Phase 17 期间）
3. **清理 metaos 运行时 sys.path.insert**: 4 处改为相对导入或 entry_points
4. **监控新增包的测试覆盖**: 禁止零测试包进入 workspace

### P2（Phase 17 后）
5. **适配器模式重构试点**: 选择 1-2 个包（建议从 engine-core 或 agora 开始）将 `try/except ImportError` 替换为 `Protocol/ABC`

---

*基线时间: 2026-06-03*
*验证命令: `ruff check packages/ --statistics`, `grep -r "/Users/xiamingxing/" packages/`, `grep -r "except ImportError" packages/`*
