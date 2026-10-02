---
schema: md/v1
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-10-02
type: report
bet_id: BET-Y2Q4-T10-220
title: BET-Y2Q4-T10-220 closeout — system.yaml 的运行态写入改挂 state 根，检出那份降级为快照
---

# BET-Y2Q4-T10-220 closeout — ADR-0456 B5 键摘库本体

契约：`docs/superpowers/specs/2026-10-02-bet-220-system-yaml-state-root-write-plane.md`
（v1.0.0，`status: accepted`，`lifecycle: contract`，digest
`sha256:0b95f16607d78310eeed714bb685e6be20fb23eb22c8644d54c0fef6ebd36d3e`）。
交付：主仓 PR #4606（squash → `origin/main@ece7a604897cfbd656fb9092c828e901ec5c1bff`），
子模块 PR omo#205（squash → `origin/main@1eda1fde7c9a49fb4d9c14f1c4d68f8c48cc3edf`，已 re-pin 进 gitlink）。
run：`20261002T080847Z-project-code-change-3e453453`（governance-agent）。
复盘：`.omo/_knowledge/retros/BET-Y2Q4-T10-220.md`。

## 1 判据被推翻的那一步，是本轮最有价值的产出

plan B5（决策 4）的完成判据是「一次 dev 运行后 `git status --short .omo/state` 为空」。
T10-215 已经把四件投影 + `runtime/omo/**` 镜像搬到 state 根，但实测声明 profile 后跑
`omo state sync-tasks`，检出的 `.omo/state/system.yaml` **仍被改写一行 `updated_at`** ——
判据路径当场不成立。写者普查（构造式 `git grep` 23 处命中逐条定性）给出的结论不是"缺机制"，
而是**机制有四处被绕过**：正确常量 `omo_paths.STATE_SYSTEM_YAML`（`:69`）与
`evidence-smoke._system_yaml()`（`:219`）早已存在并被四处使用，同时另有四个写点各自钉检出根。

| 写点 | 原来的根 |
|---|---|
| `bin/compass_radar.py:1400` | `ws_root = omo_dir.parent` |
| `bin/gac/harness-omo-bridge.py:30` | `__file__.parents[2]` |
| `bin/gac/self-evolution-loop.py:230` | `REPO` |
| `projects/omo/src/omo/omo_state.py:320`/`:474` | `find_omo_dir()` → `OMO_ROOT` |

**普查里最贵的一次纠正**：`omo_state.py` 那两处只是**调用方**，真正落笔的是
`omo_ingress.write_system_projection_fields`（`:124`）。只改 caller 会留下一份
"看起来改完、实际仍写检出"的差集，而 `write_surfaces` 与门禁都看不出差别 ——
所以内核侧收成一个共享解析器，改在写点而不是改在 caller。

## 2 写侧：call-time 解析缝，不是模块常量

模块常量在 import 期冻结 env，声明 profile 的进程拿不到它。四个 bin 写者各加一个
`_system_yaml()`（`harness-omo-bridge` 是既有形态的复用），每次调用重新解析：

```python
def _system_yaml() -> Path:
    return runtime_state_root() / ".omo" / "state" / "system.yaml"
```

未声明 profile 时 `state_root() == code_root()`，解析恒等，与历史布局逐字节一致
（`tests/unit/test_repo_root_profile.py` 的同一条不变量）。

**"没有半份镜像"这条不变量是读侧整文件优先的前提**：实测四个写者在 state 根副本缺失时
一律跳过或抛错（`cmd_state_set` 报错、`write_system_projection_fields` 抛
`FileNotFoundError`、`sync_state_projection._system_payload` 抛 TypeError），
所以 state 根那份永远是完整副本，读者整文件优先不会读到半份状态。
harness 侧因此写成"缺镜像就跳过"而不是"缺镜像就新建"。

## 3 读侧：`state_file_read` 故意不注册成投影

`repo_root.state_file_read(rel)` —— state 根优先、检出兜底。8 个读点一起移，使
"检出根拼 system.yaml"在 `bin/` 里成为可 grep 清零的形态，而不是"接线的那几个改了"。

