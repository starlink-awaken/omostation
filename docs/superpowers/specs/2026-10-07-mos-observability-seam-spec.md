---
schema_version: specification/v1
spec_version: 1.0.0
title: ADR-0464 盲区一观测缝 — MOS 默认配置真实执行观测 + surface gate 去 phase10 活性代理
bet_id: BET-Y2Q4-T10-234
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-07
---

# ADR-0464 盲区一观测缝 (inert-by-default observability seam)

本 spec 承载一项跨双仓改动：在 `projects/knowledge/kairon/packages/mos/`（kairon
子模块）建立 **真实执行观测缝**，并把父仓门禁 `bin/gac/check-memory-os-surfaces.py`
里那条**用声明当活性的代理判据**换成对观测缝的检查。

## 0. 背景 — 为什么先建缝再加门禁

`docs/../.omo/_knowledge/decisions/0464-declaration-vs-execution-three-governance-blindspots.md`
盲区一：一个能力可以 **登记齐全、锚点可解析、相位全绿**，却在**默认配置下从不真正执行**。
经验实例即 Memory OS 控制面：`status: phase10`（phase0-10 全 done）、六条
`bos://memory/mos/*` 意图路由齐全、ADR-0372 ACCEPTED —— 但其生产后端默认关闭
（`MOS_LIVE_KOS` / `MOS_LIVE_GBRAIN` 默认 off，`NEO4J_URI` 门控且默认无服务），
默认 recall 返回的是 fixture/stub 数据（修复前 `data_mode` 字段不存在）。

两次独立审计结论一致：**没有任何门禁观测默认环境下的真实执行**；而**先建门禁、
后建观测面**只会得到一个"绿染的结构检查"。所以顺序是：**先建观测缝，再改门禁**。

## 1. 现状判据（实读，2026-10-07，worktree `ws-mos-seam`）

- `bin/gac/check-memory-os-surfaces.py:117`（改前）把字面量 `"phase10"` 列入
  `check_registry_ssot()` 的必要 needle。只要 registry 文本里出现该子串即通过 ——
  实测连 `phase10_retro: docs/operations/memory-os-phase10-retro.md`（**一个文档路径**）
  都能满足它。这是"声明即活性"的代理判据，正是盲区一被放过的成因。
- `check_env_example()`（`:70-78`）只校验 `docs/operations/memory-os.env.example`
  里键**存在**，与运行期真实执行无关。
- `mos/src/mos/service.py` 已（前一轮 T3-04）计算 `data_mode`/`live_backends`/
  `fixture_backends`，但**算完即弃**，没有任何持久化观测。

## 2. 观测缝设计（kairon 子模块）

新增 `packages/mos/src/mos/observations.py`：

- **存储形态**：**追加式 JSONL**，`<state-root>/runtime/mos/observations.jsonl`，
  每行一条 `kind: mos.real_execution` 记录（含 `ts`、`data_mode`、`live_backends`、
  `default_env`、`source`）。选追加式 + 时间戳水印，而非可变 status blob：
  水印（最新记录 `ts`）即"最近一次真实执行"的判据，历史不可被覆盖。
- **写根在调用时刻解析**（ADR-0456 / AGENTS.md §7）：优先级
  `MOS_OBSERVATIONS_PATH`（显式覆盖，供测试/运维）→ `OMOSTATION_STATE_ROOT`
  → `ECOS_WORKSPACE` / `WORKSPACE_ROOT` → 逐级上溯 `docs/project-registry.yaml`
  标记。**任何一处都不在 import 时求值**。kairon 是子模块、无法 import 父仓
  `bin/lib/repo_root.py`，故按同一 env 契约镜像；父仓门禁侧用
  `repo_root.state_root()` 读同一文件。
- **只记真实执行**：`data_mode in {live, mixed}` 且有 live backend 才 append；
  fixture-only **什么都不写**（不写 `last_real_execution: null`）—— 因为 fixture 是
  默认态，逐次 recall 都写会产生无界写入；**缺席本身就是"尚未观测到真实执行"的
  诚实信号**。
