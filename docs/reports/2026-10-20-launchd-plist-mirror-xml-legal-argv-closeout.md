---
type: report
status: completed
owner: governance-team
last-reviewed: 2026-10-20
bet_id: BET-Y2Q4-T10-260
title: BET-Y2Q4-T10-260 closeout — 仓内唯一不可解析的 launchd plist 镜像（argv 移到 Python 侧）
---

# BET-Y2Q4-T10-260 closeout — plist 镜像 XML 合法性消除

交付物：`docs/superpowers/specs/2026-10-20-launchd-plist-mirror-xml-legal-argv.md`
（spec_version 1.0.0，content_digest `sha256:922daf45f32cd9aca6d43096e5c1ce35042a580fef4ce97eefdad1e00edbb418`）
台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-260`
PR：#4832 —— squash 合并为 `011f7b953d9a64c97d3f3c20d3432e81c9cd6144`（CI 终态：26 项检查 = 23 pass / 3 skipping（Documents domain projects、doc-freshness、health-check 按 on.paths 过滤）/ 0 fail）
Run：第一腿 `20261020T025627Z-project-doc-change-cf8b7a0f`（workflow `project-doc-change`，
underlying `governance-state-mutation`，work_packet_hash `sha256:10079257415d26719650b5c38e44cbf50ae6dc8ca4509c6bdebc3c111c7d4853`）；
第二腿 `20261020T035750Z-project-doc-change-60d72e4e`（同 workflow，claim 新增那条测试路径）；
本收口腿 `20261020T041439Z-project-doc-change-f83988f4`（claim retro / 本 receipt / 台账三条面，
work_packet_hash 与第二腿逐字相同 `sha256:e8a824349d6c6ba75e36d8fe9f51c6a9f4627247d60e684522eeb8444e94e265`
—— 本腿只回填非投影字段，所以哈希不变）。
两 run 并存的原因：第二腿改了 packet 投影字段（`write_surfaces` / `done_when` / `verify`），
旧 run 的 claim 一律 `WORK_PACKET_SOURCE_DRIFT`，而本仓 `refresh-packet` 不可用
（实现在 `bin/agent-workflow.py:678/814/1031`，argparse 子命令表未注册）⇒ 按 T10-259 的结论用新 run 承接。

## 1 diff

| 文件 | 变化 |
|---|---|
| `bin/ops/launchd/com.omostation.panorama-refresh-guard.plist` | `:26` 注释体内的命令行改为指向脚本模块文档的指针；注释内不再有连续两个半角连字符 |
| `bin/gac/panorama-refresh-guard.py` | 模块文档新增 `Manual check` 行，逐字承载 `python3 bin/gac/panorama-refresh-guard.py --json --dry-run` |
| `docs/superpowers/specs/2026-10-20-launchd-plist-mirror-xml-legal-argv.md` | 新建（canonical 位，frontmatter 含 `owner` / `lifecycle: contract`） |
| `docs/plans/3y-bet-ledger.yaml` | 新 BET 条目，经 `bin/gac/ledger-safe-insert.py` 定位插入（`+83/-1`）；第二腿补 4 处（见下） |
| `tests/unit/test_ops_launchd_plist_declared_guard.py` | **第二腿**：把钉在「这份 plist 不可解析」上的绊线换成不变式（合成样本覆盖回退分支 + 一条「已合法且缺口仍敞开」）；`ALLOWLIST` 集合本体、`labels_from_plists` 回退实现、集合相等与检测器自证两条用例逐字未动 |

两腿合计 5 文件、226 insertions / 14 deletions（逐文件 numstat：`2/0`、`1/1`、`93/1`、`85/0`、`45/12`；
第一腿单独为 4 文件 `171/2`）。检测器 `tests/unit/test_launchd_plists_xml_safe.py` **逐字未改**。

第二腿的台账 4 处补齐：`write_surfaces` 加本条测试文件（第 5 面）；`non_goals[1]` 补全
（原文本被明文标量里的 ` #124` 静默截断成 `…该不该活（属 task`，现改引号标量并逐字回读确认）；
`done_when` 加一条覆盖绊线；`verify` 加一条同时跑两个测试文件，并把 V3 的 `expect` 改成实测读数。

## 2 tests（基线 → 终态，同一 worktree、同一解释器）

