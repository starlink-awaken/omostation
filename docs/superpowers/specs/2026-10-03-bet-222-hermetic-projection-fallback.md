---
schema_version: specification/v1
spec_version: 1.0.0
title: BET-Y2Q4-T10-222 — tests/unit 两根投影用例去 host/时钟依赖（物化两侧 / 时间戳相对 now）
bet_id: BET-Y2Q4-T10-222
status: accepted
lifecycle: contract
last-reviewed: 2026-10-03
owner: governance-team
---

# 两条"只有这台机器 / 只有这几天才绿"的用例

> ADR-0456 B5（生成态摘库）把 health 投影从被跟踪的 `.omo/state/health.yaml` 移到被 gitignore 的
> canonical 面 `.omo/state/runtime/health.yaml` 之后，`tests/unit/` 里留下两条按构造不可复现的用例：
> 一条依赖 **host 文件系统状态**，一条依赖 **日历**。两者都不是被测代码的回归，却都会在下一次
> `pytest tests/unit` 里以"真 bug"的样子报红。本 spec 定下"测兜底先物化""新鲜度必须相对 now"
> 两条不变量，并把分类做实，免得下一轮把范围外的红也当成同一件事。

## 1. 实测读数（基线 cbbfbcc44，2026-10-03，隔离 worktree）

| 用例 | 修复前 | 修复后 |
|---|---|---|
| `test_repo_root_profile.py::test_projection_falls_back_to_committed_legacy_path` | FAILED（该文件 `1 failed, 859 passed`） | PASSED；整文件 `861 passed` |
| `test_projection_reader_resolution.py::test_probe_heartbeat_monitor_reports_absent_projections_without_failure` | FAILED（断言 `health["ok"] is True`） | PASSED；整文件 18 项全绿 |
| 两文件合跑 | — | `879 passed` |
| `tests/unit` 全量（839s） | `16 failed, 1848 passed` | 本 BET 的 2 条已绿，其余见 §5 |

## 2. 第一类：host 依赖（物化两侧）

用例断言读者会兜底到检出的 legacy 文件 `.omo/state/health.yaml`。B5/T10-212 之后，这个文件在
`origin/main` 上**既不存在也不被跟踪** —— 只有"在这台机器上跑过写者、旧的 legacy 文件还留在检出里"
的工作区才会绿。这是 hermeticity 泄漏，且 CI 永远看不见：`.github/workflows/governance-check.yml:118-127`
是显式文件白名单，不含 `tests/unit/**`（该事实由 BET-Y2Q4-T10-221 判据 3 记录）。

第二处根因决定它**不能靠 env 修**：`projects/omo/src/omo/omo_paths.py:27` 的
`WORKSPACE_ROOT = _MODULE_DIR.parents[3]` 由 `__file__` 推导，`OMOSTATION_ROOT` 对它无效
（ADR-0456 契约：读侧跟随当前检出）。于是"伪造 legacy 侧的根"只有一种做法 —— **让 omo_paths 这个
模块物理落在假检出里**。对面 `test_projection_reader_resolution.py:42` 之所以一直是 PASS 的，正因为
它的 fixture 自己物化了 legacy 文件。同一仓里已证过的形状，照着改：

```python
def _fake_checkout(root: Path) -> Path:
    """造一个自带 omo 包的检出: 模块副本 + 投影登记表, 源字节全部复制不手抄。"""
    pkg = root / "projects" / "omo" / "src" / "omo"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    shutil.copyfile(OMO_PATHS_SRC, pkg / "omo_paths.py")
    registry = root / ".omo" / "_truth" / "registry"
    registry.mkdir(parents=True)
    shutil.copyfile(RUNTIME_PROJECTIONS_SRC, registry / "runtime-projections.yaml")
    return root
```

三个约束：

1. **源字节复制，不手抄** —— 假检出的 `omo_paths.py` 与 `runtime-projections.yaml` 都取自本仓真文件，
   否则"兜底路径"是抄来的常量，登记表改了也不会红。
2. **正向落点断言** —— 除了断言 `projection_path('health') == <假检出的 legacy>`，还要断言
   state 根侧的 canonical **不存在**、legacy **存在**。只断言"返回值是 legacy"不足以证明兜底发生
   （canonical 也有值时兜底根本没走）。这条来自 BET-Y2Q4-T10-215 的教训：每条"移走某个写目标"的
   契约都要配一条正向落点断言。
3. **负向对照** —— 抽掉 `legacy.write_text(...)` 这行，用例必须失败（台账 verify 3 实测
   `MUTATION_EXIT 1` 且 `restored=0`）。没有它，"兜底"这个断言可能什么都没测。

同一轮补了一条正向用例 `test_projection_without_legacy_reports_missing_canonical`：两面皆无时
`prefer_canonical=True` 返回缺失的 canonical 路径（给写者的落点），不静默兜到别处 —— 把
`omo_paths.projection_path` docstring 里那句"absent is not a failure"钉在两个方向上。

## 3. 第二类：日历（时间戳相对 now）

