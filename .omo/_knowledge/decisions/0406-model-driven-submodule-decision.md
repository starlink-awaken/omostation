---
id: ADR-0406
status: active
lifecycle: spec
owner: '@Builder'
last-reviewed: '2026-08-09'
type: ssot
---

# ADR-0406: model-driven (M0) 维持子模块形态

## Status

PROPOSED (T1-02 产出, 待 operator 签发).

## Context

T1-02 目标: 判定 M0 (projects/model-driven 子模块) 是否在 Mesh 主链上有必经位置, 终结"横切但不在链上"的模糊状态。判定依据为**实测调用链**, 非设计意图。

`docs/ARCHITECTURE-DETAILED-MAP.md` 将 model-driven 分类为 **M0 (横切生命周期引擎)**, 但 `docs/ARCHITECTURE-EVOLUTION.md` 同时指出 "**X / M0 可被多层级调用, 但不持有治理状态**" — 文档自身矛盾。本次判定为该矛盾给出实证。

候选判定 (done_when):
- 接入主链 (升 L0)
- 降为 ecos 内库
- 归档 (废弃)

## Empirical Call-Chain Analysis

### 消费者清单 (3 处直接导入, 0 处生态内)

| 消费者 | 文件 | 导入符号数 | 调用模式 | 降级机制 |
|---|---|---|---|---|
| **l4-kernel** | `src/l4_kernel/lifecycle.py` + `signals.py` | 6 (LifecycleManager, PipelinePhase/Tracker, LifecycleStage, DerivationEngine, TransitionEngine, OMOBridge) | bridge + `try/except ImportError` 降级为 `None` | **有**, 全 try/except 包裹 |
| **cockpit** | `src/cockpit/adapters/model_driven.py` (anti-corruption layer) | 9 (全部 9 个符号) | 反腐层重导出, 用于 `cockpit workspace model-driven` 子命令 | **有**, 全部 `# type: ignore[import-not-found]` + cockpit import 也 try/except |
| **ecos** | `src/ecos/ssot/tools/mof-derive.py` + `mof-bridge-sync.py` + `mof/m0/mof_driven.py` | 8 (STANDARD_STAGES, STANDARD_GATES, PipelinePhase, LifecycleStage, TransitionEngine 等) | 内部 CLI 工具, 函数内 import, **无 try/except** | **无**, 缺则直接 ImportError |
| aetherforge / omo / runtime / metaos / kairon | — | 0 | 无 import | — |

### 主链测试 — model-driven 缺失时

**关键实测** (本地 fake finder 模拟 `model_driven` 模块不存在):

1. **`cockpit help`** (主用户路径): ✅ 正常工作, 不需要 model-driven  
2. **`cockpit governance`**: 命令不存在 (governance 已废弃, 与本 ADR 无关)  
3. **`cockpit workspace model-driven` / `lifecycle` / `okr` / `spec`**: ❌ 报错 (用户次级命令)  
4. **`l4-kernel.lifecycle.LifecycleManager().create_domain(...)`**: ✅ 正常工作, 缺 `lifecycle_tracking` 字段 (graceful degradation)  
5. **`ecos/ssot/tools/mof-derive.py`**: ❌ `ImportError: model_driven` (内部 CLI 工具)  
6. **`cockpit/_subcommands.py::model_driven` 测试路由**: ❌ 失败 (单元测试, 非主链)  

### 5 阶段架构视角

| 阶段 | model-driven 角色 | 必经? |
|---|---|---|
| (L1) 协议定义 | M3 元元模型 (`STANDARD_STAGES`/`STANDARD_GATES`/`PipelinePhase` 7+4+3 = 14 个常量) | 否 (ecos 内部 SSOT, 可独立存常量) |
| (L2) 注册 + 治理 | 元数据 (LifecycleStage enum) | 否 (可本地定义 enum) |
| (L3) 入口 (cockpit) | CLI 子命令委派 + L0 MCP tools 暴露 | **否 (不阻断主入口 help/memory/demo)** |
| (L4) 运行时 (l4-kernel) | 可选 lifecycle 仪表板增强 + derivation | **否 (所有调用点 try/except 降级)** |
| (L5) 生态 (ecos) | 内部 CLI (mof-derive, mof-bridge-sync) | **否 (内部工具, 不在用户主路径)** |

### "M0 主链" 假设的对照

**架构文档声称 M0 = 横切 (7 阶段 + 4 门禁 + 3 PipelinePhase + 10 触发机制, 零依赖叶子)**.

**实测**: 0 触发机制, 0 主链强制依赖. 实际仅 9 个数据类 (LifecycleManager 等) + 14 个常量被外部读取. "零依赖叶子" 反过来: 它是**叶子 (数据常量 + 类)**, 不是"被强制依赖的根"。

ecos 用它的 M3 桥接: 14 个常量. ecos 完全可独立 copy 这 14 个常量进 `projects/ecos/src/ecos/ssot/constants/m3_lifecycle.py` (28 行). 这是个**只读数据常量**, 不是"引擎"。

cockpit 用它的 9 个类 + CLI 委派. cockpit 完全可独立 fork 这 9 个类 (或直接跨仓 shim). 但实际 cockpit 的 `cockpit workspace model-driven` 子命令是被 bundle 进去的, 删 model-driven 等于砍 1 个二级 CLI.

l4-kernel 用它的 6 个类. 全部 try/except 降级 — 缺时 l4-kernel 主功能完整, 只少增强仪表板.

## Decision

**维持子模块形态 (M0 + 子模块)**, 不归并不归档. 但需要 3 项修正:

