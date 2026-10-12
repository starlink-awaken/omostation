---
schema: md/v1
status: completed
lifecycle: report
owner: governance-team
last-reviewed: 2026-10-12
type: closeout-receipt
bet_id: BET-Y2Q4-T10-246
title: BET-Y2Q4-T10-246 closeout receipt — 2 条占用 com.omostation 命名空间的异主服务登记为 observe-only（E2 3→1，并集 0）
---

# BET-Y2Q4-T10-246 closeout receipt

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-246`
契约：`docs/superpowers/specs/2026-10-12-services-e2-observe-only-backfill.md`（spec_version 1.0.0，digest `sha256:3ae89d69061f4a730d4a0a0b0bed5f0d8ebde9fa49a7d5aabfbd4208706d5971`）
Retro：`.omo/_knowledge/retros/BET-Y2Q4-T10-246.md`
交付：PR #4729 → squash `94ef45831`（2026-10-12，22 pass / 3 skipping / 0 fail，无 admin、无 `--no-verify`、无 `--force`；push 前 L3 深度安全审查 `findings_count: 0`）
性质：ADR-0456 **B4b 批次 2+ 的前置** —— 本轮不动本机 launchd，只让「已装 label == 注册表」这条中止判据在本仓可证

## 1 交付

| 面 | 位置 | 内容 |
|---|---|---|
| 注册表 | `.omo/_truth/registry/services.yaml` | +44 行，两条 `generate: false` observe-only 条目（services 371 → 373） |
| 规格 | `docs/superpowers/specs/2026-10-12-services-e2-observe-only-backfill.md` | 新档 150 行，含 §1b「E2 读数依赖检出注册表」陷阱 |
| 台账 | `docs/plans/3y-bet-ledger.yaml` | 新条目 `BET-Y2Q4-T10-246`，bets 543 → 544 |

登记的两条（均异主，本仓零生成）：

| label | plist 归属 | 键面 | 登记时状态 |
|---|---|---|---|
| `com.omostation.eg2-embeddings` | `~/.local/share/eg2-runtime`（外部运行时自装） | KeepAlive true + ThrottleInterval 10 + 3 env | running |
| `com.omostation.zhixing-brief-watchdog` | `~/dotfiles` commit `a63eb64` | StartInterval 120 + RunAtLoad + **ProcessType: Background** | not running |

## 2 读数（同机、同命令、同一 `--reality-check` 判据）

| 量 | 改前 | 改后（本检出） | 并集（改后 + 主区 panorama 声明） | 合并后 `origin/main` |
|---|---|---|---|---|
| E2 未声明 | 3 | **1** | **0** | 1 |
| E2 余项 | eg2 / panorama / brief-watchdog | `com.omostation.panorama-compact-observation` | — | 同左 |
| owned_declared | 40 | 42 | 43 | 42 |
| registry_declared_total | 68 | 70 | 71 | 70 |
| E1 漂移 | 1（`zhixing-projection-fullrefresh`） | 1（逐字未变） | 1 | 1 |
| E3 / E4 prefix / E5 | 0 / False / 1+1 | 零变化 | 零变化 | 零变化 |
| installed_total（本机） | 66 | 66 | 66 | 66 |
| workspace_scoped | 33 | 33 | 33 | 33 |

并集那一列是 **ISC-1b 的证据**，只在 `/tmp` 上算，不入仓、不改动任何一边的注册表：
把主工作区（`d06571798`，11 个未推送 commit）声明的 panorama 条目与本轮两条合到一份文件里，
E2 = 0 成立。也就是说「B4b 的 E2 中止判据」在两条线都落地后自然归零，本轮不冒充第三条的归属。

## 2b 机器可读读数快照（内嵌，不另立文件）

本轮 write_surfaces 不含新文件路径，而 `refresh-packet` 要求台账已等于 `origin/main`，
所以读数快照内嵌在本 receipt（已声明写面）内，而不是另落一个 canary JSON ——
这是范围纪律的结果，不是偷懒：`claim` 对未声明路径报 `WORK_PACKET_SCOPE_MISMATCH`（实测）。

```json
{
  "schema": "closeout-canary/v1",
  "bet_id": "BET-Y2Q4-T10-246",
  "generated_at": "2026-10-12T05:28:00Z",
  "command": "python3 bin/mof/gen-service-configs.py --reality-check --json --registry <registry>",
  "note": "E2 读数依赖运行命令时所在检出的注册表 (spec §1b)，三条读数分别命名其注册表来源。",
  "before": {
    "registry": "origin/main@b884e2919 (pre-merge)",
    "installed_total": 66,
    "owned_installed": 43,
    "owned_declared": 40,
    "workspace_scoped": 33,
    "registry_declared_total": 68,
    "unclassified": 0,
    "e1_drift": 1,
    "e2_undeclared": 3,
    "e2_undeclared_labels": [
      "com.omostation.eg2-embeddings",
      "com.omostation.panorama-compact-observation",
      "com.omostation.zhixing-brief-watchdog"
    ],
    "e4_prefix_ok": false,
    "e5_enabled_missing": 1,
    "e5_disabled_residual": 1,
    "rc": 1
  },
  "after": {
    "registry": "origin/main@94ef45831 (#4729 squash, 本检出)",
    "installed_total": 66,
    "owned_installed": 43,
    "owned_declared": 42,
    "workspace_scoped": 33,
    "registry_declared_total": 70,
    "unclassified": 0,
    "e1_drift": 1,
    "e2_undeclared": 1,
    "e2_undeclared_labels": [
      "com.omostation.panorama-compact-observation"
    ],
    "e4_prefix_ok": false,
    "e5_enabled_missing": 1,
    "e5_disabled_residual": 1,
    "rc": 1
  },
  "union": {
    "registry": "/tmp/t10246_union_services.yaml = 主区注册表(d06571798, 含 panorama) + 本轮两条; 不入仓",
    "installed_total": 66,
    "owned_installed": 43,
    "owned_declared": 43,
    "workspace_scoped": 33,
    "registry_declared_total": 71,
    "unclassified": 0,
    "e1_drift": 1,
    "e2_undeclared": 0,
    "e2_undeclared_labels": [],
    "e4_prefix_ok": false,
    "e5_enabled_missing": 1,
    "e5_disabled_residual": 0,
    "rc": 1
  },
  "validate": {
    "ok": true,
    "violation_count": 0
  },
  "registry_structure": {
    "yaml_docs": 2,
    "services": 373,
    "unique_ids": 373,
    "added_lines": 44,
    "removed_44_lines_equal_pre_merge_tree": "byte-identical to origin/main@b884e2919"
  },
  "host_untouched": {
    "com.omostation.eg2-embeddings": {
      "mtime": "2026-10-10T16:13:45.087312",
      "size": 979,
      "sha256": "5b79483fded24b45d81b812cd2e18a8ab71508e1dcf03847510a1990eaf8ba4f",
      "launchctl": "state=running",
      "before_equals_after": true
    },
    "com.omostation.zhixing-brief-watchdog": {
      "mtime": "2026-10-12T10:00:34.403402",
      "size": 766,
      "sha256": "16794d1ff99a86c6c9c39067c3ff00088895a817fabdabae0a24cfbb6dc632b6",
      "launchctl": "state=not running",
      "before_equals_after": true
    }
  },
  "tests": {
    "cmd": "python3 -m pytest tests/test_service_registry_reality.py tests/test_gen_service_configs.py -q",
    "passed": 32,
    "failed": 0
  },
  "ci": {
    "pr": 4729,
    "merge_sha": "94ef45831dfe7b5e3f20bc7844f3c5ef5be011b9",
    "pass": 22,
    "skipping": 3,
    "fail": 0
  }
}
```

## 3 ISC 逐条闭合

| 判据 | 反证方式 | 实测 |
|---|---|---|
| ISC-1 两条 label 离开 E2 桶 | 若 `e2_undeclared_labels` 仍含二者则否证 | 改后 E2 列表恰为 `['com.omostation.panorama-compact-observation']` ✅ |
| ISC-1b 并集 E2=0 | 若并集仍 >0 说明第三条并非异主 | `/tmp` 并集读数 `e2_undeclared=0` ✅ |
| ISC-2 不新增 E1 | `e1_drift` 或 drift 文本变化则否证 | `e1_drift=1`，finding 字符串与改前逐字相等 ✅ |
| ISC-3 不动 E3/E4/E5/installed_total | 任一字段变化则否证 | 全部 same（含 `enabled=true ⇒ 已装` 不变式） ✅ |
| ISC-4 `--validate` 零违规 | 任何 violation 即否证 | `ok=true violation_count=0` ✅ |
| ISC-5 本机 launchd 零触碰 | plist mtime/size/sha256/launchctl state 任一变化即否证 | 两条与登记前快照逐字节一致（`979`/`5b79483f…`、`766`/`16794d1f…`；running / not running） ✅ |
| ISC-6 注册表结构完好 | YAML 文档数、services 计数、id 唯一性 | 2 docs、373 services、373 unique ids、移除本轮 44 行后与 `HEAD` **逐字节相同** ✅ |
| ISC-7 测试面 | 目标用例非全绿即否证 | `tests/test_service_registry_reality.py` + `tests/test_gen_service_configs.py` → 32 passed ✅ |

## 4 为什么是 observe-only，而不是 exempt 或 generate: true

- **exempt 路结构上关闭**：`bin/mof/gen-service-configs.py:478-480` 把被 workspace 前缀遮蔽的
  exempt 项报成死数据；E2 桶按 `launchd_namespace.workspace_prefixes` 的 11 条前缀派生，不看路径。
  两条 label 命中 `com.omostation.` 前缀，标 exempt 也仍留在 E2 桶里。
- **`generate: true` 会造新债**：逐字节比对会让外部 plist（尤其 `ProcessType: Background`）立刻
  产生 E1 漂移，并把本仓变成异主 plist 的写者。
- **`generate: false` 的三处实现理由**：`--check` 跳过字节比对（`:645-652`）、
  `validate_service_declaration` 早退（`:142-165`）、`--validate` 对 launchd + generate:false
  跳过 `resolve_interpreter`（`:627-629`）。

## 5 门禁差异（`gac-local-gate --scope staged --json`，69 检查）

本轮引入的唯一硬拦是 `change-lane-check`：`governance_state` 与任何别的面不同 commit（
`bin/change-lane-check.py:207` 的 `len(lanes) > 1 ⇒ False`）。处置是**拆 commit 而不是放宽判据**：
`ce3eba6c5`（仅注册表）+ `f841ccd42`（spec + 台账，命中允许组合 `{docs, docs_data}`）。
收尾交付分三个单面 commit：retro（governance_state）/ report（docs）/ ledger（docs_data）。

其余硬拦均与本轮无关、且在 `origin/main` 基线上同样红：`service-config-drift`（E1 那 1 条，
需 `--write` + LaunchAgent 重载，属另一条授权线）、`check-work-landed`（2 条 10-04 他线 run
missing_landing）。软告警 2 条是干净检出的环境缺失：`test-mcp-kos`（无 `data/kos/kos-index.sqlite`，
exit 78 = skipped）、`current-state-coherence`（无 gitignored `.omo/state/system.yaml`）。
pre-push 面不跑 `change-lane-check`（`.githooks` / `bin/gac/hook-runner.sh` 实测），所以分支范围
聚合不会二次触发。

## 6 回滚

本轮无运行态副作用（launchd 零触碰、无生成物、无迁移）。回滚 = 反向提交那一个 squash commit：

```bash
git revert --no-edit 94ef45831   # 只撤注册表 44 行 + spec + 台账条目
```

撤完后 `--reality-check` 回到改前读数（E2=3），本机 66 个已装 label 一个未动。

## 7 未做（登记，不冒充完成）

- E1 那 1 条漂移的修复（需 `--write` + 重载 LaunchAgent，属授权线）。
- `com.omostation.panorama-compact-observation` 的归属：由声明它的并发线（`ccecdd571`）交付。
- 主工作区 11 个未推送 commit（`42e82e8c0..d06571798`）—— 只报告，不代它交付。
- E4 的 12 条 `com.local.*` 未分区、E5 的 `com.l4.omo.sync`（声明 enabled 未装）与
  `com.cockpit.dashboard`（disabled 仍装）。
- B4b 批次 2+ 的 plist/cron 改道：判据尺上 `workspace_scoped` 仍是 **33**（不是 plan 里写的 43；
  43 是 `owned_installed`，两个口径的混用已记在 spec §1）。
- `docs/architecture/ops-services-health.md:17` 的「338 个服务」早于本轮即为陈旧读数（实际 373）。