两条边界，都是实测逼出来的：

- **只有显式声明 `OMOSTATION_STATE_ROOT` 才去探 state 根**。否则传给 `root=` 的 tmp 检出
  跟 `state_root()`（真实检出）是两个不同目录，无条件优先 state 根会把 fixture 的读取
  **劫持到宿主仓库那份文件上** —— 这不是简化，是隔离测试的前提，测试里有一条专门钉它。
- **不把 `system.yaml` 注册成新投影**。它是同一个文件的"快照 + 运行态镜像"两个身份，
  不是 canonical/legacy 两个名字；注册进 `runtime-projections.yaml` 会让
  `projection_name_for()` 把快照误判成 legacy 位。

## 4 R-GOV-2：同义反复删除，但阈值与分级不动

`bin/compass_radar.py:1420-1421` 把自己的 `health_score` 复制进 `health_score_evidence`
并把 `_source` 写成 `"compass_radar (synced)"`，注释自称 "R-GOV-2 convergence"；
`bin/gac/evidence-smoke.py:242` 写的是它独立测出来的 evidence 分。同一个键两个语义、后写者赢。
实测两例读数：跟踪态 `health_score=46` vs `health_score_evidence=100.0`（source=evidence-smoke），
刚跑完本地门禁的工作副本 `health_score=71` 而 R-GOV-2 报 `divergence 29.0 > 5`。

阈值 5 与 WARN-only 分级**不动**，依据是实测 `governance-convergence-lint.py` 的 `errors`
恒空（`:163` 只 append warning）—— 诚实化只会让警告变真，不会把门禁变红。
`health_score_evidence` / `_source` 的 `fields` 归属随之从两写者收成单写者。

## 5 登记面：一条判据被自己的测量否证，于是换了一种做法

初稿把「把 `compass_radar.yaml` 的 `id` 改指活入口 `bin/compass_radar.py`」当修复。实测否证：
`bin/ssot/script-registry.py validate()` 用 `registered = set(ids)` 且
`missing = actual_scripts - registered`（`actual_scripts` = `git ls-tree HEAD bin` 全部
`*.py`/`*.sh`，只跳过 `_registry`/`_` 前缀目录），基线 **PASSED 713**。于是改 `id` 会同时造成
① 两个条目同 id（set 静默去重，不报错）② `bin/meta/compass_radar.py` 从 registered 消失
⇒ `Missing registrations: 1` ⇒ 判据当场自否证。

本轮因此只做**登记侧诚实化**：description 写明"冻结分叉副本、无调用者；活入口
`bin/compass_radar.py`"，`maturity` 从枚举外假值 `draft` 改 `deprecated`（schema 枚举实测含它）。
删文件 + 删登记是另一个动作，见 spec §4。

顺带实测到一条登记面事实（本轮不修，另立）：`validate()` **不校验 schema**，
所以 57 个条目的 `maturity` 取值（`active` 46 / `shadow` 6 / `alpha` 4 / `production` 1）
全不在 `[draft, stable, deprecated, archived]` 枚举里而无任何告警 —— `maturity` 目前是装饰。

## 6 判据实测

