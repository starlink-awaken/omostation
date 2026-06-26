# BOS Contract Linter Phase 0 — 预部署分析与评估

> 日期: 2026-06-25
> 作者: omostation P110+
> 关联: 提案 paste_1.txt (BOS Contract Linter 全面落地作战包 v1.0, 30 天 / 4 阶段)
> 状态: ✅ Phase 0 可执行, 标注风险与建议

---

## 1. Phase 0 范围回顾

| 交付物 | 文件 | 工作量 | 风险 |
|:-------|:-----|:------:|:----:|
| **1. mof-contract-lint.py** | `projects/ecos/src/ecos/ssot/tools/mof-contract-lint.py` (新) | ~200L | 中 (T0-1 规则集, 多模块依赖) |
| **2. pyproject.toml 补丁** | `projects/ecos/pyproject.toml` (注册子命令) | ~5L 改动 | 低 (与现有 mof-* CLI 一致) |
| **3. pre-commit hook 补丁** | `~/.hermes/scripts/git-hooks/pre-commit` (本地门禁) | ~10L 改动 | 低 (Bash 增量) |

**Phase 0 价值**: 把 `bos-services.yaml` 变更从"无门禁"变为"提交时自动校验"

---

## 2. 前置条件检查结果 (8 项)

### 2.1 ✅ 满足的前置条件 (6/8)

| # | 条件 | 状态 | 证据 |
|:-:|:-----|:----:|:-----|
| 1 | mof 工具目录存在 | ✅ | `projects/ecos/src/ecos/ssot/tools/` 有 20+ 个 mof-*.py |
| 2 | pyproject.toml 存在 | ✅ | `projects/ecos/pyproject.toml` |
| 3 | bos-services.yaml 存在 | ✅ | `projects/agora/etc/bos-services.yaml` (832L, 100 services) |
| 4 | pre-commit hook 存在 | ✅ | `~/.hermes/scripts/git-hooks/pre-commit` |
| 5 | internal transport 字段完整 | ✅ | 19/19 internal services 都有 module_path + func_name |
| 6 | mof CLI 子命令模式已建立 | ✅ | 现有 mof-enforce, mof-analyze, mof-drift 等子命令 |

### 2.2 ⚠️ 需要注意的问题 (3 项)

| # | 问题 | 影响 | 解决 |
|:-:|:-----|:-----|:-----|
| 1 | `omo.scopes.ALL_SCOPES` 不存在 | 中 — required_scopes 校验会全部跳过 | **降级为 WARN** (提案已设计 fallback) |
| 2 | pyproject.toml `[project.scripts]` 块为空 | 低 — 提案 patch 实际是**新增**整个块 | 需检查现有子命令是否在别处定义 |
| 3 | `importlib_metadata` 依赖 (Python <3.12) | 极低 — 现有 Python 3.13, 不需要 | **省略**该依赖 |

### 2.3 ⚠️ 提案 patch 与现状不符 (1 项, 重要)

**提案 patch 假设**:
```toml
mof-enforce = ["ecos[dev]"]
mof-analyze = ["ecos[dev]"]
mof-export = ["ecos[dev]"]
mof-drift = ["ecos[dev]"]
```

**实际状态**: 该 `[project.optional-dependencies]` 块 **不存在** (需确认)

**修正方案**: Phase 0 实施时先 audit pyproject.toml, 找到正确插入位置

---

## 3. 详细风险评估

### 3.1 高风险点 (3 个)

| 风险 | 触发条件 | 缓解措施 |
|:-----|:---------|:---------|
| **R1: omo.scopes 模块导入失败** | `from omo.scopes import ALL_SCOPES` 触发 ImportError | ✅ 提案已设计 fallback (SCOPE_VALIDATION_SKIPPED warning) |
| **R2: importlib.import_module 在 internal services 加载时崩溃** | aetherforge / agora / omo 任一未在 sys.path | 提案已 try/except ImportError 包裹 |
| **R3: bos-services.yaml 在 agora submodule working tree 未初始化** | git submodule update --recursive 未跑 | ✅ `path.exists()` 检查已存在 |