- **限流/水印策略**：`MOS_SEAM_MIN_INTERVAL`（默认 300s）内最多一条，按上一条
  记录的 `ts` 判定 —— 即使 recall 被高频调用，写入也有界。
- **fail soft**：缝内任何异常都被吞掉、返回 False；`recall()` 行为不受影响。
- **遥测而非策略**：记录真实执行**不改变** `recall()` 的任何返回值/分支。

`MemoryOS.recall()` 在算完 `data_mode` 后调用 `_observe_execution(...)`
（`service.py`，fail-soft）。覆盖 CLI（`python -m mos recall`）、cockpit 子进程、
Agora stdio、`unified.py` 等所有 recall 面。

## 3. 门禁改动（父仓）

`bin/gac/check-memory-os-surfaces.py`：

- **删除** `check_registry_ssot()` 里的字面量 `"phase10"` needle —— 去掉
  "声明即活性"的代理。**保留**其余 needle（`id: memory-os` / `surface_check:` /
  `bos://memory/mos/`）与全部 path / port / env-key / help-catalog 检查。
- **新增** `check_default_execution_seam()`：用 `repo_root.state_root()`（**调用时刻**）
  读观测缝文件，判定是否**存在一条默认环境（`default_env: true`）下的真实执行**。
- **发布为 WARN（advisory），不是 ERROR**：缝是新的，生产上可能还没记录，
  hard error 会在每个干净检出/CI 上假红。**升级路径**（写在函数 docstring，暂不启用）：
  一旦生产观测到基线记录并作为本 BET 的证据入库，把"无真实执行"分支改为 hard error，
  并加**新鲜度窗口**（最近一条默认环境记录超过 N 天 => FAIL）。

## 4. 双仓交付边界

- **kairon 子模块**：`packages/mos/src/mos/observations.py`（新）、
  `packages/mos/src/mos/service.py`（hook）、`packages/mos/tests/conftest.py`（新）、
  `packages/mos/tests/test_observations.py`（新）。子模块内提交 + 单独 bump 父仓 gitlink。
- **父仓**：`bin/gac/check-memory-os-surfaces.py`、`.omo/_truth/registry/memory-os.yaml`、
  本 spec、`docs/plans/3y-bet-ledger.yaml`、retro。

## 5. 验收标准（可执行）

- **I1（不假成功）**：fixture-only recall 不产生任何观测记录；显式 live backend
  的 recall 追加一条 `kind: mos.real_execution` 记录。由 `test_observations.py`
  的 fixture-silent / real-observed 两条用例钉住。
- **I2（调用时刻解析）**：模块 import **之后**才声明 `OMOSTATION_STATE_ROOT`，
  仍解析到 `<state-root>/runtime/mos/observations.jsonl`（冻结常量按构造做不到）。
- **I3（有界写入）**：`MOS_SEAM_MIN_INTERVAL` 窗口内重复真实执行只写一条。
- **I4（fail soft）**：写路径不可建、无根可解析时，`recall()` 照常返回、
  缝返回 False、不抛异常。
- **I5（门禁去代理）**：registry 文本删除全部 `phase10` 后，门禁不再 hard-fail
  （旧规则会失败）；path/env/port 检查保持。
- **I6（门禁不假红）**：无观测文件时门禁 exit 0 + 一条 WARN；存在默认环境真实执行
  记录时 WARN 清空；只存在 fixture 记录或只在显式 live 覆盖下的记录时 WARN 保留。
- **I7（回归）**：kairon MOS 套件在干净 env 下 ≥ 93 passed（本轮实测 101 passed，
  含新增 8 条）；`ruff check` 干净；`make gac-local-gate` 无新增 hard failure。

## 6. 非目标

- 不改任何 `MOS_LIVE_*` / `NEO4J_URI` 默认值（保持 fixture-safe）。
- 不把本门禁改为 blocking（升级为 ERROR 属后续独立 BET）。
- 不引入第三方依赖；不引入 import 时求值的 profile 根常量。
- 不改 `bin/gac/check-memory-os-surfaces.py` 的 path / port / env-key / help-catalog 检查。
- 不动 `.omo/tasks/active/BET-Y2Q4-T10-CJK-ROUTING.yaml`，不给 CI 重加 `--require-main`。