| # | 命令 | 基线 @`origin/main@0329ceeb3` | 终态 |
|---|---|---|---|
| V1 | `plistlib.loads(<mirror>).read_bytes()['Label']` | `ExpatError: not well-formed (invalid token): line 26, column 48` | `com.omostation.panorama-refresh-guard`，rc=0 |
| V2 | `pytest tests/unit/test_launchd_plists_xml_safe.py -q -p no:randomly`（`uv run --no-project --with pytest --with pytest-timeout --with pyyaml`） | `2 failed, 2 passed` | **`4 passed`** |
| V3 | `git grep -n "panorama-refresh-guard.py --json --dry-run"` | plist `:26` 命中（非法源） | plist **0 命中**；`bin/gac/panorama-refresh-guard.py:15` 命中 |
| V4 | 注释体 legality（regex over `<!--…-->`，python） | offender 1 行 | `comment blocks: 1 / "--" inside any: False` |
| V5 | `python3 bin/plan/bet-ledger.py lint` | —（插入时即为该读数，未另取改前基线） | `OK -- 554 bets, 16 tracks, no errors` |
| V6 | `python3 bin/ssot/doc-governance-check.py --json --scope workspace` | —（本轮未单独取改前读数） | `ok: true`，`files_scanned 5052`，`findings 30`，指向本 spec 的 finding **0 条**；`accepted-specifications` 桶无未基线告警 |
| V7 | `ast.parse` + docstring argv 复核 | — | `ast.parse OK; docstring carries argv: True` |
| V8 | `pytest tests/unit/test_ops_launchd_plist_declared_guard.py tests/unit/test_launchd_plists_xml_safe.py -q -p no:randomly` | CI `interface-check`：`1 failed, 408 passed, 9 skipped`（红的是 `test_malformed_plist_still_reports_its_label`） | **`14 passed`** |
| V9 | 同上再加 `tests/unit/test_panorama_refresh_guard.py` | — | **`26 passed`**（改脚本模块文档没有碰到那份用例的行为面） |
| V10 | 变异对照：把 `--` 注回 plist 注释体 | — | `3 failed`（绊线有牙齿）→ 逐字节复原后 `sha256` 与 HEAD blob 相等，`disk==HEAD blob: True` |

### V3 的如实读数（判据措辞偏差 → 第二腿按实测改写）

done_when-2 / verify-3 的第一版 `expect` 写作「命中仅出现在 `bin/gac/panorama-refresh-guard.py`」。
实测 `git grep` 共 6 处命中，除 `guard.py:15`（本轮的目标落点）外另有 5 处**散文引用**：

- `docs/plans/3y-bet-ledger.yaml:43583` —— 本 BET 自己的 `goal` 文本引用了这行命令行；
- `docs/plans/3y-bet-ledger.yaml:43634` —— 本 BET 自己的 `verify` 命令文本；
- `docs/superpowers/specs/2026-10-19-services-e2-observe-only-backfill-5.md:163` —— T10-258 spec 对这条缺陷的记录；
- 本 BET spec 的 `:29` / `:49` —— C2 条款必须逐字写出该 argv 才能被下一轮核对。

**处置（诚实说明，与第一版的措辞相反）**：第二腿把这条 `expect` 文本改成实测读数
（「任何 plist 内零命中；代码面唯一命中是 `bin/gac/panorama-refresh-guard.py` 的模块文档，
其余命中是记述这一缺陷的文档」）。这不是「删引用凑数」也不是改窄断言 —— 判据的实质两半
（非法源所在 plist 0 命中、信息仍在仓内可 grep 且落 Python 侧）逐字保留，被改掉的只是
一个**从未成立的量化词**。第一版此处写「不改台账措辞」，实测面前不成立，已订正。

## 2b 绊线的报错文案要求「登记进 services.yaml」，本腿不采纳

`test_malformed_plist_still_reports_its_label` 的失败消息写的是：该 label「应同时从 ALLOWLIST 摘除
**并登记进 services.yaml**」。前半句在前提消失后确实该摘（本腿把理由改了、集合相等断言仍要求它留在
清单里，因为缺口未变），后半句是三条权威来源一致排除的动作：

1. 本文件 `:33` 自己的注释：「它同时未声明，且未装机；登记与否同样是署名面」；
2. BET-Y2Q4-T10-258 的 `circuit_breaker` 明文：「若为过 ISC-4 而必须把 … 塞进 services.yaml → 停止，
   改用评审清单而不是替它们决定『该不该活』」；
3. task #124 的 21 条准入清单（T10-259 交付的取证面）里，这条 label 的准入是待署名项。

