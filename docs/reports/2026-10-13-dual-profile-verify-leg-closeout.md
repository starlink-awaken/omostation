---
schema: md/v1
type: closeout-receipt
status: completed
lifecycle: report
owner: governance-team
last-reviewed: 2026-10-13
bet_id: BET-Y2Q4-T10-248
---

# Closeout receipt — BET-Y2Q4-T10-248 双 profile verify 腿

- **交付**：分支 `agent/governance-agent/t10-248-dual-profile-verify`（源冻结 `d06509559`，3 commits）
  → PR **#4741** → squash 合并 **`b59797e6d7ba4e18b33d4ab8d1329aec0e4d8b64`**
  （merged_at `2026-10-13T07:17:52Z`，CI 16 pass / 1 skipping）。
- **合并面**：`bin/gac/dual-profile-verify.py`、`bin/_registry/scripts/governance/dual-profile-verify.yaml`、
  `tests/unit/test_dual_profile_verify.py`、`.github/workflows/governance-check.yml`（白名单第四件）、
  `.omo/_truth/registry/governance-checks.yaml`（`script_baseline: 720 → 721`，具名授权）、
  spec `docs/superpowers/specs/2026-10-13-dual-profile-verify-leg.md`。
- **零运行时效应**：launchd plist 43 条与 crontab 一行未改，权威 ledger 未翻，
  `.omo/state/**` 写目标未改道（B4b 分批授权面）。

## 验收复跑（2026-10-13，在 `origin/main` 已含 `b59797e6d` 的检出上）

| # | 命令 | 读数 |
|---|---|---|
| V1 | `env -u OMOSTATION_ROOT -u OMOSTATION_STATE_ROOT -u OMO_EVENT_LEDGER_DB … pytest tests/unit/test_dual_profile_verify.py -q` | **22 passed** |
| V2 | `dual-profile-verify.py --profiles prod,dev --json` | **rc=0**；两腿 root 互不相同（各自 scratch），`landing` 均在本腿 root 之下且文件真实存在（`<root>/.omo/state/system.yaml`），`ok: true` |
| V3 | `dual-profile-verify.py --profiles prod --json` | **rc=1**（ISC-1 反证：单 profile 不得被当成「两个 profile 各跑一遍」） |
| V4 | `python3 bin/ssot/script-registry.py validate` | **VALIDATION PASSED: 721 scripts registered**（missing=0 / extra=0，ISC-9） |
| V5 | `make gac-local-gate` | 硬失败集合与起手基线一致，零新增：`resident-bos-check`（`bos-services.yaml` 本地与 `origin/main` 皆无）、`check-evidence-freshness`（走 `.omo/_delivery/` 共享桥的 import 失败）两条为环境/预存项，均不读本 BET 交付文件 |

`install_root` 探针读数（V2 内）：`target=/Users/xiamingxing/.local/opt/omostation`、
`head=1b5f02cb35ef6bc27363bbaa9458b90c710f4157`、`is_ancestor=true`、`behind=312`、
`status=warn`。按 ISC-5 语义这是告警不是中止；CI 干净检出探不到时记 `deferred`，**不得记 pass**。

## 变异对照（ISC-8，交付轮实测）

- 剥掉落点断言 → **2 failed**；
- 把 profile 名单收成单元素 → **1 failed**；
- 逐字节还原后回到全绿且红集合与基线逐项相等。

## 隔离核对（ISC-4）

双腿默认解析出的 root 是脚本自建 scratch 目录（`$TMPDIR/dual-profile-{prod,dev}-*`），
既不在检出根之下、也不在 `~/.local/state/omostation/**` 之下；跑完后
`git status --short` 对声明写目标为空——**本轮没有向任何权威面写过一字节**。

## 回滚

`git revert b59797e6d`（单条 squash commit）即撤全套：脚本、登记、用例、CI 接线、registry 一条。
无数据面副作用（无迁移、无写目标改道），回滚后 `script_baseline` 回 720。
