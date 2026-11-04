---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-11-04
type: report
bet_id: BET-Y2Q4-T10-284
title: BET-Y2Q4-T10-284 closeout — 1 条已装未声明 label observe-only 回填（E2 复零）
---

# BET-Y2Q4-T10-284 closeout receipt

> 交付：`a52f7481b`（PR #5042，squash 合并到 main）
> PR #5042 是 **#5039 的受控后继**：base 前进到 `d53f975b1` 后 #5039 的 `governance-verify` 变红
> （§3 第 3 条），同样的 6 条提交在最新 main 上重放，文件面零交集。
> 分支提交（后继分支 `agent/governance-agent/audit-b4b-s2`）：`03ebe80ab`（准入：spec + 台账
> in_progress）、`a322de333`（services.yaml +1 条）、`100e3e95d`（spec 计数订正）、
> `ed2467bf4`（notes 去计数）、`09d09c7cb`（spec 补 owner/schema）、
> `1542a4adc`（台账 non_goals 修 YAML 平面缺陷）。

## 1. 结论

`.omo/_truth/registry/services.yaml` 追加 1 条 observe-only 条目（`user.omlx-smart-gateway`，
`generate: false`）后，同一份 `reality_check()` 在**同一检出、同一台机**上：

| 读数 | 剥掉本条（反证基线） | 交付后 |
|---|---|---|
| `e2_undeclared` | 1（点名 `com.user.omlx-smart-gateway`） | **0** |
| `owned_installed` | 51 | 51 |
| `owned_declared` | 50 | **51**（等式成立） |
| `e1_drift` / `e3_lint_debt` | 0 / 0 | 0 / 0 |
| `e5_enabled_missing` / `e5_disabled_residual` | 0 / 0 | 0 / 0 |
| `installed_total` / `external` / `unclassified` | 87 / 8 / 0 | 87 / 8 / 0 |
| `e4_prefix_ok` | False（未分区 22） | False（未分区 22，未被本条触碰） |
| `ok` | False | False（驱动项仍是 E4，非本条） |

plan `nimble-bay-asp` 的 B4b 逐批判据「每批切完 `--reality-check` E2 仍为 0」因此重新可满足，
批次 2 的阻塞解除。B4b 批次 2 本身（机器侧改道，任务 #91）**未**在本 BET 范围内推进。

## 2. done_when 逐条实测

1. `e2_undeclared == 0 且 owned_declared == owned_installed == 51` ——
   `--reality-check --json`：0 / 51 / 51。
2. 反证由同一次扫描产出 —— 对上版注册表副本（`t284-pre-edit-services.yaml`）调同一个
   `reality_check()`，得 `e2_undeclared 1` + `owned_declared 50`，其余字段与现读数全等。
3. 零扰动 —— 见 §1 表，e1/e3/e5 双向/installed_total/external/unclassified/e4 未分区逐字段同基线。
4. `--validate --json` → `ok true, violation_count 0`；`--check` → exit 0、`0 drift (76 launchd services)`。
5. `pytest tests/test_service_registry_reality.py -q` → **32 passed**（1.84s，其 E2 用例走
   `tmp_path` 合成注册表，无真实计数需重签）。
6. 本机 launchd 零改动 —— 交付前后逐字节一致：
   sha256 `c15d4cca95e90d6dc672d259a7160dad93bc93b6b971cd153bfda01590ffeda5`（同）、
   size 712（同）、mtime_ns `1793763413.684707801` = 2026-11-04T11:36:53+0800（同）、
   `launchctl print` `state = running`（同）。
   如实记录：`runs` 由 1 变 2、pid 由 49772 变 26415（进程 14:19:00 由 launchd 重新拉起）。
   本 BET 未执行任何 `bootout/bootstrap/kickstart`，plist 三个物理量不变 ⇒ 重启非本轮所造成。
   复测活性：`lsof` 127.0.0.1:18080 LISTEN（pid 26415）、`GET /gateway/status` → **200**（8ms）。
7. `make gac-local-gate` 硬失败集合 = 基线（**仅** `check-evidence-freshness`，冷检出的既有缺陷
   任务 #182；本轮零新增）。

## 3. 途中修掉的两个自造缺陷

