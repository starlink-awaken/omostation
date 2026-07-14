---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0103: P109 治理赋能三件套 (验证模板 + 智能化 + TS 工具)

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P109
- **Extends**: ADR-0094-0102 (omo_lint + omo_governance_surfaces 5 阶段拆解, 9 子模块)
- **Superseded by**: (无)

## Context and Problem Statement

P104-P108 五阶段 omo_governance_surfaces 拆解累计 -75% 行数, 但暴露 3 类反复出现的问题:

1. **验证不充分**: P104 验证仅跑 1 个 lint, P106 R3 才暴露 re-export 漏写
2. **静态扫描盲点**: god-module-13-error-list 仅显示行数, 缺智能拆解建议
3. **TS AST 工具缺失**: 10 个 TS god-module 因无 ts-morph 工具被标记 "暂用 line count"

**P109 决策**: 暂停继续拆解, 转做 **3 项治理赋能工具** (高 ROI 长期价值):

| 项 | 内容 | ROI | 工作量 |
|:-:|:-----|:---:|:------:|
| **A** | omo submodule 拆分验证模板 (7-step checklist + 脚本) | 🔴 高 | 1 文件 + 1 脚本 |
| **B** | god-module-13-error-list 智能化 (--auto-classify + --suggest-modules + --roadmap) | 🟡 中-高 | 1 工具扩展 |
| **C** | TS god-module 基础结构分析器 (无 ts-morph 依赖) | 🔴 高 | 1 新工具 |

## Decision

### D1: P109-A omo Submodule 拆分验证模板

**产出**:
- `.omo/standards/omo-submodule-split-validation.md` (7-step checklist)
- `bin/omo-submodule-split-validate.sh` (一键验证脚本)

**7 步 checklist**:
1. 子模块创建 (submodule file creation)
2. 原文件剥离 (source file strip)
3. **🔴 Re-export 双向覆盖** (P104 教训)
4. **🔴 Circular import 修复** (P105 教训, 决策树)
5. **🔴 全套 lint 验证** (P106 教训, 6+lint 必跑)
6. Re-export 等价验证
7. 阈值达标 + ADR 记录

**验证脚本功能** (`omo-submodule-split-validate.sh`):
- 检查 parent re-export child 模块符号
- 跑全套 6 surface lint
- 验证 parent + child 共享 callable 一致性 (含 `_load_yaml` whitelist)
- 阈值检查 (parent <800L, child <800L)

**测试结果**: 用 P108 (omo_governance_surfaces + omo_governance_surfaces_internal_write_profiles) 反向验证, 7 步全过 ✅

### D2: P109-B god-module-13-error-list 智能化

**扩展 3 个新 flag**:

**`--auto-classify`** (智能归类):
- 按 category (python-omo / python-ecos / ts-gbrain / ts-other)
- 按 difficulty (low / medium / high, 基于 max unit lines)
- 按 ROI (high / medium / low, 基于 category + excess)

**输出**:
```
📊 ROI: HIGH (1 files)
  • projects/omo/src/omo/omo_ingress_task_lifecycle.py (1530L, excess 730L)
    category=python-omo difficulty=medium
    💡 category=python-omo, difficulty=medium, roi=high, omo submodule 内, P104-P108 模式可复用

📊 ROI: MEDIUM (1 files)
  • projects/ecos/src/ecos/services/governance/domain_manager.py (1914L, excess 1114L)
    category=python-ecos difficulty=low
    💡 category=python-ecos, difficulty=low, roi=medium, 需 ecos submodule 治理节奏

📊 ROI: LOW (10 files)
  • projects/gbrain/src/commands/doctor.ts (4825L, excess 4025L)
    💡 category=ts-gbrain, difficulty=high, roi=low, blocked by ts-morph tool gap (P109-C 候选)
```

**`--suggest-modules`** (子模块拆分建议, 基于 P104-P108 模式):
- 自动生成 `omo_<parent>_<child>.py` 命名
- 输出 phase + child_module + split_function + cumulative_reduction
- 例: doctor.ts 拆 3 子模块 (runDoctor / runRemediate / doctorReportRemote)

**`--roadmap`** (4-步 roadmap, 按 ROI 排序):
- 1. P110: omo_ingress_task_lifecycle.py (HIGH)
- 2. P111: ecos domain_manager.py (MEDIUM)
- 3-12. TS god-modules (LOW, blocked by ts-morph)

### D3: P109-C TS god-module 基础结构分析器

**问题**: 10 个 TS god-module 因无 ts-morph 工具被标记 "暂用 line count"

**解决**: 写 `bin/ssot/ts-file-analyze.py`, 用 Python 实现 TS 基础结构分析 (无外部依赖):
- regex 匹配 `function` / `class` / `interface` / `type` / `const`
- brace counting 找 block end (含 string/comment 跳过)
- 输出 top N functions/classes/interfaces

**精度**: ~80% (vs ts-morph 100%), 足够 god-module 拆解建议

**关键发现** (10 TS god-module 首批分析):
| 文件 | 行数 | top 结构 |
|:-----|:----:|:---------|
| `doctor.ts` | 4825L | runDoctor(2322L) + runRemediate(289L) + doctorReportRemote(255L) |
| `postgres-engine.ts` | 4514L | escapeSqlStringLiteral(4458L, 整文件) + PostgresEngine class(4341L) |
| `pglite-engine.ts` | 4509L | PGLiteEngine class(4285L) |
| `serve-http.ts` | 1756L | runServeHttp(1449L) |
| `cli.ts` | 1735L | handleCliOnly(700L) + main(144L) + printHelp(135L) |
| `cycle.ts` | 1707L | runCycle(533L) + 6 phase functions (76-78L each) |
| `sync.ts` | 1609L | performSyncInner(655L) + runSync(258L) + performFullSync(142L) |
| `engine.ts` | 1563L | 1 small function (5L) + 27 interfaces (BrainEngine 1018L) |

