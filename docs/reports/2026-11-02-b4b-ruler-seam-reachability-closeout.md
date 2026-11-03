---
type: report
title: BET-Y2Q4-T10-281 收口收据 —— B4b 验收尺的 repo_root 缝可达性修复
bet_id: BET-Y2Q4-T10-281
owner: governance-agent
status: completed
lifecycle: journal
last-reviewed: 2026-11-02
---

# BET-Y2Q4-T10-281 收口收据

## 交付

| 项 | 值 |
|---|---|
| PR | #5017（squash 合并为 `58dc596e774d3d132a1809a2f2202290d8c30b34`，`2026-11-02T09:04:26Z`） |
| 分支 | `agent/governance-agent/t281-ruler-seam`（base `6a5faf7e3`） |
| run | `20261102T085157Z-project-code-change-11f1b30d` |
| 规范 | `docs/superpowers/specs/2026-11-02-b4b-ruler-seam-reachability.md`，`spec_version: 1.0.0`，digest `sha256:36c1b617f060c60e9e56fe86c492d5b0b39ef891c3763b088b55bdd7862aaac1` |
| 改动文件 | `scripts/tools/launchd-workspace-reality-check.py`、`tests/unit/test_b4b_ruler_seam_reachability.py`（新）、上述 spec、`docs/plans/3y-bet-ledger.yaml`（立案） |

## 修的是什么

`launchd-workspace-reality-check.py` 是 BET-Y2Q4-T10-272 为 ADR-0456 B4b 造的 E7 写根轴量具，
它的 `repo_root` 缝算成 `Path(__file__).resolve().parents[1] / "lib"` = `scripts/lib`。该目录在
检出根与运行时安装位**两侧都不存在**，于是每次运行都走 `except ImportError` 的字面量兜底：

- `canonical_root()` / `code_root()` 硬编码某台机器的检出根 ⇒ profile（`OMOSTATION_ROOT`）声明与否
  对这把尺**不可见**，而它输出的正是 profile 面读数（`state_root_distribution`）；
- 兜底 `install_root()` **永不返回 `None`** ⇒ 直接违反 BET-Y2Q4-T10-265 的 fail-closed 纪律。

修复：缝 → `parents[2] / "bin" / "lib"`；目录缺席 → `SystemExit`；`install_root()` 返回 `None`
→ `SystemExit`；整段静默兜底删除。

## 工程证据（4 条用例）

```
uv run --no-project --with pytest --with pytest-timeout --with pyyaml \
  python -m pytest tests/unit/test_b4b_ruler_seam_reachability.py -q -p no:randomly -o addopts=""
→ 4 passed in 2.13s
```

| 用例 | 钉住的判据 |
|---|---|
| `test_ruler_seam_resolves_to_the_real_repo_root` | 三个 resolver 的 `__module__ == "repo_root"`（真走缝，非同名兜底函数） |
| `test_ruler_source_has_no_checkout_literal` | 尺源码内不再出现检出根字面量 |
| `test_seam_depth_mutation_is_caught_by_the_guard` | **合成违规自证**：把缝改回 `parents[1]` 注入临时树 ⇒ 守卫当场 `SystemExit` 含「缝不可达」 |
| `test_ruler_fails_closed_when_install_root_absent` | `install_root() → None` ⇒ `SystemExit` 含「安装位」，不退回检出 |

前两条防「数值断言在兜底路径下同样绿」；第三条防「绿只是检测器没命中」；第四条防本轮要修的那个
具体违反（静默退回）。

## 读侧无回归：旧版 vs 新版逐字节对拍

同一棵检出、同一份 plist 面，兜底版与修复版各跑一次 `--json`：

| 维度 | 读数 |
|---|---|
| 顶层字段 | **9 个，0 处差异** |
| 叶子字段 | **19 个，0 处差异** |
| 两份 JSON | **逐字节相同**（`sha256` 一致） |