### 3.2 中风险点 (2 个)

| 风险 | 触发条件 | 缓解措施 |
|:-----|:---------|:---------|
| **R4: pre-commit hook 在 ecosystem 多 repo 不一致** | kairon / cockpit 等 submodule 各自有 pre-commit | 仅对 workspace 根生效, 不修改各 submodule |
| **R5: mof CLI 子命令冲突** | 未来 mof-contract-lint 与现有 mof-bos 命令重叠 | 命名清晰 (contract-lint vs bos), 无冲突 |

### 3.3 低风险点 (1 个)

| 风险 | 触发条件 | 缓解措施 |
|:-----|:---------|:---------|
| **R6: pyproject.toml 改动影响 ecos 安装** | version bump 0.1.0→0.1.1 触发依赖刷新 | 仅 patch, 不主动 install |

---

## 4. 投资回报 (ROI) 评估

### 4.1 量化收益

| 维度 | 现状 | Phase 0 后 |
|:-----|:-----|:----------|
| bos-services.yaml 变更审计 | ❌ 无 | ✅ pre-commit 拦截 |
| internal transport 错误发现时机 | 运行时 (subprocess 失败) | 提交时 (lint error) |
| 100 services 完整性扫描耗时 | N/A (无工具) | < 2s (一次 mof contract-lint) |
| required_scopes 漂移检测 | ❌ 0 services 有此字段 (新增字段将强制规范) | ✅ 自动检查 |

### 4.2 工作量评估

| 交付物 | 估时 | 实际估时 (有现成工具参考) |
|:-------|:----:|:----:|
| mof-contract-lint.py (复制提案 + 适配) | 30 min | **15 min** (提案代码完整, 仅需适配现状) |
| pyproject.toml patch | 10 min | 10 min (需 audit 现有结构) |
| pre-commit hook patch | 10 min | 5 min (Bash 增量) |
| 单元验证 | 15 min | 15 min |
| ADR + commit | 10 min | 10 min |
| **合计** | **75 min** | **~55 min** |

### 4.3 ROI 评分

| 维度 | 评分 | 备注 |
|:-----|:----:|:-----|
| 实施风险 | 🟢 低 (3/3 高风险已 mitigation) |
| 实施工作量 | 🟢 小 (~55 min) |
| 长期价值 | 🟡 中-高 (依赖 Phase 1-3 落地) |
| 与现有工作流整合 | 🟢 易 (mof CLI 模式已成熟) |
| **总评** | **🟢 值得执行** |

---

## 5. 设计调整 (vs 提案)

### 5.1 必须调整 (3 项)

| 编号 | 调整 | 原因 |
|:-----|:-----|:-----|
| **A1** | 删 `importlib_metadata>=6.0` 依赖 | Python 3.13 (当前目标), 不需要 backport |
| **A2** | 调整 pyproject.toml patch, 仅添加缺失字段 | 避免覆盖现有配置 (需先 audit) |
| **A3** | 适配 bos-services.yaml 字段 (19 services 无 command) | proposal 假设 100% 有 command, 实际只有 81% |

### 5.2 可选改进 (3 项, 非阻塞)

| 编号 | 改进 | ROI |
|:-----|:-----|:---|
| O1 | 输出 JSON schema 给 `--json` 选项, 便于 CI 解析 | 中 |
| O2 | 添加 `--strict` flag, 把 warning 也算 error | 低 |
| O3 | 添加 `--quiet` flag, 仅输出 summary | 低 |

**Phase 0 建议**: 仅实施 A1-A3 必要调整, O1-O3 推迟到 Phase 1

---

## 6. 执行计划 (Phase 0)

### 6.1 顺序依赖

```
Step 1: 创建 mof-contract-lint.py
   ↓ (无依赖)
Step 2: 更新 pyproject.toml (注册 mof-contract-lint 子命令)
   ↓ (依赖 Step 1: 必须先有 main() 才能注册)
Step 3: 更新 pre-commit hook (门禁接入)
   ↓ (依赖 Step 2: 必须能 uv run mof contract-lint)
Step 4: 验证 (单元 + 集成)
```