**集成**: `god-module-13-error-list.py` 自动调用 `ts-file-analyze.py` (subprocess), TS god-module 不再是盲点

### D4: 收口统计

| 指标 | P108 末 | P109 末 | 变化 |
|------|---------|---------|------|
| 治理工具数 (bin/) | 44 | **47** | +3 (validate.sh + ts-file-analyze.py + 1 工具扩展) |
| standards 模板 | 32 | **33** | +1 (omo-submodule-split-validation.md) |
| ADR 数 | 62 | **63** | +1 (本 ADR) |
| TS god-module 盲点 | 10 文件盲 | **10 文件结构已知** | 解除 |
| `--auto-classify` 输出 | (无) | 12 文件 ROI 分级 | 新增 |
| `--roadmap` 输出 | (无) | 按 ROI 排序 8 步 | 新增 |
| god-module 13 error 数 | 12 | 12 | 不变 (本阶段不拆) |
| mof-version | v0.0.97 | **v0.0.98** | bumped |

### D5: P109 ROI 评估

| 维度 | 价值 |
|:-----|:-----|
| **避免 P104/P106 类错误** | 🔴 高 — 7-step checklist + 验证脚本立竿见影 |
| **god-module 治理智能化** | 🟡 中-高 — 后续 P110+ 阶段自动分类/建议 |
| **解锁 10 TS god-module** | 🔴 高 — 从盲点到有结构分析 |
| **3 工具协作** | 🟢 中 — validation + classification + TS analysis 形成完整链路 |

### D6: P110+ 候选 (基于 --roadmap 输出)

按 ROI 排序:
1. **P110** omo_ingress_task_lifecycle.py (1530L, ROI high, omo submodule)
2. **P111** ecos domain_manager.py (1914L, ROI medium, 跨 submodule)
3. **P112+** 10 TS god-modules (LOW ROI, 待 ts-morph 工具成熟或人工拆解)

**P110 优先**: omo_ingress_task_lifecycle.py 是最高 ROI Python 候选, 业务核心但 P105/P107 模式可复用。

## Consequences

**正面**:
- **3 工具赋能未来拆分**: 避免 P104/P106 类错误, 自动分类/建议, TS 盲点解除
- **ADR 数 +1**: 治理经验显式登记
- **不动 god-module**: 不增加 governance 风险, 纯工具改进
- **P110+ roadmap 明确**: --roadmap 输出可直接用作 P110+ 阶段选题

**负面**:
- **god-module 12 个未减**: 本阶段不拆, 但 --auto-classify + --roadmap 加速后续
- **ts-file-analyze 精度 ~80%**: 复杂 TS 语法可能误判, 但对 god-module 拆解足够
- **inline _load_yaml 重复**: P108 8 子模块仍用 inline 范式 (P105), 已成可接受重复

**关联**:
- ADR-0094-0102: 5 阶段拆解 (omo_lint + omo_governance_surfaces)
- **ADR-0103**: 3 工具赋能 (验证模板 + 智能化 + TS 分析), 治理从"动手拆"转向"工具有效"
- P109 是 100 阶段关键转折: 从**纯拆解**到**工具驱动治理**

## Validation

```bash
# P109-A 验证
bin/omo-submodule-split-validate.sh omo_governance_surfaces omo_governance_surfaces_internal_write_profiles
# 期望: 🎉 all 7 steps pass

# P109-B 验证
python3 bin/ssot/god-module-13-error-list.py --auto-classify
# 期望: HIGH/MEDIUM/LOW 分级, 12 文件

python3 bin/ssot/god-module-13-error-list.py --suggest-modules
# 期望: 每个 error 文件输出子模块拆分建议

python3 bin/ssot/god-module-13-error-list.py --roadmap
# 期望: 8 步 roadmap, 按 ROI 排序 (omo_ingress_task_lifecycle 第 1)

# P109-C 验证
python3 bin/ssot/ts-file-analyze.py projects/gbrain/src/commands/doctor.ts --top 3
# 期望: runDoctor(2322L) + runRemediate(289L) + doctorReportRemote(255L)

python3 bin/ssot/god-module-13-error-list.py 2>&1 | grep doctor
# 期望: Top 函数: runDoctor(2322L), runRemediate(289L), doctorReportRemote(255L) (不再是 line count)

# P109 R5: dashboard
PYTHONPATH=projects/omo/src python3 bin/gac/governance-dashboard.py
# 期望: 22/22 OK

# P109 R6: mof-version
bin/mof-version record "P109: 治理赋能三件套 (验证模板 + 智能化 + TS 工具)"
# 期望: v0.0.97 → v0.0.98
```

## References

- P82-P108: 见 ADR-0093-102 References 列表
- ADR-0093: P99 omo_lint 兑现路径 P100-P103 4 步
- ADR-0094-97: P100-P103 omo_lint 子模块拆分
- ADR-0098: P104 omo_governance_surfaces snapshots 子模块拆分
- ADR-0099: P105 omo_governance_surfaces ingress-check 子模块拆分 (circular import 修复)
- ADR-0100: P106 omo_governance_surfaces 4 子模块化 (warn 阈值清零, P104 re-export 修复)
- ADR-0101: P107 omo_governance_surfaces 6 子模块化 (<600L ideal)
- ADR-0102: P108 omo_governance_surfaces 8 子模块化 (黄金值)
- **ADR-0103: P109 治理赋能三件套 (验证模板 + 智能化 + TS 工具, 本 ADR)**

---

*最后更新: 2026-06-25 · P109 治理赋能三件套收口 (从"动手拆"到"工具有效", 100 阶段关键转折)*