```
schema = launchd-workspace-reality-check/v1
total_plists = 84 | pointing_to_workspace = 2 | pointing_to_install = 40 | other = 42
state_root_distribution: checkout 0 | profile 35 | install 0 | undeclared 49 | other 0
workspace_categories: core_daemons 0 / resident_decision 0 / maintenance_gc 0 / unmanaged_other 2
```

**这条对拍的准确读法**：它证明本轮改动对读数零影响，因此历史 receipt 里的数字**没有错**。
它同时证明那些数字**不可复现、不可移植**——兜底字面量恰好等于这台机器的真实根，所以尺在
「换机器 / 声明 profile / 安装位缺席」三种情形下都不会改变输出，也就无法观察它被造出来要观察的东西。
本轮不推翻历史结论，只把量具接到能真证伪它的地方。

## 运行证据

| 检查 | 结果 |
|---|---|
| CI（`governance-check.yml` + 其余 legs） | **23 pass / 0 fail / 2 skipping**（`Documents domain projects`、`doc-freshness` 按 `on.paths` 跳过） |
| `mergeable` / `mergeStateStatus` | `MERGEABLE` / `CLEAN` |
| `ruff check` 两文件 | All checks passed |
| `bin/ssot/doc-governance-check.py --no-new-warnings --scope tracked --json` | `ok=True errors=0 warnings=0` |
| L3 深度安全审查（推送前，署名批准） | **0 findings** |
| affected-graph receipt | `runtime/affected/t281-receipt.json`（`receipt_hash 79c09ea5…`，用完即删、不进 commit） |
| 合并内容可达性 | `git merge-base --is-ancestor 58dc596e7 origin/main` = **YES**；三个文件在 `origin/main` 上存在且 spec 摘要与台账绑定值逐字节一致 |

⚠️ **`tests/unit/**` 在 CI 里不可见**（`.github/workflows/governance-check.yml` 的显式 pytest 白名单不含
该目录），所以这 4 条用例的唯一证据是本机那次 `4 passed`。这是本文件如实标注的边界，不是 CI 背书。

## 范围边界（本轮明确不做）

1. **`scripts/tools/spine-daily-ingress.py`**：同一个死缝，但它是 B4b 唯一仍在**真写检出根**的活面，
   6 个读者（其中 2 个在子模块内）仍锚检出。单独改缝会把一条活数据面劈成两半，需要署名裁定
   「spine 数据面是否跟随 profile」以及既有 buffer 的迁移/回填方案。**缺陷成立且正在发火，但不在本轮范围。**
2. **`tests/unit/test_writeplane_root_pin.py` 的枚举面扩展**：那是另一把尺的准入清单
   （CWD 相对锚类目缺失），与缝可达性是两件事。

## 附带取证：台账 note 的 YAML 注释截断（同轮发现，非本轮范围但已修）

写台账 evidence 后做解析回读（`yaml.safe_load` 后打印字段值，而不是只断言「能 parse」），
发现自己的 `value.evidence.note` 被截断：

```
磁盘上： note: B4b 量具可达性修复，…… 由工程腿 PR #5017 squash 58dc596e7 闭环。
解析后： B4b 量具可达性修复，…… 由工程腿 PR          ← # 起注释，后半段丢失
```

这是 AGENTS.md §7 已记过的形状（BET-Y2Q4-T10-277 那条 `note: … PR #4956 …`）。同形检查顺手做了
邻居条目，取证到 **`origin/main` 上的 BET-Y2Q4-T10-280 已有同一缺陷**：

```python
next(b for b in data['bets'] if b['id'] == 'BET-Y2Q4-T10-280')['completion_evidence'] \
    ['axes']['value']['evidence']['note']
# → '治理/根缝类任务，value_indicator_policy 声明为 false，由 PR'   （截断，磁盘文件本身完好）
```

本轮把这两处 note 一律改为双引号标量（T10-281 自身 + T10-280 的一行订正，同一文件、不同 BET 块，
不改任何摘要位或状态字段）。判据留在 retro 教训 6。

## 回滚

单文件尺 + 单文件用例，回滚 = revert `58dc596e7`。历史读数零变化（逐字节相同），
因此回滚不改变任何已发布的 B4b 结论。
