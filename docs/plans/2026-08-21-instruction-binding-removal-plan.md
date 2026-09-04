---
lifecycle: entry
owner: auto-fix-loop
last_updated: 2026-08-24
type: ephemeral
---

# Instruction Binding 全链移除方案(独立 BET 候选)

- 状态: PROPOSED(2026-08-21)
- 定位: 架构迁移候选,非当前实施
- 背景: #1815 半删 instruction binding 跨仓不一致已通过 #1825 恢复主仓解决; 本方案评估彻底移除该机制的可行性

## 1. 背景

`instruction_binding` 是 WorkPacket v2 的一个字段,要求 worker 启动前确认接受 Blueprint Agent Instruction Pack
(`docs/operations/blueprint-agent-instruction-pack-v1.md`)。它是 omo #63 "gate workers on instruction acknowledgement"
引入的 worker 治理护栏。

2026-08-21 的 #1815 试图删除主仓生成侧但保留 ecos/omo/worker 消费侧,导致所有 BET start 失败。
#1825 恢复主仓生成侧恢复一致性。**但机制本身仍横跨 3 仓 25+ 文件,存在双权威。**

## 2. 完整引用面(3 仓 25+ 文件)

| 仓库 | 文件 | 职责 |
|---|---|---|
| **ecos(8)** | `ssot/mof/m2/work_packet.yaml` + 4 个 generated(control.schema.json/control-schemas.ts/control_models.py/control.sql)+ `ssot/tools/work_packet_compiler.py` + 2 测试 | MOF schema 强制 + 编译校验 |
| **omo(11)** | `blueprint_control.py`(7 处)/`workflow_mesh.py`(6 处)/`workflow_dispatch.py`/`omo_worker_core.py`/`omo_worker_cmd_worker.py`/`omo_worker_dispatch.py`/`worker_lifecycle.py` + 5 测试 | worker gate + packet 编译 + 生命周期 |
| **主仓(6)** | `bin/gac/codex-worker-adapter.py`/`pi-worker-adapter.py`/`orca-codex-supervisor.py`/`omp-worker-adapter.py`/`orca-worker-start.py` + `bin/plan/bet-ledger.py` + 6 测试 | worker 适配器校验 + 生成侧 |

## 3. 实施步骤(若批准)

### Step 1: ecos 先(改 schema + 重新生成)
1. `work_packet.yaml` 的 WorkPacket v2 定义删除 `instruction_binding` 属性
2. 运行 MOF 生成器重新生成 4 个文件(models/schema/sql/ts)
3. `work_packet_compiler.py` 删除 instruction_binding 强制校验(对应 #1825 恢复的对称位置)
4. 更新 `test_mof_compiler.py` + `test_work_packet_compiler.py`
5. **PR 合并 + 主仓 bump ecos 指针**

### Step 2: omo(删除 worker gate)
1. `blueprint_control.py` 删除 `_instruction_binding()` 及 7 处引用
2. `workflow_mesh.py` 删除 6 处 admission context 字段
3. `omo_worker_*`/`worker_lifecycle.py`/`workflow_dispatch.py` 删除绑定要求
4. 更新 5 个测试
5. **PR 合并 + 主仓 bump omo 指针**

### Step 3: 主仓(删除生成侧 + worker 适配器)
1. `bet-ledger.py` 删除 INSTRUCTION_PACK_* 常量 + `resolve_instruction_binding()` + `_work_packet_from_bet` 参数(对称于 #1825 恢复)
2. `bin/gac/` 5 个 worker 适配器删除 instruction_binding 校验
3. 更新 6 个测试
4. **PR 合并**

## 4. 风险与缓解

| 风险 | 缓解 |
|---|---|
| MOF schema 变更破坏生成文件 | Step 1 单独 PR,CI 完整环境重新生成验证 |
| 跨仓 gitlink 指针失效 | Step 1→2→3 顺序,每步 bump 后主仓验证 |
| **worker 治理语义变化**(移除"确认接受指令包"约束) | **需确认 spec_binding 是否承担该职责; 若不承担,保留 instruction_binding 或引入替代约束** |
| #1815 半删重演 | 全链移除必须一次性覆盖三仓,禁止分仓半删 |

## 5. 决策点(需 human gate)

**核心问题: 是否废弃 instruction_binding 机制?**

- **选项 A: 废弃**(本方案)—— 删除三仓全部引用。前提: spec_binding(fail-closed)已足够约束 worker,或引入替代护栏。
- **选项 B: 保留** —— 维持现状(#1825 已恢复一致性)。instruction_binding 继续作为 worker 指令包确认护栏。
- **选项 C: 降级** —— 保留机制但改为非强制(仅记录不拒绝)。风险: 削弱护栏。

**建议**: 当前无强需求废弃,选项 B(保留)是低风险默认。若未来 worker 治理收敛到 spec_binding 单一权威,再实施选项 A。

## 6. 关联

- #1825(恢复主仓,本方案的先决条件)
- #1823(instruction binding 回归测试锁定)
- omo #63(gate workers on instruction acknowledgement)
- T1-19(done,Codex transport cutover,与 instruction binding 无关但同一波清理)