- **spec frontmatter 缺 `owner`** → `missing_frontmatter:accepted-specifications count=1`
  落在未预算 warning 桶 ⇒ `unbaselined_warning` [error]，#5039 首跑 gac-gate /
  governance-verify / interface-check 红。补齐 `owner: governance-team` + `schema: md/v1`
  后本地 `doc-governance-check --scope workspace --no-new-warnings` 实测 `ok true`、
  5774 文件、0 error、45 条在册 warning、无一条指向本 spec。技能清单缺 `owner` 另立任务 #188。
- **台账 `non_goals` 三条被 YAML 当注释截断、一条误判成 mapping**（本 PR 引入，未进 main）：
  `…（任务 #147）` 里的 ` #` 使解析只剩「不收口 E4 的 22 条未分区（任务」。加引号后
  `yaml.safe_load_all` 复核五项全为 str 且文本完整。main 上同款既有债（BET-Y2Q4-T10-269 两条）
  另立任务 #186。
- 附带：把落在检出根目录的临时目录 `.tmp/` 移出检出 —— 它让 `root-directory-governance-scan`
  多出第 2 条硬失败（20 个未跟踪未 ignore 文件，非白名单）。移出后该扫描 `0 violation`，
  门禁回到基线 1 条。感知固化候选见任务 #187。

### 第三红：base 漂移 × CI 的两棵树（非本 diff 引入，但决定了交付路线）

`7867d7339` 推送后 `governance-verify` 红在 step `diff debt marker gate`
（`pytest tests/unit/test_diff_debt.py` → 2 fail，`ERROR: 无法解析 ref 'main'`）。取证：

- `git diff 04b1a669c..HEAD -- tests/unit/test_diff_debt.py` **为空** ⇒ 本 PR 从未碰该用例；
- main `d53f975b1`（#5041）**同时**做两件事：给该用例加 `git init -q -b main`（去掉对
  `init.defaultBranch` 的依赖 —— 本机两份 gitconfig 都配了 main，CI 两边都没配）并把
  step `diff debt marker gate` 接进 `governance-check.yml`；
- 该 job 显式 `ref: pull_request.head.sha`（检出的是我的旧 head tree），步骤集合却来自
  PR 的 merge ref（含新 step）⇒ **新尺跑旧用例**；main 自身 push CI 在同一 commit 上绿。

处置（不是绕）：先试 `git merge origin/main` —— pre-merge-commit 的 submodule-guard 要求
`git submodule update --init projects/family-hub`（照做后合并干净，parents = `7867d7339` + `d53f975b1`，
内容面 `git diff --name-status origin/main..HEAD` 只有我的 3 个文件）；但 pre-push 的 lane 尺
用 `rev-list --no-merges` 枚举 push 范围，把 main 的混 lane 提交 `d53f975b1`（code+docs+governance_code）
算进我的范围 ⇒ `change-lane-check: FAIL` 拒推（钩子不绕）。因此按 WP1 typed 指令改走
**distinct managed full successor**：在 `d53f975b1` 上逐条重放 6 个提交（文件面零交集，重放后
`--name-status` 无 `D` 行），开 PR #5042 全绿 squash 合并，#5039 标 superseded 关闭。
后继树上重测：6 个新接线用例 **36 passed**、`--reality-check` e2 0 / owned 51==51、
`doc-governance-check` ok=true 0 error 45 在册 warning。

## 4. 边界与未做

`launchd_namespace.workspace_prefixes` / `exempt_labels` / `--reality-check` 判据本体未动；
本条保持 `generate: false`，未生成或覆写任何 plist；E4 的 22 条未分区未顺带收口（任务 #147
署名裁定面）；`ok` 仍 False 未被「做绿」；不宣称 ADR-0456 任一阶段或整个 plan 完成。

个人工具入口脚本 `~/.local/bin/omlx-smart-gateway.py` 内含明文 bearer token —— 值未进入
services.yaml / spec / 台账 / PR / 本 receipt 任何一处；已向 principal 报告并建议轮换
（本机 plist 无 `EnvironmentVariables` 键，泄露面仅该脚本）。

## 5. value 轴

`value_indicator_policy: false`，value 轴 `NOT_PROVEN` —— 本条只是将既有现实登记进注册表，
使 B4b 的验收尺重新可用；没有新增可度量价值。
