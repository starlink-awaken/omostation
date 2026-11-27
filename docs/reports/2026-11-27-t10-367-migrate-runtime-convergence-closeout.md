---
schema: md/v1
type: report
status: completed
lifecycle: evidence
owner: governance-agent
last-reviewed: 2026-11-27
bet_id: BET-Y2Q4-T10-367
---

# BET-Y2Q4-T10-367 收口回执 —— 宿主迁移路径一致性

> 事实以实测读数为准, 不填占位。宿主面未变更 (本 BET 只改发布器与身份契约,
> **本轮未在本机执行任何一次真实迁移或真实发布**)。

## 0. 交付坐标

| 项 | 值 |
|----|----|
| PR | [#5659](https://github.com/starlink-awaken/omostation/pull/5659) (squash merged) |
| merge SHA | `ebee26beb52fdf507f04d197c8b4a4e82d97ae70` (`git://origin/main@ebee26beb52fdf507f04d197c8b4a4e82d97ae70`) |
| 规格 | `docs/superpowers/specs/2026-11-27-host-migrate-runtime-convergence.md` (`spec_version 1.0.0`, digest `sha256:0ecc4ec0044dd25d86e6c5bfdf904556d7291b8496a3629e415da4f61185f127`) |
| CI | PR #5659 全部 job 绿 (`gac-gate` / `gac-gate-aux` / `governance-verify` / `interface-check` / `meta-doctor` / `integration (3.13)` / `evidence-gate` / `bet-done-transition` / `omo governance audit` / `ai-review` 等) |

## 1. 变更面

| 路径 | 变更 | lane |
|------|------|------|
| `bin/panorama/assets/host/release_identity.py.asset` | 身份契约新增 `deployment_baseline` 形态: `content_oid` 为被复制字节的内容摘要, 可从 release 字节独立重算; 文件集合必须恰好等于 `selected_assets`; `commit_oid` 保持 `null` | other |
| `bin/gac/zhixing-host-sync.py` | 清单对称 (基线写 `content_oid`, `_base_manifest_valid()` 与运行期 helper 同一判定); 绝对路径资产来源 (基线自带身份 helper); `migrate()` 接入运行期契约 (切换前证明可绑定 + 协调不可用拒绝, 切换后收敛验收, 不收敛回滚) | governance_code |
| `tests/unit/test_zhixing_migrate_runtime_convergence.py` | 新增 11 条判据用例 (基线可绑定 / 内容摘要可重算 / 篡改字节即拒 / 篡改 `content_oid` 即拒 / 发布器与运行期判定一致 / 协调不可用拒绝 / 收敛成功 / 降级判据显式标注 / 降级判据不被旧进程骗过 / 不收敛回滚 / 缺 helper 资产拒绝 / 幂等) | code |
| `tests/test_zhixing_host_sync_publish.py` | 既有发布面用例补上机器级动作替身 (launchd / `/health` 探针 / 收敛超时) + 基线身份资产, 保持 hermetic | code |
| `docs/superpowers/specs/2026-11-27-host-migrate-runtime-convergence.md` | 规格 (spec_version 1.0.0) | docs |
| `docs/plans/3y-bet-ledger.yaml` | 台账条目 + done-transition | docs_data |
| `.omo/_knowledge/retros/BET-Y2Q4-T10-367.md` | 复盘 | governance_state |
| `docs/reports/2026-11-27-t10-367-migrate-runtime-convergence-closeout.md` | 本回执 | docs |

## 2. 事实链

`migrate()` 是第三个会切 `current` 的入口, 但它只有 T10-366 的一半契约:

| 契约段 | `publish()` | `restore()` | `migrate()` (本轮前) |
|--------|-------------|-------------|---------------------|
| 运行期身份快照 `runtime_binding_snapshot()` | 有 | 有 | **无** |
| 切换前比两侧身份 `check_runtime_binding()` | 有 | 有 | **无** |
| 协调不可用 ⇒ 拒绝切换 | 有 | 有 | **无** |
| 切换后收敛 `coordinate_runtime()` + `/health` 验收 | 有 | 有 | **无** |
| 收敛失败 ⇒ 回滚 | 有 | 有 | **无** |

更靠前一层 —— **迁移激活的基线 release 在运行期根本绑不了**:

1. 基线清单形态 (`identity_kind=deployment_baseline`, `commit_oid=null`) 被运行期身份
   helper fail-closed 拒绝 (`release_manifest_source_invalid`);
2. 基线 release 里根本没有身份 helper (部署根本来就没有这个文件);
3. 发布器 `_base_manifest_valid()` 却接受这种运行期必然拒绝的清单 ⇒ 两套判定同源
   不同义 ⇒ 给出虚假的绿。

⇒ 契约缺口不在检查层, 在**两处**: 「切过去的东西本身不合法」与「切完之后不验收」。

## 3. 实测读数 (只读; 本轮未执行任何一次真实迁移或真实发布)

### 3.1 宿主部署面现状 (2026-11-27)

| 项 | 读数 |
|----|------|
| `~/.local/share/zhixing-dashboard/current` → | `releases/8f43efedc4e04e80e7612a68c6be046f4950c6cb` |
| `releases/` 目录数 | 55 |
| 其中带清单的 release | 54, `identity_kind` **全部** `git_commit` (无任何基线形态 release) |
| 部署根 `live_server.py` / `observatory_query.py` / `runtime_paths.py` | 全部 present |
| 部署根 `release_identity.py` | **absent** ⇒ 基线必须从仓库资产注入 helper |
| `releases/` 中带 `release_identity.py` 的基线 | 0 (潜伏缺陷, 尚未被激活) |

读法: 缺陷**潜伏** —— 但 `publish()` 的前置条件就是「先 migrate」(`reason=plist_not_migrated`),
一旦换机或回退到迁移前形态, 迁移必然交付一个「切了 `current`、但运行期绑不了」的宿主,
且旧实现返回 `ok: true`。部署根的三个代码文件齐备 ⇒ 注入 helper 后基线可绑定这一前提
在本机成立。

### 3.2 迁移的三态判定 (本轮后)

| 情形 | 判定 | 动作 |
|------|------|------|
| 基线 release 运行期绑不了 (缺 helper / 清单形态非法) | `baseline_release_unbindable` | **拒绝激活**: 不切 `current`, 不改 plist, 不留版本目录 |
| 绑定将被破坏且协调通道不可用 (采集器刷新作业未加载) | `runtime_coordination_unavailable` | **拒绝迁移**, `current`/plist 均不变 |
| 切换后运行期不收敛 | `runtime_convergence_failed` | **回滚**: plist + `current` + 版本目录复原 |
| 收敛成功且运行期报告身份 | `criterion=identity_bound` | 放行 (`code_drift=false` 且 `dashboard_code_oid == 基线 content_oid`) |
| 收敛成功但运行期不报告身份 (旧代运行期) | `criterion=service_available_only` | 放行, 但**必须**证明进程确实重启过 (pid 变化) —— 降级显式标注, 不得伪装成身份收敛 |

### 3.3 降级判据的可观测口径

只看「还活着 (200)」会把「重启没生效、旧进程仍在服务」当成收敛 ⇒ 降级判据额外要求
切换前后的 `/health` pid 不同 (`previous_pid`)。切换前运行期不可观测 (pid 未知) 时不作
此比较 —— 探不到即当时没在服务, 之后能通本身就说明进程起来了。

## 4. 验证

| 检查 | 读数 |
|------|------|
| `pytest tests/unit/test_zhixing_migrate_runtime_convergence.py` | 11 passed |
| `pytest` (发布面 6 suite: 新增 + release_identity + publish_runtime_convergence + producer_binding + host_sync_publish + host_sync) | **91 passed** |
| `python3 bin/plan/bet-ledger.py lint` | `OK -- 613 bets, 17 tracks, no errors` |
| `agent-workflow verify 20261127T124847Z-bet-execution-e7b761dc --from-diff --execute` | `ok (executed)`, `files=2 checks=1`, `[PASS] project-code-and-submodule-coverage` |

用例走**真实** `migrate()` / `publish()` 入口 (沿用「测试绕过接线就钉不住接线」),
launchd 动作与 `/health` 探针全部换成替身 —— 用例绝不真的 kick 本机服务。

## 5. 门禁实况 (预存红, 与本 diff 无关)

本机 `make gac-local-gate` 红在 `check-governance-ratio` (`ratio 47.5% > ceiling 40%`)。
该判据读的是 `.omo/_delivery/agent-workflows/events.jsonl` —— `.gitignore` 面、**未被 git
跟踪**的本机运行账本, 且在 worktree 与 canonical 共享同一 inode ⇒ 读数与任何 commit 的
内容无关; T10-366 回执 §5 已逐条量过 (剔除该轮 run 后比值 47.77%, 该轮 run 按
`bet-execution` 判为 `flex` 反而把比值**拉低**)。CI 侧干净检出里没有这份账本 ⇒
check 自报 `measured=false` 并 exit 0 ⇒ PR #5659 的 `gac-gate` 全绿。

⇒ 结论: 预存红, 归入「治理占比」这条**已知未收口**的主线 (继续用产品侧 flex 轮次稀释,
不动 `GOVERNANCE_CEILING` / `_classify` 判据面)。

## 6. 边界与残留

- **本轮不在本机执行任何一次真实迁移或真实发布** (机器级运行时变更, 属 principal 窗口);
  全部读数均为只读。
- **上宿主仍需两步**: 先 `bash bin/ssot/anchor-install-root.sh origin/main`
  (机器级: 运行时安装位 + code-main + 子模块 + omo venv), 再跑
  `zhixing-host-sync.py migrate` —— 本 PR 把它变成**自带基线可绑定证明 + 收敛验收**
  的事务, 第一步仍是 principal 的运行时窗口。
- **跨仓残留 (留给宿主仓裁决)**: 看门狗探针 `curl -s -o /dev/null` 缺 `--fail` ⇒
  HTTP 503 退出码仍是 0 ⇒ 只读态被判为「活着」⇒ 分级恢复链从不触发。
- **同族残留**: `publish()` / `restore()` 走**严格身份判据** (`identity_bound`); 若宿主
  长期处在「运行期不报告身份」的旧代形态, 这两条路径会一直判不收敛而拒绝发布 ——
  这是刻意的 (宁可不发), 但需要一次显式的宿主升级窗口, 而不是放宽判据。
- **治理占比仍在 30 天窗口 47% 量级** —— 继续用产品侧 flex 轮次稀释。
