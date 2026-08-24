# BOS Contract Linter Phase 2 — 预部署分析与评估

> 日期: 2026-06-25
> 作者: omostation P110+ (Phase 2)
> 关联: 提案 paste_1.txt (BOS Contract Linter Phase 2: Intelligence 作战包 v1.0)
> 状态: ⚠️ Phase 2 **可执行但需调整**, 标注 4 项必要调整

---

## 1. Phase 2 范围

| 维度 | Phase 0 v0.1 (现状) | Phase 2 v0.2 (提案) | 增量 |
|:-----|:-------------------|:--------------------|:-----|
| 主验证 (internal/scope/action) | ✅ | ✅ | 不变 |
| **--explain <error-id>** | ❌ | ✅ 新增 | 自然语言解释 |
| **--impact <uri>** | ❌ | ✅ 新增 | 影响分析 (direct/affected_files) |
| Panel 渲染 | ❌ | ✅ 新增 | rich.panel 用于 --explain |
| 工作量 | 0 | ~80L 新增代码 + 集成 | 中 |

**Phase 2 价值**:
- `--explain`: MTTR 从小时 → 分钟
- `--impact`: 变更前展示涟漪效应, 支持知情决策

---

## 2. 前置条件检查 (3 项)

### 2.1 ✅ 满足的前置条件 (3/3)

| # | 条件 | 状态 | 证据 |
|:-:|:-----|:----:|:-----|
| 1 | Phase 0 v0.1 已实施 | ✅ | `mof_contract_lint.py` (326L) 已 commit (197d670b) |
| 2 | rich.panel 在 deps | ✅ | `rich>=15.0.0` 已安装 (含 panel) |
| 3 | `--explain` / `--impact` 在 v0.1 中**不存在** | ✅ | grep 确认 0 匹配 |

### 2.2 ⚠️ 提案关键问题 (1 项, 重要)

**提案 file_mappings 只覆盖 3/100 services (3%)**:
- ✅ (`governance`, `audit`) → 2 services 命中
- ✅ (`analysis`, `research`) → 1 service 命中
- ✅ (`memory`, `kos/search`) → 0 service 命中 (提案 key 错误, 实际 URIs 是 `bos://memory/kos/search` 但 domain 字段是 `memory`)
- ❌ 其他 97 services `--impact` 输出空数组

**影响**: 用户对 97% services 跑 `--impact` 看不到任何文件关联, **功能价值大打折扣**

---

## 3. 详细风险评估

### 3.1 高风险点 (2 个)

| 风险 | 触发条件 | 缓解措施 |
|:-----|:---------|:---------|
| **R1: file_mappings 不覆盖 97% services** | 用户跑 `--impact bos://memory/kos/search` 看不到受影响文件 | **A1 调整**: 扩展 file_mappings 到 12 个常用 key |
| **R2: explain_error 字典只 2 个 error_id** | 用户对 `SCOPE_VALIDATION_SKIPPED` / `ACTION_NAMING_CONVENTION` 跑 --explain 返回 "No explanation" | **A2 调整**: 扩展 explanations 字典到 4 个 (覆盖 v0.1 全部规则) |

### 3.2 中风险点 (2 个)

| 风险 | 触发条件 | 缓解措施 |
|:-----|:---------|:---------|
| **R3: analyze_impact 的 "direct_dependencies" 启发式太粗糙** | 仅基于 domain+module_path 包含判断, 假阳/假阴 | ✅ 提案已标记 "rule-based" + "production would use graph analysis" |
| **R4: v0.2 重写整个 v0.1 文件** | 替换而非增量, 风险面大 | **A3 调整**: 在 v0.1 增量修改, 不重写 |

### 3.3 低风险点 (1 个)

| 风险 | 触发条件 | 缓解措施 |
|:-----|:---------|:---------|
| **R5: Panel 渲染在某些 terminal 不支持** | 旧 terminal 无 rich | rich 自适应, 默认降级到纯文本 |

---

## 4. 投资回报 (ROI) 评估

### 4.1 量化收益

| 维度 | Phase 0 v0.1 | Phase 2 v0.2 |
|:-----|:--------------|:--------------|
| MTTR (Mean Time To Repair) | 小时级 | 分钟级 (--explain) |
| 变更前影响分析 | ❌ 无 | ✅ 部分覆盖 (--impact, 但需 A1 扩展) |
| 错误码理解 | 需读源码 | 自然语言指南 |
| 工具智能化 | 静态分析 | 智能解释 + 影响分析 |