| # | 命令/探针 | 读数 |
|---|---|---|
| C1–C3 | `OMOSTATION_STATE_ROOT=/tmp/t10220.eQsDzI` 下真实 `state sync-tasks`（rc=0）+ 四写者探针 | state 根那份拿到 `health_score=55` / `harness.last_run=probe-t10220` / `self_evolution` / 本次新 `updated_at`；检出的 23 键 blob 逐字节未变（`git status --short .omo/state` 空）。双断言成对，不用"脏检出"单一带否定式验收 |
| C4 | 读者落点探针（state 根 `health_score=90` / `health_score_evidence=10`，检出放差值<5 的另一份） | divergence 取自 state 根那份；删掉则回退读检出且不报错 |
| C5 | `git grep 'data["health_score_evidence"] = updates['` | 0 命中；`--rule R-GOV-2` 仍可跑且 `errors == []` |
| C6 | `python3 bin/gac/omo-state-write-guard.py --json` | `present == declared == 23`，`undeclared-key` / `ghost-declaration` / `unresolvable-owner` 全 0，`findings: []` |
| C7 | `python3 bin/ssot/script-registry.py validate` | `VALIDATION PASSED: 713 scripts registered`（未变） |
| C7 | `make gac-local-gate` | `GaC local gate: PASS (68 checks executed, 1 SOFT WARN)`；该 WARN 是 `data/kos/kos-index.sqlite` 运行时产物缺失的环境性跳过（exit 78），非本轮引入 |
| C8 | AST 扫 `bin/**/*.py` 中由检出根变量拼出的 system.yaml 路径 | 归一两种写法后按 8 文件 allowlist 做集合相等核对，并附反向核对（state 根写者必须在场）。初稿的裸 `git grep` 单一形态只命中 4 处，漏掉分引号写法与 `omo_dir / "state"` 形态 —— 那样一条判据会在写者没改完时就变绿 |
| C9 | `python3 -m pytest tests/unit/test_system_yaml_write_plane.py tests/unit/test_projection_reader_resolution.py tests/unit/test_repo_root_profile.py -q` | 新测试 23 passed；整组 899 passed / 2 failed（见 §7） |
| C9′ | `python3 -m pytest projects/omo/tests/test_omo_system_yaml_state_root.py -q`（子模块） | 9 passed；相邻 `test_omo_ingress/sync/governance/ingress_state` 69 passed |

`/` 链必须按**源码顺序**递归展开：上一版用栈弹序拼出 `"system.yaml/state"`，
于是那条守卫对任何代码都绿。新增一条合成违规样本自证检测器会咬
（`test_detector_itself_catches_a_known_offender`）。

## 7 本地红的归属（不假装成本轮成果）

`test_projection_reader_resolution.py::test_probe_heartbeat_monitor_reports_absent_projections_without_failure`
与 `test_repo_root_profile.py::test_projection_falls_back_to_committed_legacy_path` 失败，
实测**不是本轮引入**，来自已合并的 #4524 摘库：`git ls-tree origin/main` 里
`.omo/state/health.yaml` 已不被 track，这两条"回退到最后提交的 legacy 路径"的**前置断言失效**。
`.github/workflows/governance-check.yml:118-126` 的 pytest 文件白名单不含 `tests/unit/**`，
CI 从未看见。归属另立任务修判据前提。本轮 `bin/lib/repo_root.py` 的改动纯新增
`state_file_read` + 导出，未碰 `projection_read`。

## 8 回滚

三段式 commit，按 lane 分离，任一段可独立 revert：
`8d8b69cc2`（code：bin/** + `tests/unit/test_system_yaml_write_plane.py`）、
`ff0be32cc`（governance_state：write-owners + 台账 + spec + registry 条目）、
`843ca61ae`（submodule_pointer → omo `1eda1fde7`）。
回滚主仓 PR 后，写侧退回检出根、R-GOV-2 恢复同义反复；
`write-owners.yaml` 的 `fields` 段退回两写者不影响 guard 的 `present == declared == 23` 判据。
无数据迁移、无服务启停、plist/cron 一行未改。

## 9 未做（避免被读成已做）

tasks 面 `INDEX.md` 的 `Updated:` 仍脏（D5：`.omo/tasks/**` 是任务真源、INDEX 是其派生缓存且
按设计跟踪，挪进 state 根会让检出的 tracked 缓存永不更新，正好复活它当初要治的病）；
`projects/runtime/src/runtime/scheduler.py` 的根未改（D7：该服务未安装、已有 `OMO_STATE_FILE`
env seam、submodule 在本 worktree 是 shallow）；8 处面外读点留在 allowlist；
`OMO_GOVERNANCE_DATA` 保持检出根（`.gitignore:412` 实测）；
`OMO_ALLOW_GIT_WRITE=0` 属 B4b 批次 2，需逐批授权。
