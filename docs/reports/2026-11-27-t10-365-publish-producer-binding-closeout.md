---
schema: md/v1
type: report
status: completed
lifecycle: evidence
owner: governance-agent
last-reviewed: 2026-11-27
bet_id: BET-Y2Q4-T10-365
---

# BET-Y2Q4-T10-365 收口回执 —— 宿主发布前置条件机器化

> 事实以实测读数为准, 不填占位。宿主面未变更 (本 BET 只改发布器, 不部署)。

## 0. 交付坐标

| 项 | 值 |
|----|----|
| PR | [#5650](https://github.com/starlink-awaken/omostation/pull/5650) (squash merged) |
| merge SHA | `e85525788d4f0480b923ce26a68f1d6ea22eea09` (`git://origin/main@e8552578…`, 已验 `merge-base --is-ancestor` 可达) |
| 规格 | `docs/superpowers/specs/2026-11-27-host-publish-producer-binding-preflight.md` (`spec_version 1.0.0`, digest `sha256:81e4bee11ccd8dadd0d53a18a966c72f5b7a8d9d345d0fa9471fa6567ff1c10e`) |
| CI | PR #5650 全部 18 个 job 绿 (含 `governance-verify` / `interface-check` / `integration (3.13)` / `evidence-gate` / `bet-done-transition`) |

## 1. 变更面

| 路径 | 变更 | lane |
|------|------|------|
| `bin/gac/zhixing-host-sync.py` | 新增生产者字节绑定前置检查 (`check_producer_binding` + `_producer_code_root` + `_bound_producer_collector`), `publish()` 在切换 `current` 之前调用 | governance_code |
| `tests/unit/test_zhixing_publish_producer_binding.py` | 新增 9 条判据用例 (绑定成立放行 / 绑定不成立拒绝且 `current` 未被切换 / 生产者根缺失跳过 / 非 git 仓跳过 / 无采集器跳过 / 根解析优先级) | code |
| `docs/superpowers/specs/2026-11-27-host-publish-producer-binding-preflight.md` | 规格 (spec_version 1.0.0, digest `sha256:81e4bee11ccd8dadd0d53a18a966c72f5b7a8d9d345d0fa9471fa6567ff1c10e`) | docs |
| `docs/plans/3y-bet-ledger.yaml` | 台账条目 (本 BET 插入一条) | docs_data |
| `.omo/_knowledge/retros/BET-Y2Q4-T10-365.md` | 复盘 | governance_state |

## 2. 实测读数

### 2.1 绑定检查在真实发布面上的读数

判据: 新版本目录内的 `panorama-collect-main.py` 字节 vs 生产者代码根
(`PANORAMA_CODE_ROOT` = `~/.local/share/zhixing-dashboard/code-main`) HEAD 上的
`bin/panorama/panorama-collect.py` 字节。

| 待发布字节 | 判定 | release sha256 | 绑定 sha256 |
|-----------|------|----------------|------------|
| 线上 `current` 的采集器 (release `8f43efed…`) | `producer_binding_satisfied` | `45046a1a…` | `45046a1a…` |
| 仓库 asset `bin/panorama/assets/host/panorama-collect-main.py.asset` (T10-364 采集器) | `producer_binding_unsatisfied` | `4a115353…` | `45046a1a…` |

第二行**就是 T10-364 那次自伤的条件**: 采集器资产 `4a115353` 与生产者绑定 `45046a1a`
不一致 ⇒ 采集器必然抛 `projection_collector_not_at_bound_commit` 拒绝运行 ⇒
投影停更 ⇒ 静态资源 503。本检查在切换 `current` 之前把它挡下, 且失败时宿主零扰动
(只丢弃本次新建版本目录, `current` 不动)。

生产者在位读数: `code-main` HEAD = `92183b493e010f3ec8fd30ce5e2b22b84d37f955`
(origin/main 的祖先); 线上 `current` 采集器 sha256 = `45046a1ad942f04490b7b688d94c379d560ad20824cdb0ca1882f35fd034f83a`。

### 2.2 三态判定

| 情形 | 判定 | 动作 |
|------|------|------|
| 两侧字节相等 | `producer_binding_satisfied` | 放行 |
| 两侧字节不等 | `producer_binding_unsatisfied` | **拒绝发布** (`current` 不切换, 新建目录丢弃), `detail` 给出「先重锚 code-main, 再发布资产」 |
| 生产者根缺失 / 非 git 仓 / HEAD 无该路径 | `producer_binding_unverifiable` / `producer_root_unavailable` | **跳过, 不阻断** —— 无法自证时不反手阻断发布 |
| 新版本目录内无采集器 | `collector_absent_in_release` | 跳过, 不阻断 |

生产者根解析优先级 (有单测钉住): refresh 作业 plist 的 `PANORAMA_CODE_ROOT`
(`~/Library/LaunchAgents/com.omostation.panorama-dashboard-refresh.plist`)
> 进程环境 `PANORAMA_CODE_ROOT` > 默认 `~/.local/share/zhixing-dashboard/code-main`。

## 3. 判据

```
$ uv run --with pytest --with pytest-timeout --with pyyaml --with "rich<15" \
    python -m pytest tests/unit/test_zhixing_publish_producer_binding.py -q
9 passed in 1.12s

$ uv run --with pytest --with pytest-timeout --with pyyaml --with "rich<15" \
    python -m pytest tests/unit/test_zhixing_release_identity.py \
    tests/unit/test_zhixing_external_root_contract.py -q
67 passed in 13.23s

$ python3 bin/plan/bet-ledger.py lint
1 个问题   ← 预存: BET-Y2Q4-T10-360 缺字段 done_when (他人条目, 本 PR 未触碰)
```

核心用例走**真实 `publish()` 入口**: 绑定不成立时返回 `ok=false` +
`reason=producer_binding_unsatisfied`, 且 `CURRENT_LINK` 指向的版本目录不变、
`_switch_state_snapshot()` 前后一致、`releases/` 下没有残留新建目录。

## 4. 持久性边界（诚实声明）

- 本 BET 只改**发布器** (`bin/gac/zhixing-host-sync.py`, 在本仓) —— 宿主上跑的是
  `current/panorama-collect-main.py` (采集器), 发布器本身在仓内由人执行,
  因此本检查从本 PR 合入起对**每一次发布**生效, 不依赖宿主部署。
- 检查的**另一半** (重锚 `code-main`) 仍属机器级运行时变更, 本 BET 未执行 ⇒
  **宿主尚未拿到 T10-364 的采集器**; 上宿主仍需「先重锚, 再发布资产」两步。
- 发布器拒绝时**宿主零扰动**: 只丢弃本次新建的版本目录, `current` 不切换,
  刷新作业与 live server 不受影响 (与 T10-364 那次「发布成功 → 503 → 手工
  restore + 两次 kickstart」相比, 失败面从「服务不可用」缩到「发布未发生」)。

## 5. 宿主面现状（未变更）

- 线上 `current` = release `8f43efed…`; `/health` 读数 `code_drift=false` /
  `projection_status=BOUND_FRESH`; 静态资源 200; 投影按 240 s 周期持续发布。
- 本 BET **不部署任何资产**, 故宿主面与 BET-Y2Q4-T10-364 收口时一致。

## 6. 结论

T10-364 回执登记的「发布面前置条件未写进契约」这条债, 已从**文档层**下沉到
**机器判据**: 发布器现在会拒绝发布一份必然让采集器拒绝运行的字节, 并给出处置顺序。
判据在真实发布面上复现了缺陷面 (线上当前字节满足绑定; 仓库新 asset 不满足,
且该不满足正是上一轮自伤的成因)。
