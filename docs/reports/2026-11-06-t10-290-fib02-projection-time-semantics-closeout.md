---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-11-06
type: report
bet_id: BET-Y2Q4-T10-290
title: BET-Y2Q4-T10-290 收口收据 —— FIB-02 投影租约/内容观测/复制时间分开展示
---

# BET-Y2Q4-T10-290 收口收据

工程腿 = PR #5071 squash `3349250e8435c0f175da7eb3d29f01d48c9da036`
（`2026-11-06T03:56:01Z` 入 main，7 件：`bin/panorama/assets/host/live_server.py.asset`、
`bin/panorama/assets/host/template.html`、`tests/unit/test_live_server_payload_freshness.py`、
`tests/unit/test_live_server_time_semantics.py`、`tests/unit/test_dashboard_panel_assets.py`、
spec、台账）。**工程腿由另一会话交付**，本收据是收口腿：现网只读取证 + 定向测试复跑 +
retro + 台账 `done`/evidence。

## 1. done_when 逐条判定

| # | 条款 | 判定 | 证据 |
|---|------|------|------|
| ① | 租约/内容观测/副本时间分开展示；未知值明确不可判 | **成立** | 现网 `/health` 的 `projection_time_semantics` 五元组（`state_revision`/`content_generated_at`/`content_status`/`lease_fresh_until`/`lease_status`）与 `materialized_brief` 十字段并列返回，见 §2 读数 A/B；未知侧一律 `UNKNOWN`/`UNCONFIGURED`，无 `now`/`0` 伪造 |
| ② | 更新租约与复制时间不使旧内容转鲜；300 秒 TTL 边界不变 | **成立** | 副本面 `current.json` 于 `06:24:01Z` 重写，同一进程读数仍为 `content_generated_at=2026-11-05T14:59:43Z` + `content_status=STALE`，而 `lease_status=VALID`（§2 读数 B）；TTL 两处常量在**部署那份**仍为 `_GATEWAY_KEY_TTL = 300.0`（`:72`）与 `bound_payload_freshness(revision, *, max_age_seconds=300)`（`:1573`） |
| ③ | revision 及 manifest/code 摘要保留；既有错误态保持 fail-closed | **成立** | `state_revision=1754eefc6dca…` 未缩短；`projection_error=projection_payload_stale` 仍如实上报；`code_drift=False` 且 `dashboard_code_sha256 == expected_dashboard_code_sha256 = f3a025b8755c…` |
| ④ | 定向测试通过且记录静态测试与生产运行的证据边界 | **成立** | 70 passed / rc=0（§2 读数 C，装置写明）；生产运行证据 = §2 读数 A/B/D 与「本轮无部署动作」的 §5 限制①，两者分栏不混 |

## 2. 读数（每条都带产出该读数的 base）

**A. 现网 `/health` 第一次 —— `2026-11-06T06:23:56Z`**
服务进程 PID 78127，cwd
`~/.local/share/zhixing-dashboard/releases/17afa5408a01b164af14be4c559f615766715025--pub-0c898071716f40368528150bcb2e4b02`，
监听 `127.0.0.1:43191`。

```
projection_time_semantics = {state_revision: 1754eefc6dca2c63d5dfc3fc3f1066040f2f9cf32f371f38bac356d68d142f5f,
                             content_generated_at: 2026-11-05T14:59:43Z, content_status: STALE,
                             lease_fresh_until: 2026-11-06T06:30:22Z, lease_status: VALID}
materialized_brief        = {status: UNCONFIGURED, copied_at: null, copy_status: UNKNOWN,
                             data_generated_at: null, data_status: UNKNOWN,
                             provenance_comparison: UNKNOWN, revision_match: UNKNOWN,
                             provenance_trust: SELF_REPORTED, source_revision_id: null,
                             source_manifest_sha256: null}
projection_error = projection_payload_stale | payload_age_seconds = 55453.886
code_drift = False | payload_generated_at = 2026-11-05T14:59:43Z
```

**B. 现网第二次 —— `2026-11-06T06:28:15Z`**（中间发布器刚重写副本文件）

```
current.json: mtime = 2026-11-06T06:24:03Z, generated_at = 2026-11-06T06:24:01.316321+00:00（17,299,345 B）
/health:      content_generated_at = 2026-11-05T14:59:43Z（未变）, content_status = STALE,
              lease_status = VALID, lease_fresh_until = 2026-11-06T06:30:22Z,
              payload_age_seconds = 55712.982, state_revision = 1754eefc6dca…
```

副本时间前进 4 分 18 秒而内容观测时间纹丝不动，这是 AC-2/AC-3 在现网的直接形状。
机制落到行：部署码 `live_server.py:1785` 的 `content_generated_at` 取
`health["payload_generated_at"]`，`:1786` 的 `lease_fresh_until` 取
`health["projection_fresh_until"]`，两者不同源。

**C. 定向测试（ledger `verify[0]` 等价复跑）**
现场 = `/Users/xiamingxing/ws-t289-finalize` @ `2f52fccbe`（该树与 `origin/main` 在这三个
测试面与资产面内容等价）。台账原文写 `/Users/xiamingxing/Workspace/.venv/bin/python`，
但共享主区停在 `0b67fac45`（不含 #5071），照原文跑会测旧码，故换成最小 venv 复跑：