### 4.2 工作量评估

| 任务 | 估时 |
|:-----|:----:|
| 增量添加 `--explain` (A2: 扩展字典 4 个 error_id) | 15 min |
| 增量添加 `--impact` (A1: 扩展 file_mappings 12 个 key) | 25 min |
| 增量 main() (2 flag) | 10 min |
| 单元验证 (4 模式 × 2 新 flag) | 15 min |
| ADR + commit | 10 min |
| **合计** | **~75 min** |

### 4.3 ROI 评分

| 维度 | 评分 | 备注 |
|:-----|:----:|:-----|
| 实施风险 | 🟢 低 (3 高风险 mitigation 充分) |
| 实施工作量 | 🟡 中 (~75 min, 略大于 Phase 0) |
| 长期价值 | 🟢 高 (--explain 降低 MTTR, --impact 预防破坏) |
| 与 Phase 0 兼容性 | 🟢 完全兼容 (向后兼容, 默认行为不变) |
| **总评** | **🟢 值得执行 (但需 A1+A2 调整)** |

---

## 5. 设计调整 (vs 提案, 4 项必要)

### 5.1 必要调整 (4 项)

| 编号 | 调整 | 原因 | 估时 |
|:-----|:-----|:-----|:----:|
| **A1** | file_mappings 从 3 key 扩展到 12 key (覆盖 ~70% services) | 97% 未覆盖问题 | +15 min |
| **A2** | explanations 字典从 2 扩展到 4 (含 SCOPE_VALIDATION_SKIPPED + ACTION_NAMING_CONVENTION) | 50% error_id 未解释 | +10 min |
| **A3** | 增量修改 v0.1 文件 (非重写), 复用现有 326L + 新增 ~80L | 风险控制 + diff 可读 | 必需 |
| **A4** | 添加 --explain 和 --impact 退出码: 0 (成功) / 1 (未找到 error_id 或 URI) | CI 集成友好 | +5 min |

### 5.2 12 个扩展 file_mappings (A1)

| (domain, action) | URI 示例 | 受影响文件 (推断) |
|:-----------------|:---------|:------------------|
| (governance, audit) | bos://governance/omo/audit | projects/omo/src/omo/omo_audit.py |
| (governance, inspect) | bos://governance/omo/inspect | projects/omo/src/omo/omo_inspect.py |
| (governance, decide) | bos://governance/metaos/decide | projects/metaos/src/metaos/decide.py |
| (governance, gate) | bos://governance/quality/gate | projects/omo/src/omo/omo_governance.py |
| (governance, debt) | bos://governance/omo/debt | projects/omo/src/omo/omo_debt.py |
| (analysis, search) | bos://analysis/minerva/search | projects/kairon/packages/minerva/minerva_search.py |
| (analysis, research) | bos://analysis/minerva/research | projects/kairon/packages/minerva/minerva_research.py |
| (memory, search) | bos://memory/kos/search | projects/kairon/packages/kos/kos/cli.py |
| (memory, ingest) | bos://memory/kos/ingest | projects/kairon/packages/kos/kos/cli.py |
| (memory, all-search) | bos://memory/local/all-search | projects/agora/src/agora/mcp/bos_resolver.py |
| (capability, run) | bos://capability/swarm/run | projects/aetherforge/packages/swarm/src/swarm_engine/rpc.py |
| (meta, discover) | bos://meta/discover | projects/agora/src/agora/mcp/bos_resolver.py |

### 5.3 4 个扩展 explanations (A2)

```python
explanations = {
    "INTERNAL_MODULE_NOT_FOUND": "...",
    "INVALID_SCOPE": "...",
    "SCOPE_VALIDATION_SKIPPED": "omo.scopes module not found. To enable: create projects/omo/src/omo/scopes.py with ALL_SCOPES = {...}.",
    "ACTION_NAMING_CONVENTION": "Backend file naming inconsistency. Convention: governance→omo_<action>.py, analysis→minerva_<action>.py.",
}
```

---

## 6. 执行计划 (Phase 2)

### 6.1 顺序依赖