1. **将 model-driven 标记从"M0 主链"降为"M0 横切工具"** (修订 `docs/ARCHITECTURE-DETAILED-MAP.md`), 与 `docs/ARCHITECTURE-EVOLUTION.md` 的 "不持有治理状态" 一致.
2. **ecos 内的 8 处 import 加 try/except 降级** (与 l4-kernel 对齐). 内部 CLI 工具缺 model-driven 时, 输出 "model-driven 未安装, 跳过" 而非 traceback. (低成本, 1-2 小时).
3. **记录 mof-derive 等工具的硬依赖** (从 README 明示 "需要 model-driven 子模块, 否则 NoOp"), 避免后续维护者误以为 "可降库".

理由:
- **3 个真实消费者 + 0 个主链强制依赖**: 不满足 "主链必经" 判定, 也不满足 "降为内库" 的"无人依赖"判定
- **横切工具 (常量 + 类库) 形态**: 14 个常量被 ecos 用作 SSOT, 9 个类被 cockpit 用作 CLI 入口. 复制成本 (28+200 行) 与维护成本 (单一源 vs 三处 fork) 取舍后, 维持单一源 + 子模块是最低熵选择
- **生态总信号**: cockpit 已建立反腐层 `cockpit/adapters/model_driven.py`, l4-kernel 已建立 bridge+try/except, ecos 也有 SSOT 桥接. 横切隔离工作已完成, 子模块是合适的依赖边界

## Consequences

**正面**:
- 生态 mesh 主链 (cockpit/l4-kernel/ecos/aetherforge) 无需修改即可继续工作
- 现有 3 个消费者保留, 不需要迁移
- 14 个 M3 常量保持单一源 (SSOT 价值)

**负面**:
- 子模块指针仍需 PASW + drift 门禁 (历史经验: bus-foundation/aetherforge 等已被 T6-01 清空, 易重演)
- ecos 内部 CLI 缺 model-driven 时硬崩 (需按 Decision 2 修)
- "M0" 文档语义与实际不符, 后续维护者可能误判

**约束**:
- 此判定结论: **2 季度复审 (Y2Q1)**. 若届时 model-driven 仍只有 0-1 个新消费者或 0 个新主链功能, 降为 ecos 内库或归档
- **禁止**: 不得在主链强制依赖 model-driven (无 try/except 的强制 import). l4-kernel 现有模式 (bridge+降级) 是唯一允许的接入方式

## Alternatives Considered

### A. 降为 ecos 内库
- 复制 14 个常量 + 9 个类到 `projects/ecos/src/ecos/_lifecycle/`. 成本 200-400 行, 收益 1 个子模块指针消失.
- 反对: cockpit/l4-kernel 仍需要 model-driven 类, 降库后 cockpit 反而要 `from ecos._lifecycle` 反向依赖 ecos 内部路径, 拓扑更乱.

### B. 归档 (废弃)
- 删 3 个消费者路径, 删 model-driven 整个子模块.
- 反对: cockpit `model-driven` 子命令 + l4-kernel 增强仪表板被外部用户使用 (l4-bridge 测试 + cockpit capability map 登记), 删了是回退, 不是优化.

### C. 升 L0 (主链强依赖)
- 删 try/except, model-driven 缺则拒绝启动.
- 反对: 模型驱动的 14 个常量不需要"引擎"运行时 — 升 L0 引入不必要紧耦合, 且违反"X / M0 不持有治理状态"原则.

## Verification

```bash
# 1. 确认生态无新直接 import (与判定一致)
rg "from model_driven|import model_driven" projects/ --include="*.py" 2>/dev/null | grep -v "projects/model-driven/" | wc -l
# 期望: ≤ 23 (现状: cockpit 9 + l4-kernel 6 + ecos 8)

# 2. 主链 cockpit 帮助不依赖 model-driven
cd projects/cockpit
uv run python -c "
import sys
class F:
    def find_spec(self, n, p, t=None):
        if n.startswith('model_driven'): raise ImportError
        return None
sys.meta_path.insert(0, F())
from cockpit.cli import main
import sys; sys.argv = ['cockpit','help']
main()
"
# 期望: 正常输出, exit 0

# 3. l4-kernel lifecycle 在 model-driven 缺失时仍可创建 domain
uv run --directory projects/l4-kernel python -c "
import sys
class F:
    def find_spec(self, n, p, t=None):
        if n.startswith('model_driven'): raise ImportError
        return None
sys.meta_path.insert(0, F())
from l4_kernel.lifecycle import LifecycleManager
r = LifecycleManager().create_domain('test', name='t', domain_type='document', path='/tmp')
print(r.get('status'), 'lifecycle_tracking' in r)
"
# 期望: ok False  (degraded, 无 lifecycle_tracking 字段)
```

## Follow-ups

- [x] **COMPLETED (T1-02 follow-up #2)**: ecos 内部 CLI 工具已带降级或显式失败:
  - `mof-derive.py`: `if not MODEL_DRIVEN_M3.exists(): return fallback` + `try/except` (7 stages + 4 gates + 3 phases 硬编码备份)
  - `mof-bridge-sync.py`: 显式 `if not exists: sys.exit(2)` (B.3 工具, 缺 model-driven 应失败而非跑出错误推导)
  - `mof/m0/mof_driven.py`: 显式 `if cand.exists(): import` else 早退
  - 实证: `mof-derive --stages --json` 在 model-driven 缺失时仍正常返回 fallback
- [ ] 1h: `docs/ARCHITECTURE-DETAILED-MAP.md` M0 行重命名为 "M0 横切工具 (非主链)"
- [ ] 1h: `projects/model-driven/README.md` 加 "Consumers" 章节 (l4-kernel/cockpit/ecos 列表)
- [ ] 30m: 2 季度后 (Y2Q1, 2026-10) 复审. 触发器: 新主链强制依赖出现 OR 0 新消费者达 6 个月