```
HOME=$(mktemp -d) UV_CACHE_DIR=$(mktemp -d) \
  env -u OMOSTATION_ROOT -u OMOSTATION_STATE_ROOT -u OMO_EVENT_LEDGER_DB \
  uv run --no-project --with pytest --with pytest-timeout --with pyyaml \
  python -m pytest tests/unit/test_live_server_payload_freshness.py \
      tests/unit/test_live_server_time_semantics.py \
      tests/unit/test_dashboard_panel_assets.py -q
→ 70 passed in 36.09s   rc=0
```

第一次跑的输出是 `error: unrecognized arguments: --timeout=300`（装置缺 `pytest-timeout`，
`pyproject.toml` 注入该 flag），**0 条用例执行** —— 已按补插件后的读数记录，不采用那次空跑。
`verify[1]` `git diff --check` 在同棵树 rc=0。

**D. 生产码面 = 交付码面（逐字节）**

| 对象 | 部署侧 sha256 | `origin/main` 侧 sha256 | 一致 |
|------|---------------|--------------------------|------|
| `live_server.py`（= 仓内 `live_server.py.asset`） | `f9fd5eb4b968892865f095d4be76f2deca37ccce531e9e1343774968151b6d47` | 同值 | ✓ |
| `template.html` | `70999e0798671450ee6567e1f9d102ac5f1b8dcd9a07bdd758efe7d161b34904` | 同值 | ✓ |

部署目录名里的 OID `17afa5408` 是工程分支上的 commit（标题
`test(panorama): 覆盖投影与副本时钟边界`），squash 后**不在** `origin/main` 祖先图内 —— 所以
「生产是否跑到这次交付」不能问祖先，只能问这两行摘要。

## 3. 归属与偏离（不冒充）

- 工程腿的作者不是本会话；本收据只承接收口腿的取证与登记。台账原记
  `engineering: NOT_STARTED` 与事实不符（码已合且已投放），本轮按实测改记。
- spec 草稿的 `bet_id` 曾被误写为 `BET-Y2Q4-T10-286`（已被 #5062 占用），工程腿第三个 commit
  才改为 T10-290 并同步摘要。台账 `accepted_specifications[0].content_digest`
  = `sha256:2f9324db759eb73ecb076619754794d40ea0df5a7338c4c2c33bee8214b1a691`，本轮**一字未改**，
  且已由校验器对 spec 字节复算通过。
- spec「非目标」写有「不得 commit、push」，而交付实际走了 PR #5071。本条只登记冲突事实，
  不追溯改写契约。

## 4. 回滚

撤回工程腿即回滚本条交付：

```
git revert 3349250e8435c0f175da7eb3d29f01d48c9da036
```

squash 提交是单亲，**不要加 `-m 1`**。回滚只覆盖仓内码面；已投放的生产侧要等发布器下一次
成功同步才会跟着回退，因此回滚后须重跑 §2 读数 D 的两行摘要比对，不能只看 PR `MERGED`。

## 5. 限制（三条，逐条给判据）

1. **本轮零部署动作**。生产码面等于 main 是发布器
   `com.omostation.zhixing-projection-fullrefresh`（`runs=192`，日志
   `~/.local/log/projection-fullrefresh.log` 近期 400 行内 0 条非零 rc）自己推进的结果。
   不得据此声称「本轮让改动生效」。判据：投放者身份看发布器日志，码面等价看 §2 读数 D。
2. **`materialized_brief` 整面 `UNCONFIGURED`** —— 副本侧的 `copied_at` /
   `data_generated_at` / `source_manifest_sha256` 全为 `null`，`provenance_comparison`
   与 `revision_match` 为 `UNKNOWN`。所以 AC-3 的「副本时间标注来源」现网只证到
   「不伪造、明确不可判」，**未**证到「展示真实复制时间」。这不是 T10-290 的回归（配置面未开），
   但它是该 AC 现网证据的边界，须另立条目把 `HITL`/brief 配置面接上后才能升级为完整证明。
3. **内容时间 15.4 h 不推进是运维线索，不是本条缺陷**。`state_revision` 长时间恒等
   `1754eefc6dca…` 而副本文件持续重写，说明发布器在产出同一 revision。T10-290 的改动恰好把
   这件事从「看不出来」变成「看得清楚」（`payload_age_seconds` 55,712 s 直接可见）。
   判据留此：`content_status` 若长期 STALE，先查 revision 是否变化，再查采集器。

## 6. evidence 位与摘要（收口腿）

| 位 | ref | sha256 |
|----|-----|--------|
| receipt（diff/tests/rollback/live_canary/fresh_receipt/cleanup 共用） | `docs/reports/2026-11-06-t10-290-fib02-projection-time-semantics-closeout.md` | 写入后计算，见台账 |
| retro（operational.replay） | `.omo/_knowledge/retros/BET-Y2Q4-T10-290.md` | 写入后计算，见台账 |
| engineering.merged_reachable_commit | `git://origin/main@3349250e8435c0f175da7eb3d29f01d48c9da036` | — |

`value.status = NOT_PROVEN`（`value_indicator_policy: false`，与同族 281/282/284/288/289 同判）。