```
Step 1: 扩展 explanations 字典 (4 个 error_id)
   ↓ (无依赖)
Step 2: 扩展 file_mappings 字典 (12 个 key)
   ↓ (无依赖)
Step 3: 添加 --explain / --impact CLI flag (2 个)
   ↓ (依赖 Step 1+2)
Step 4: 验证 (4 模式 + 新 flag)
   ↓ (无依赖)
Step 5: ADR + commit + mof-version
```

### 6.2 关键决策

| 决策 | 选择 | 理由 |
|:-----|:-----|:-----|
| 增量 vs 重写 | **增量** (A3) | 风险控制 + diff 可读 + 复用 v0.1 326L |
| file_mappings 来源 | **基于真实 URIs 反推** (A1) | 避免 97% 未覆盖问题 |
| explanations 来源 | **基于 v0.1 实际规则** (A2) | 覆盖 100% 已实现规则 |
| 退出码 | 0 / 1 二元 (A4) | CI 集成简单 |

---

## 7. 验证清单

| 验证项 | 期望 |
|:-------|:-----|
| `mof-contract-lint --help` | 显示 `--explain` `--impact` 两个新 flag |
| `mof-contract-lint --explain INTERNAL_MODULE_NOT_FOUND` | Panel 渲染 + 自然语言 |
| `mof-contract-lint --explain XYZ_UNKNOWN` | 退出码 1 + "No explanation" |
| `mof-contract-lint --impact bos://governance/omo/audit` | 显示 2-3 个 direct deps + 2 文件 |
| `mof-contract-lint --impact bos://governance/UNKNOWN/x` | 退出码 1 + "no match" |
| `mof-contract-lint --impact bos://memory/local/all-search` | 显示 `agora.mcp.bos_resolver` |
| `mof-contract-lint --impact bos://governance/quality/gate` | 显示 `omo_governance.py` |
| `mof-contract-lint --json` | 默认行为不变 |
| `mof-contract-lint --quiet` | 默认行为不变 |

---

## 8. 跨阶段影响

### 8.1 Phase 0 → Phase 2 衔接

| Phase 0 交付 | Phase 2 增量 |
|:-------------|:-------------|
| v0.1 (4 模式 CLI) | v0.2 (+ --explain + --impact) |
| 326L | ~410L (+84L) |
| 3 flag (--json, --quiet, --bos-yaml) | 5 flag (+ --explain, --impact) |

### 8.2 与 god-module 治理的关系

- **完全独立**: Phase 2 不影响 omo submodule god-module 治理
- **共存**: v0.2 加入 bin/ 工具家族 (47 + 0 = 47, 因为是同一工具升级)

---

## 9. 决策建议

### 9.1 ✅ 推荐执行 Phase 2 (with 4 调整)

理由:
1. **前置条件 3/3 满足**, v0.1 已稳定
2. **工作量 ~75 分钟**, 略大于 Phase 0 但 ROI 显著 (MTTR 降低)
3. **4 项必要调整** 在提案基础上做, 不偏离 Phase 2 目标
4. **向后兼容**: 默认 CLI 行为不变, 仅新增 2 个可选 flag

### 9.2 实施前需确认

| 问题 | 决策 |
|:-----|:-----|
| 12 个 file_mappings 的"受影响文件"路径是否准确? | 基于真实 URIs 反推, 实施时验证 |
| 是否同时升级 mof-version? | ✅ 是 (v0.0.100 → v0.0.101) |
| 是否新增 ADR? | ✅ 是 (ADR-0106) |
| 跨 submodule 文件路径 (projects/aetherforge, projects/kairon) 是否仍有效? | 需验证, Phase 2 不修改 |

### 9.3 不推荐执行

- ❌ 跳过 A1 (3 key 扩展), 仅保留 3 个 hardcoded — 价值大打折扣
- ❌ 重写整个文件 (而非增量) — 风险高, diff 不可读
- ❌ 推迟 file_mappings 到 Phase 3 — 用户已等 30 天

---

## 10. 批准

✅ **本分析建议执行 Phase 2 (with 4 调整)**

**预计产出**:
- v0.2 升级 (~410L, +84L)
- 2 个新 CLI flag (--explain, --impact)
- 4 个 explanations + 12 个 file_mappings
- ADR-0106 (Phase 2 决策)
- mof-version: v0.0.100 → v0.0.101

**实施时间**: ~75 分钟
**风险**: 低 (A1-A4 mitigations 充分)

---

*版本: v1.0 | 2026-06-25 | Phase 2 预部署评估完毕*
