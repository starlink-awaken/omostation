---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y1Q2-T1-02 复盘
type: retro
---
# BET-Y1Q2-T1-02 复盘

## Q1 实际耗时 vs appetite？超出比例？
单 session ~1.5h vs appetite 1 week（大幅提前）。瓶颈在**初始依赖调用方测试的"鸡生蛋"循环**（第一次跑 mof-derive 缺失 model-driven 的测试时, 因 sys.path/exec 错误以为未降级, 实际 5 行 try/except 已就位）。

## Q2 done_when 是否全部通过？哪条没过, 为什么？
| done_when | 状态 |
|---|---|
| 产出判定 ADR | ✅ ADR-0406 (PROPOSED) |
| 判定依据 = 实证调用链 | ✅ importlib fake finder 模拟 model-driven 缺失 + 跨 3 仓 (cockpit/l4-kernel/ecos) 跑实测 |
| 若判定为降库, 排 Y1Q4 | 跳过（维持子模块, 不需 Y1Q4） |

全过。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **"M0 = 7 阶段 + 4 门禁 + 10 触发机制" 文档假设** vs **"0 触发机制被强制依赖"** 的实测 → 文档夸大横切作用域, 与 ARCHITECTURE-EVOLUTION "不持有治理状态" 自相矛盾。已修订 project-registry。
2. **"23 个 model_driven import" 看似 0 主链依赖** → 实际细看, **ecos 3 个文件 (mof-derive / mof-bridge-sync / mof/m0/mof_driven) 已经显式 `if not exists: return fallback` 或 `sys.exit(2)`**, 比我 ADR follow-up #2 提议的 try/except 早 6 个月完成。`mof-derive --stages --json` 实测缺 model-driven 时正常返回。
3. **cockpit "anti-corruption layer" `cockpit/adapters/model_driven.py`** 是 **反腐层 + 全部 # type: ignore[import-not-found]**, 而非严格 try/except. 实测 cockpit help 在 model-driven 缺失时正常输出。
4. **l4-kernel LifecycleManager 在 model-driven 缺失时**: `LifecycleManager = None` (类型哨兵), 之后 `mgr = LifecycleManager()` 报 `TypeError`, 但 **每个调用点都用 try/except 包裹**, 返回 None 而非崩溃. 防御深度足够。
5. **aetherforge 0 个 model_driven import** (预期 M0 应被横切框架调用) → M0 实际不影响 aetherforge compute/serve 路径。

## Q4 净增减（代码行 / 文件 / GaC 规则 / ADR / 脚本）
- 新文件: 1 (`.omo/_knowledge/decisions/0406-model-driven-submodule-decision.md`, ~200 行)
- 改文件: 3 (project-registry.yaml +1, INDEX.md +1, 0406.md follow-up 修订)
- 净增 ADR: +1 (PROPOSED, 待人签发)
- 净改 GaC 规则: 0
- 净增脚本: 0
- **台账**: 1 bet done (T1-02, 41 → 42)

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **T1-TRUTH 剩余**: T1-05（仓库拓扑改造 ★2 周）+ T1-01（omo-debt + c2g 并入 omo ★2 周）。T1-01 依赖 T1-02 完成 ✓.
2. **ADR-0406 待 operator 签发**: PROPOSED → ACCEPTED. 签发后把 status 改 accepted, 移除 follow-up #1（#2 已完成）.
3. **Y2Q1 复审触发器**: 新主链强制依赖 model-driven 出现 OR 0 新消费者达 6 个月 → 重新评估降为 ecos 内库.
4. **未来 model-driven 接入规范** (ADR 派生): 任何新主链强制依赖 model-driven 必须先经 governance-agent 评审, 默认驳回 (l4-kernel 现有 bridge+try/except 是唯一允许方式).
5. **mof-derive 等内部 CLI 工具** 缺 model-driven 时降级或显式失败, 已是现状 — 后续若发现新工具硬依赖, 需先加 fallback 后才能合入.
