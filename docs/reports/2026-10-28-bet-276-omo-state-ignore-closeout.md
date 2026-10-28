---
type: ephemeral
status: completed
owner: governance-team
last-reviewed: 2026-10-28
lifecycle: history
---

# BET-Y2Q4-T10-276 Closeout Report — `.omo/state` 运行态写面目录补 ignore + 源码派生守卫

> **BET ID**: `BET-Y2Q4-T10-276`
> **所属规划**: 3Y-BET-LEDGER (Y2Q4) / ADR-0456 B5 摘库残面
> **责任团队**: governance-agent
> **交付日期**: 2026-10-28
> **工程腿 PR**: [#4935](https://github.com/starlink-awaken/omostation/pull/4935) → squash `cad4585a3`
> **闭环状态**: **DONE / VERIFIED**（工程轴）；运行轴见 §3，价值轴 NOT_PROVEN

---

## 1. 交付目标与验收矩阵

台账 `done_when` 的四条判据与本轮实际交付的形状：

| # | done_when | 交付物 | 读数位置 |
|---|-----------|--------|----------|
| 1 | `git check-ignore -v` 对 daemon/healer/memory/notification 各命中一次并打印行号，新行与既有 9 条同构 | `.gitignore:318-328` 共 11 条目录级规则（尾斜杠、无通配） | §3.1 |
| 2 | `git status --porcelain -uall .omo/state` 改前 15 行 / 改后 0 行，由同一条命令产出 | 两份只由 `.gitignore` 不同的 scratch 检出，同一命令各跑一次 | §3.2 |
| 3 | 守卫用例含派生全覆盖、合成缺失被点名、唯一跟踪项不被吞 | `tests/unit/test_omo_state_plane_ignore_invariants.py`（6 条用例） | §3.3 §3.4 |
| 4 | hermetic：`HOME=<空>` + `env -u OMOSTATION_ROOT/…` 最小 venv 复跑 | 6 passed | §3.5 |

范围外（spec §4 逐条列出）：不改写者代码、不删本机 15 个运行时文件、不收紧既有 ignore/re-include
语义、不宣布 B1–B5 或整个 plan 完成、不碰 plist/launchd/crontab/权威 ledger。

## 2. 实际交付

- **`.gitignore`** +19 行（441 → 460）：6 行说明块 + 11 条目录规则。判据集合由源码导出，
  不是按"本机恰好长出的 4 个目录"手抄。
- **`tests/unit/test_omo_state_plane_ignore_invariants.py`** 新增：写目录集合由 `projects/omo/src/omo/**`
  的 AST 字面量导出（五种形状：`/`-链、整串、`Path("…")`、docstring 内联、嵌套续段），与
  `EXPECTED_KERNEL_DIRS` 做**集合相等**断言；忽略判定用两把独立的尺交叉核对
  （`git check-ignore --no-index` 与规则文本解析），两尺读数必须一致。
- **`docs/superpowers/specs/2026-10-28-bet-276-omo-state-ignore-completion.md`** 新增：契约与判据。
- **台账**：`accepted_specifications[0].content_digest` 按**字段路径**刷新为 spec 字节摘要
  （未用"块内出现即候选"的值反选，见 AGENTS.md §7 台账刷新条）。

**导出集与规则面的差**是本轮真正要钉的东西：源码派生出 14 个目录名，其中
`agent-cell/ agent-beliefs/ policy-radar/ runtime/` 此前已有规则，`healer/` 的写者
（`omo.resident.healer`）本机存在但未提交到 gitlink 钉住的 omo commit ⇒ 不在源码导出集内，
按实测单列并在 `.gitignore` 注释里点名。

## 3. 判据读数（装置与 base 一并记录）

### 3.1 `git check-ignore -v` 逐条命中

在合并后的树（`cad4585a3` 的 `.gitignore`）上：

```
.gitignore:318:.omo/state/compute/
.gitignore:319:.omo/state/daemon/            ← done_when-1
.gitignore:320:.omo/state/decision-graph/
.gitignore:321:.omo/state/im-triage/
.gitignore:322:.omo/state/agent-cell-memory/
.gitignore:323:.omo/state/agent-cell-replay/
.gitignore:324:.omo/state/memory/            ← done_when-1
.gitignore:325:.omo/state/notification/      ← done_when-1
.gitignore:326:.omo/state/refinement-snapshots/
.gitignore:327:.omo/state/refinements/
.gitignore:328:.omo/state/healer/            ← done_when-1
```

四条 done_when 探针各命中自己那一行；`rc=1`（零命中）在父树 `8f2675297` 上复现。

### 3.2 改前 15 行 / 改后 0 行（同一条命令，两个读数）

`git status --porcelain --untracked-files=all .omo/state`，两侧都是**只含 `.gitignore` 一个差异**的
scratch 检出，运行时面按**路径**物化为空文件（不复制本机运行数据）：

| 树 | 读数 |
|----|------|
| `8f2675297:.gitignore`（改前） | **15 行** |
| `cad4585a3:.gitignore`（改后） | **0 行** |

⚠️ 一条必须如实记的限定：**canonical 检出此刻仍读 15 行**（`/Users/xiamingxing/Workspace` 停在
`39a9d4e57`，落后 `origin/main`）。规则在 `origin/main` 上，共享检出一旦自行推进即为 0；本轮**不**
用 `sync-main.sh`/`reset --hard` 去快进它（AGENTS.md §6/§7：主区只读，`sync-main.sh` 默认
`reset --hard` 会在并发 agent 有未提交工作时销毁而非修复）。

### 3.3 唯一跟踪项不被吞

`git ls-files .omo/state` = `['.omo/state/collab-dualtrack.yaml']`（1 项）。对 4 条 re-include 探针，
`git check-ignore -v` 打印的是 `!` 反选行（`:306-309`），规则文本尺判定 `verdict=False`，
守卫用例 `test_tracked_state_exceptions_are_not_swallowed` 钉住这一面。

### 3.4 检测器自证 + 六组变异对照

`test_derivation_is_not_a_no_op` 在合成源上同时命中链式与整串两种形状，并排除两类不该进集合的段
（文件名段 `synthetic-plane.yaml.bak-20261028`、带尾 `-` 的 f-string 断头）。

变异对照复跑（收口腿 2026-10-28T05:41Z，装置 = 就地改 worktree 的 `tests/unit/…py` / `.gitignore`，
每条跑一次守卫用例后 `git checkout --` 还原并 sha256 对拍回提交态，6 条全部 `restored=True`；
基线 `6 passed`）。**每条都记「改法 → 哪几条红」**，因为只报计数会把"检测器没命中"也读成承重：

| 变异 | 改法（一次最小文本编辑） | 读数 | 红的用例 |
|------|--------------------------|------|----------|
| M1 | `.gitignore` 删掉 `.omo/state/daemon/` 一条 | 3 failed | 全覆盖 / 缺失被点名 / 15 项不再松散 |
| M2 | 同一条去掉尾斜杠（目录规则 → 文件规则） | 2 failed | 全覆盖 / 缺失被点名 |
| M3 | `.gitignore` 删掉 `.omo/state/healer/` 一条 | 3 failed | 全覆盖 / 缺失被点名 / 15 项不再松散 |
| M4 | 派生器关掉 `/`-链 AST 展平（只认整串） | 2 failed | **自证** / 契约集合相等 |
| M5 | 契约里塞一个源码导出不可能命中的名字 | 1 failed | 契约集合相等 |
| M6 | 规则文本尺去掉 `!` 取反（反选也算忽略） | 1 failed | 跟踪项不被吞 |

M4 是这轮最要紧的一条：摘掉展平后红的**包含自证用例本身**，说明"派生集合 = 契约"不是靠少认一种形状
凑出来的。M6 只红一条也如实记 —— 它证明"不被吞"那条承重，不证明其余五条承重。

### 3.5 hermetic 复跑与邻面

```
env -u OMOSTATION_ROOT -u OMOSTATION_STATE_ROOT -u OMO_EVENT_LEDGER_DB \
  HOME=<空目录> UV_CACHE_DIR=<空> uv run --no-project \
  --with pytest --with pytest-timeout --with pyyaml \
  python -m pytest tests/unit/test_omo_state_plane_ignore_invariants.py -q -p no:randomly
→ 6 passed
```

依赖面由最小 venv 供给（`HOME=<空>` 会同时摘掉装在 user-site 的 pytest，用宿主解释器跑出的
`No module named pytest` 是装置没搭对，不是回归）。邻面：同目录 7 个测试文件合计 **975 passed**。
`python3 bin/plan/bet-ledger.py lint` → `OK -- 573 bets, 16 tracks, no errors`。

### 3.6 CI 读数与一条证据边界

工程腿 PR #4935 终态读数 **20 pass / 2 skipping（`on.paths` 过滤）/ 0 fail**，
`mergeable=MERGEABLE`、`mergeStateStatus=CLEAN`，squash 为 `cad4585a3`。

**但 `tests/unit/**` 不在 `.github/workflows/governance-check.yml:118-127` 的显式 pytest 白名单里**
⇒ CI 绿**不构成该守卫的证据**；守卫的证据只有 §3.5 的本地 hermetic 读数与 §3.4 的变异对照。这是
本轮最容易被误读成"已验证"的一点。

### 3.7 本地门禁两处 FAIL 的归类（未绕过）

- `CR-RESIDENT-BOS-01`：本 worktree `services=0` FAIL，canonical 同一条命令 `services=8 registry=8
  allowlist_resident=True` PASS ⇒ 新生成态面在干净 worktree 里缺席，属**环境/缺席面**类，与本轮 diff
  （gitignore + 两个新文件 + 台账一行）无因果。
- `check-evidence-freshness`：`generation_failed — import_failed`，明细 `No module named 'agora'`；
  `projects/agora` 在 claim 后仍是空检出（0 条目，`submodule update --init --depth 1` 后依旧）。
  同类环境类，CI 侧对应 job 绿。

两处都没有用 `--no-verify`、没有放宽判据、没有改窄断言。

## 4. 残留（登记，不在本轮处置）

1. **`bin/` 侧 5 个目录未被源码派生覆盖**：`evolution-proposals/ handoffs/ heartbeats/ mos/
   proposals/` —— 守卫的导出面只扫 `projects/omo/src/omo/**`，`bin/` 内的写点按构造看不见。
   另有**变量后缀名**（`convergence-pulse-{周}`、`m2-ssot-batch-{N}`）静态字面量导出按构造不可达。
2. **canonical 工作区的并发未提交工作**会改变派生尺可见面（本机 `src/omo/resident/healer.py` 等
   5 个文件为未提交态）。本轮不碰、不据它扩张契约；`healer/` 因此是"实测单列"而非源码导出项。
3. **canonical 检出的 15 行噪声**要等共享检出自行推进到含 `cad4585a3` 的树才归零（§3.2 限定）。

## 5. 回滚

工程腿是**单提交、纯追加**：`git revert cad4585a3`（或反向 PR）即回到 `8f2675297` 的规则面与守卫缺席
态；未跟踪文件、既有 re-include 行、任何写者代码都没被触碰，因此不存在需要"恢复被删数据"的半边。
回滚后的复算判据 = §3.1 的 `rc=1`（零命中）与 §3.2 的 15 行。