因此本腿只做**前提维护**：把「非法 XML」这条一次性事实从豁免理由里摘掉、用合成样本继续覆盖回退分支、
并新增一条把「文件已合法」与「缺口仍敞开」同时钉住。测试文件的 ALLOWLIST 由集合相等断言
（`test_allowlist_is_exactly_the_measured_undebt`）守护 —— 若后续有人无署名登记它，那条断言当场红。

## 3 live canary（运行面零效应的正向读数）

| 观测 | 期望 | 实测 |
|---|---|---|
| `~/Library/LaunchAgents` 内名字含 `panorama-refresh-guard` 的条目数 | 0 | **0** |
| `~/Library/LaunchAgents/*.plist` 总数 | 77 | **77** |
| `crontab -l` 的 sha256 前 16 位 | `cbf14ddc2fdd972a` | **`cbf14ddc2fdd972a`** |

计数用 python（`pathlib.iterdir` / `hashlib`）而不用 `ls | grep -c`：零匹配会让管道断链，
本机 `ls` 是 eza 别名、`grep` 是 rg 别名。未做任何 `bootout` / `bootstrap` / `kickstart`，
未写 `~/Library/LaunchAgents`，未改 crontab。

## 4 replay

`python3 -c "import plistlib,pathlib; plistlib.loads(pathlib.Path('bin/ops/launchd/com.omostation.panorama-refresh-guard.plist').read_bytes())"`
对 merge 后的 `origin/main` 检出重跑一次即可复现 V1；V2 用 `uv run --no-project --with pytest
--with pytest-timeout --with pyyaml python -m pytest tests/unit/test_launchd_plists_xml_safe.py -q -p no:randomly`。
两条均不依赖 host 状态（不读 `~/Library/LaunchAgents`、不 import 子模块）。

## 5 rollback

单 commit 逆向即回滚：`git revert 011f7b953d9a64c97d3f3c20d3432e81c9cd6144`（无数据迁移、无生成态、无子模块指针变化）。
回滚后镜像回到 `ExpatError`，检测器回到 `2 failed, 2 passed` —— 即恢复一个已知红，而非引入新债。

## 6 cleanup

- 临时件全部删除：`runtime/affected/t260-receipt.json`、`runtime/affected/t260-leg2.json` 与
  `runtime/affected/t260-closeout.json`（三腿 claim 用的 affected-graph receipt，
  `--changed-projects workspace-root`，用完即删、未进 commit）、`/tmp/t260/` 验算副本、
  `/tmp/t260-bet-entry-*.yaml` 草案、`/tmp/t260-docgov.json`、`/tmp/t260-checks.json`。
- 未提交任何生成态：交付 diff 里没有 `.omo/state/**`、`BRIEF.md`、子模块 gitlink。
  `git diff --name-status origin/main..HEAD` 只有 5 行 `M/A`，无 `D` 行（无 base 漂移反向条目）。

## 7 scope 边界（未做的事）

不判定 `com.omostation.panorama-refresh-guard` 该不该活（属 task #124 的 21 条准入清单）；
**第二腿同样没有替它登记进 `services.yaml`**（理由见 §2b）；
不扩 `.github/workflows/governance-check.yml:118-127` 的 pytest 白名单把 `tests/unit/**` 接进 CI
（这是 main 恒红而 CI 恒绿的根因，需独立评估）；不动检测器判据、不加豁免、不把注释挪到
`<!DOCTYPE` 之后；不改 `services.yaml`、不写运行面。**不宣布 ADR-0456 B1/B3/B4/B5 或整个 plan 完成。**

顺带发现、**未在本 BET 内处置**的独立缺陷（如实登记，不夹带修复）：全台账括号配平审计读出
18 条不配平字符串，除本 BET 这一条真截断外另有 15 条分布于
`BET-Y1Q3-T10-62 / BET-Y1Q3-T6-04 / BET-Y1Q3-T8-02 / BET-Y1Q4-HITL-02 / BET-Y1Q4-T16 /
BET-Y1Q4-T8-24C / BET-Y2Q1-T7-05 / BET-Y2Q4-T10-203 / -217 / -222 / -225 / -229 / -232 / -233 / -237`，
它们是同类 `#` 静默截断还是无害折行**尚未逐条定性** —— 需一条独立的 triage BET
（判据：dup-aware 扫描 + 逐条回读，不在治理收口腿里顺手改别人的台账条目）。
