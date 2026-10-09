---
schema_version: specification/v1
spec_version: 1.0.0
title: ADR-0456 B5 残留 — evidence-freshness 读侧根分裂与「生成即豁免分数」
bet_id: BET-Y2Q4-T10-238
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-09
---

# 这条门禁不是「首跑必绿」，是「声明 profile 后每次跑都必绿」

## 1 判据现状（2026-10-09 实测，非引用）

写者与读者对同一个逻辑目录用了两个不同的根：

| 侧 | 代码 | 求值时机 | 根 |
|---|---|---|---|
| 写 | `bin/gac/evidence-smoke.py:111` `_output_dir()` → `state_root() / ".omo" / "_delivery" / "evidence-smoke"` | 调用时刻 | profile |
| 读 | `bin/gac/check-evidence-freshness.py:21-22` `WORKSPACE = Path(__file__).resolve().parents[2]` | import 时刻 | 检出 |

同一 worktree、同一时刻的实测读数（`OMOSTATION_STATE_ROOT=~/.local/state/omostation/dev`）：

```
no-profile   SPLIT=False  read=<checkout>/.omo/_delivery/evidence-smoke
dev-profile  SPLIT=True   read=<checkout>/.omo/_delivery/evidence-smoke
```

后果不是「偶尔不一致」，而是**结构性的**：声明 profile 后 `_latest_report()` 永远命中不到写者刚落盘的报告，
于是每次运行都走 `:93-99` 的生成支路；而那条支路只查 `error` 键，**从不把分数与 `MIN_SCORE` 比**。
读数 `score` 被赋值（`:96`）却没有任何判据消费它。BET-Y2Q4-T10-214 的 retro 已经把这条记为
「会自己写状态文件的检查，不能当 verify 锚 —— 它的第一次运行必然绿」（`#:12`），并点名了
`:93-99`；本 BET 的增量是：**分裂把「首跑」放大成了「每跑」**，且 `age_days = 0`（`:97`）是硬写的，
不是测出来的。同一族还有 T10-232 §5 记的读写分裂与 86.6/100.0 双读数。

交付面边界（不在本轮）：CI 的 `CR-X2-EVIDENCE-FRESHNESS`（`.github/workflows/gac-gate.yml:294-296`）
带 `continue-on-error: true`，是 advisory；把它翻成阻断属门禁强度政策变更，另案。本轮只让这条检查
**在本地门禁面（`bin/gac/gac-local-gate.py:296` / `:937`）说得真话**。

## 2 Ideal State Criteria（每条点名伪证形状）

- **ISC-1 读侧落点 = 写侧落点**。声明 `OMOSTATION_STATE_ROOT=<X>` 时，检查器的证据目录解析为
  `<X>/.omo/_delivery/evidence-smoke`。伪证：路径仍含检出根，或该目录下只读不到写者产物。
  这是**正向落点**断言（T10-232 §5 点名的「不能只测能读到」）：断言必须绑定到
  「判据读数来自那棵树」——把一份陈旧报告只物化在 state 根，检查器必须报出它的真实年龄。
- **ISC-2 生成支路不再豁免分数**。空证据目录 + 生成得到 `evidence_health_score < MIN_SCORE` →
  `exit 1` 且 `violations` 含 `low_score`。伪证：同一场景 `exit 0`。判据与被验对象不得共享失效模式，
  所以此条同时钉「改前该形状为绿」——旧代码在同一注入下必须 PASS（变异对照）。
- **ISC-3 分裂可见，而非被容忍**。生成成功但读路径上没有那份产物时，不得静默 PASS：
  报 `evidence_unreadable`。伪证：注入「生成 OK、落盘不可见」后 `ok=true`。
- **ISC-4 未声明 profile 时逐字节等于历史**。`env -u OMOSTATION_STATE_ROOT` 下证据目录字符串与
  `<checkout>/.omo/_delivery/evidence-smoke` 完全相同，脚本路径/cwd 仍取检出侧代码根。
  伪证：CI（无 profile）的读数或路径因本轮改变 —— ADR-0456 的这条不变量由
  `tests/unit/test_repo_root_profile.py` 钉住，本轮在其消费者侧再加一条。
- **ISC-5 检测器自证**。新增用例必须包含一条「向真实代码注入违规形状、当场点名」的对照，
  否则「绿」只说明装置没命中（AGENTS.md §7 ④）。

## 3 约束

- 只改读侧；`evidence-smoke.py` 的写侧与 `--gate` 语义不动。
- 不把 `MIN_SCORE`/`MAX_AGE` 调低来「让 CI 过」——收紧判据不是放宽判据。
- 生成支路保留（CI 干净检出没有报告，这是真实需求），移除的是它对分数的豁免。
- 根一律经 `bin/lib/repo_root.py` 取，不在本模块用 `__file__` 反推。