`test_probe_heartbeat_monitor_reports_absent_projections_without_failure` 的 fixture 写死
`generated_at: 2026-09-29T00:00:00Z`，而 `runtime-projections.yaml` 的矩阵给 health 配的是
`sla_hours: 72`（相对窗口）。绝对字面量 × 相对窗口 ⇒ **2026-10-02 起无条件变红**，被测代码一行没动。
同文件同形状的另两处那天恰好没断言 `ok`，属同一枚没拆的雷；正确写法就写在它下方 26 行处
（`datetime.now(UTC)`）。三处统一改为 `_fresh_ts()`：

```python
def _fresh_ts() -> str:
    """新鲜度必须相对 now 取。..."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()
```

**断言语义只收紧不放宽**：`ok is True` 保留，投影解析用例仍断言具体落点路径（不是"存在即可"）——
换的是输入时间戳的来源，不是换掉的断言。

## 4. 逐文件分类（9 个含 `generated_at` 的 tests/unit 文件）

判据不是"文件里有绝对日期"，而是**绝对值是否与 now 或 SLA 窗口比较**。据此只有 §3 那三处是雷。

| 文件 | 绝对字面量 | 相对窗口 / now | 判定 |
|---|---|---|---|
| `test_projection_reader_resolution.py` | 3 处写点 | `sla_hours: 72` + `datetime.now` | **雷，已修** |
| `gac/test_meta_doctor.py` | 0 | `now - timedelta(days=30)` | 已是相对式，正确形状 |
| `test_system_yaml_write_plane.py` | 2（`generated_at=` 实参） | 无 | 静态回读断言，不比较 now |
| `test_panorama_objective_coverage.py` | 6 | 有 `datetime.now` | 新鲜度路径**显式注入** `now=datetime(2026,9,24,3,30,…)`，hermetic |
| `test_panorama_agent_brief.py` | 2 | 无 | 静态 fixture |
| `test_live_server_value_readiness.py` | 1 | 无 | 静态 fixture |
| `ssot/test_proposal_to_adr_status.py` | 1 | 无 | 静态 fixture |
| `test_panorama_a9_race.py` | 1（`2020-01-01`） | 无 | 故意旧，用于竞态断言 |
| `test_repo_root_profile.py` | 0 | 无 | — |

机器面判据（台账 verify 5）：

```
/usr/bin/grep -rn "write_text.*generated_at:[ ]20" tests/unit --include="*.py" || echo CLEAN
```

它是**必要而非充分**条件 —— 多行 fixture 里的 `generated_at` 可以不出现在 `write_text` 同一行，
语义面由上表覆盖。第一版判据写成 `grep "generated_at:[ ]202"`，实测命中 `_fresh_ts()` docstring 里
那句事故描述（那行不含 `_fresh_ts` 字样，排除不掉），因此改为锚在 `write_text` 上：**判据自己也红过一轮**。

## 5. 范围外：全量枚举余下的 14 个可指认用例名

| 根因 | 用例 | 为什么不在本 BET 修 |
|---|---|---|
| 装置性：本 claim 用 `SKIP_SUBMODULE_INIT=1` 建工作树，`projects/agora` 未 init | `test_live_server_value_readiness.py` 3 + `test_panorama_pending_authorizations.py` 5（`No module named 'collectors'`）+ `test_phase8_unified_ecosystem.py::test_env_resolver_workspace_paths` 1（sys.path 缺 `projects/agora/src`） | 不是代码问题；判据换地方测（canonical 或 `claim --full`），AGENTS.md §6 已固化该坑 |
| 登记表与用例分歧：`.omo/cron/registry.yaml` 里 panorama job `status: proposed`，用例断言 `active` | `test_panorama_runtime_scheduler.py` 2 | origin/main 逐字节同状态 ⇒ 基线红。真实前置事实是 launchd 现实核对（与 #86 生产 UI 脱离 vite、#104 相邻面）；把断言改成迁就登记表等于放弃那条契约 |
| 顺序依赖污染：单跑 6 passed，全量跑红 | `test_reporting_reads_ledger.py` 2 | 另一枚 hermeticity 缺陷，需独立定位污染源，与本 BET 的"绝对时间戳 × 相对窗口"不同机制 |

`16 failed` 与 14 个用例名的差额是后台输出文件被截断（只留了尾部），不是漏计。

## 6. 不做

- 不动 `projects/omo/**`，不改 `omo_paths.WORKSPACE_ROOT` 的 `__file__` 推导 —— 改成 env 可控会让
  `test_kernel_read_plane_stays_on_checkout` 失效，并把 host 依赖换成另一种 host 依赖。
- 不摘 `.gitignore:294` 的 `!.omo/state/system.yaml`、不 untrack `system.yaml`（属 task #98，
  实测仍有 ≥9 个 checkout-rooted 消费者）。
- 不新增检测脚本（会进 `bin/ssot/script-registry.py` 的 missing 面），不往 `.github/workflows/**`
  加 `tests/unit` 路径。
- 不修 §5 三类范围外红。

## 7. 判据映射

台账 `docs/plans/3y-bet-ledger.yaml` 条目 `BET-Y2Q4-T10-222` 的 verify 1–7：单文件全绿 / 单跑该用例绿 /
抽掉物化必须失败且源文件零脏 / 邻居文件读数不变 / `generated_at` 写点清零 / 出界文件为空 /
doc-governance 通过。`done_when` 5 条与本文 §2–§4 一一对应。