### 6.2 关键决策

| 决策 | 选择 | 理由 |
|:-----|:-----|:-----|
| 实施位置 | 提案 `projects/ecos/src/ecos/ssot/tools/` | 与现有 mof-* 工具一致 |
| Python 版本 | Python 3.13+ (当前 workspace) | 提案 importlib_metadata backport 不需要 |
| 校验范围 | 全部 100 services | 提案 patch 假设完整扫描 |
| 失败模式 | exit 1 (有 error) / exit 0 (warning only) | 提案实现已设计 |

### 6.3 验证清单

| 验证项 | 期望 |
|:-------|:-----|
| `uv run mof contract-lint --help` | 输出 usage |
| `uv run mof contract-lint` (无 --json) | 表格输出 |
| `uv run mof contract-lint --json` | JSON 输出 |
| 故意写错 `bos-services.yaml` (移除 module_path) | exit 1 + error |
| pre-commit 触发 (git commit 修改 bos-services.yaml) | 自动跑 mof contract-lint |
| pre-commit 跳过 (无 bos-services.yaml 改动) | 不跑 mof contract-lint |

---

## 7. 跨阶段影响

### 7.1 Phase 0 → Phase 1 衔接

| Phase 0 交付 | Phase 1 增量 |
|:-------------|:-------------|
| mof-contract-lint.py 工具 | agora CI workflow 接入 (jobs.bos-contract-lint) |
| pyproject.toml 注册 | system backend health 集成 (api.py contract_health) |
| pre-commit 本地门禁 | l4-kernel 监督脚本 (contract_monitor.py) |

### 7.2 与 omostation 当前治理的关系

- **omostation god-module 治理 (P100-P110)**: 平行工作流, 无依赖
- **BOS Contract Linter**: agora/ecos/l4-kernel 跨 submodule 工作流
- **共存性**: Phase 0 完成后, 治理面增加 1 个新工具 (44+1=45 个 bin 工具)

---

## 8. 决策建议

### 8.1 ✅ 推荐执行 Phase 0

理由:
1. **前置条件 6/8 满足**, 剩余 2 项 (omo.scopes / importlib_metadata) 提案已设计 fallback
2. **工作量小 (~55 min)**, 实施风险低
3. **ROI 高** (长期价值), 是 Phase 1-3 的基础
4. **提案代码完整**, 主要是适配 (而非从零开发)

### 8.2 实施前需确认

| 问题 | 决策 |
|:-----|:-----|
| pyproject.toml `[project.scripts]` 块目前是空, 是否需要新建? | 需先 audit (Step 0) |
| 是否一并添加 Phase 1 的 CI workflow 接入? | **Phase 0 范围限定**, Phase 1 再做 |
| 是否一并添加 l4-kernel 监督脚本? | **Phase 0 范围限定**, Phase 1 再做 |
| omo.scopes 模块是否需要同步创建? | **不需要**, 提案 fallback 足够 |

### 8.3 不推荐执行

- ❌ 跳过 Phase 0 直接做 Phase 1-3 (基础工具缺失, 后续无意义)
- ❌ 同时启动 Phase 0 + Phase 1 (顺序依赖, 串行执行)
- ❌ 修改 aetherforge / agora / omo 任一 submodule (超出 Phase 0 范围)

---

## 9. 批准

✅ **本分析建议执行 Phase 0**

**预计产出**:
- 1 个新工具 (`mof-contract-lint.py`)
- 1 个 pyproject 改动 (注册子命令)
- 1 个 pre-commit 改动 (本地门禁)
- 1 个 ADR (ADR-0105)
- mof-version: v0.0.99 → v0.1.0 (Phase 0 完整闭环)

**实施时间**: ~55 分钟
**风险**: 低 (提案完整 + fallback 充分)

---

*版本: v1.0 | 2026-06-25 | Phase 0 预部署评估完毕*
