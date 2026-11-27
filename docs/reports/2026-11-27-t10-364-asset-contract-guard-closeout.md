---
schema: md/v1
status: completed
lifecycle: evidence
owner: governance-agent
last-reviewed: 2026-11-27
type: report
bet_id: BET-Y2Q4-T10-364
title: BET-Y2Q4-T10-364 驾驶舱契约守卫覆盖面收口 —— 资产面缺席字段判据 + 宿主部署尝试与回滚
---

# BET-Y2Q4-T10-364 收口回执 —— 驾驶舱契约守卫覆盖面收口

> 合并 SHA: `8b2a7351f660455bd669a8dd8f6d23cb2591a680`（PR #5648，squash）
> 规格: `docs/superpowers/specs/2026-11-27-dashboard-asset-contract-guard.md`（`spec_version 1.0.0`）

## 1. 变更面

| 路径 | 变更 | lane |
|------|------|------|
| `bin/panorama/panorama-collect.py` | 守卫覆盖面从 `template.html` 扩到全部被服务 JS 资产（`_scan_dashboard_asset_contract` + `_dashboard_missing_fields`） | code |
| `bin/panorama/assets/host/panorama-collect-main.py.asset` | 宿主采集器资产镜像同步（与仓内源逐字一致，sha256 `4a11535352a3156f33d6ed573631a2deee4fcd756a19c2de1a73607616bc2679`） | other |
| `bin/panorama/assets/host/workbench_ui.js.asset` | 清掉 `D.pending_publications` 死引用分支（该字段在 T10-354 已退役出 payload） | other |
| `tests/unit/test_panorama_asset_contract_guard.py` | 新增 5 条判据用例（缺席被报出 / 全在场不静默 / null 计入缺席 / 逐资产告警 / 模板面仍报） | code |
| `docs/superpowers/specs/2026-11-27-dashboard-asset-contract-guard.md` | 规格（digest `sha256:dee2dea613c98016737e02899fcba8b1a7ae2788452368249011e7ecf8afb11e`） | docs |
| `docs/plans/3y-bet-ledger.yaml` | 台账条目（本 BET 插入一条；合并后 main 台账共 609 条） | docs_data |
| `.omo/_knowledge/retros/BET-Y2Q4-T10-364.md` | 复盘 | governance_state |
| `docs/reports/2026-11-27-t10-364-asset-contract-guard-closeout.md` | 本回执 | docs |

## 2. 线上实测

采集器 payload **111** 个顶层键（发布器检出 `~/.local/opt/omostation-publisher`，HEAD == origin/main），
被服务面 = 宿主 release `releases/8f43efedc4e04e80e7612a68c6be046f4950c6cb`：

| 消费面 | 读到的 `D.<field>` 数 | 缺席字段 |
|--------|------------------|---------|
| `template.html` | 55 | 无 |
| `data_access.js` | 10 | `safety_boundaries` |
| `ui_extensions.js` | 15 | `events`, `live_sources`, `submodules_summary` |
| `workbench_ui.js` | 16 | `local_server`, `pending_publications`, `safety_boundaries` |

- 资产面 **7 处死读**，分布在 3/11 个被服务资产上；模板面 0 处。
- 其余 8 个资产 refs 为 0 或全部在场。7 处缺席全部是可选链 / 三元写法：不崩，但恒空。
- 同一读数在宿主仓工作树 HEAD（`c2a8471`）重扫后缺席集合完全一致 ⇒ 不是某一版 release 的偶然。
- 本仓侧死引用清零后（`workbench_ui` 去掉 `pending_publications`），剩 **6 处跨仓残留**。

判据（`tests/unit/test_panorama_asset_contract_guard.py`，5 用例）：

```
$ uv run --with pytest --with pytest-timeout --with pyyaml --with "rich<15" \
    python -m pytest tests/unit/test_panorama_asset_contract_guard.py -q
5 passed in 0.10s

$ python3 -c "... count('D.pending_publications') ..."
pending_publications_refs=0
```

### 2.1 扫描根的三种上下文（读数归属，不可混用）

同一份采集器在三种上下文里 `ZHIXING_DASHBOARD_CODE_ROOT` 不同 ⇒ 守卫读数对应不同的面：

| 上下文 | `ZHIXING_DASHBOARD_CODE_ROOT` | 守卫读到的面 | 与被服务面关系 |
|--------|------------------------------|-------------|---------------|
| 发布链（publisher） | 被服务的 release 根 | release 内 `template.html` + 11 个 JS | **= 被服务面** |
| 宿主刷新作业（launchd `com.omostation.panorama-dashboard-refresh`） | `~/.local/share/zhixing-dashboard` | 宿主仓工作树 `template.html` + 11 个 JS | = 发布**源**面，不等于被服务副本 |
| 本轮干跑测量 | release `8f43efed…` | 同第一行 | = 被服务面 |

实测两侧 JS 逐字节相同（`data_access.js` / `ui_extensions.js` sha 一致），但 `template.html` 不同
（宿主仓 `09dcb25bbf76` vs 被服务 `0fd5ce5deff4`）⇒ **运行时告警里的模板面读数不等于浏览器加载的那份模板**；
资产面结论不受影响（JS 两面同字节），模板面结论只有发布链上下文可信。

## 3. 跨仓残留登记（zhixing-dashboard）

以下死读位于宿主仓 `zhixing-dashboard` 的被服务 JS，本轮不改跨仓写面（见规格 non_goals）。
已把每处死读对到采集器 payload 的**确切来源**，使下一轮（跨仓 BET）可照单改：

| 资产:行 | 死读 | payload 实际来源 | 判定 |
|---------|------|----------------|------|
| `data_access.js:34` | `D.safety_boundaries` | `D.agent_visibility.safety_boundaries` | 一行改名可解 |
| `workbench_ui.js:233` | `D.safety_boundaries` | 同上 | 一行改名可解 |
| `ui_extensions.js:175` | `D.submodules_summary.aligned` / `.total` | `D.submodules.synced` / `D.submodules.total` | 一行改名可解（`synced` = 已对齐数） |
| `ui_extensions.js:176` | `D.events`（取 length） | `D.recent_events.events`（或 `D.panel_events.events`） | 一行改名可解 |
| `ui_extensions.js:373` | `D.live_sources?.workflow?.observed_at` | `D.source_states.workflow.observed_at` | 一行改名可解 |
| `ui_extensions.js:210` | `D.live_sources?.catalog` | 已被同句 `D.catalog \|\|` 前置分支覆盖 | 死分支，无害，可删 |
| `ui_extensions.js:235` | `D.live_sources?.workflow?.active_runs` | **无对应键** | 需口径裁定（最近似 `D.swarm.items` / `D.live_agents`，语义不同） |
| `workbench_ui.js:224` | `D.local_server?.status` / `.read_only` | **无对应键** | 宿主自描述面：同一 origin 的 `/health` 端点，或由采集器补 `local_server` 顶层键 |

⇒ 8 处里 5 处一行改名、2 处需口径裁定、1 处（`pending_publications`）本仓镜像已删分支。
处置建议（留宿主仓自行裁决）：① 改 JS 读现有键名；② 或由本仓在 payload 顶层补别名键。前者代价更小。

## 4. 持久性边界（诚实声明）

- 本仓 `bin/panorama/assets/host/workbench_ui.js.asset` 是**宿主发布面副本**，不是宿主仓源。
  宿主仓 HEAD 的同名文件仍带 `pending_publications` 死分支 ⇒ 宿主仓下一次发布会把该分支带回，
  本仓镜像里的清理只对「宿主资产平面」这一条发布路径持久。
- 守卫扩展（采集器）落在本仓 + 宿主资产镜像，随宿主资产平面发布持久；但宿主仓若从上游
  覆盖 `panorama-collect-main.py`，同样的覆盖风险存在。⇒ 两处都需要在宿主仓侧同步一次。
- 本 BET 的守卫与清理**尚未落到宿主运行面**（原因见 §5），当前宿主仍在跑旧采集器（仅模板面守卫）
  与旧 `workbench_ui.js`（仍带 1 处 `pending_publications`）。

## 5. 宿主部署尝试与回滚

### 5.1 部署前读数

| 读数 | 值 |
|------|-----|
| `current` 指向 | `releases/8f43efedc4e04e80e7612a68c6be046f4950c6cb` |
| `current/panorama-collect-main.py` sha256 | `45046a1ad942f044…`（无资产面守卫） |
| `current/workbench_ui.js` 内 `pending_publications` 计数 | 1 |
| `/health` | 200 |
| 刷新作业节奏 | 每 240 s 发布一个 revision |

### 5.2 部署动作

从 `origin/main` 对齐的检出（HEAD == `8b2a7351`，`assets/host` 干净）执行：

```
python3 bin/gac/zhixing-host-sync.py publish --file workbench_ui.js --file panorama-collect-main.py
```

结果 `ok: true`，新建 `releases/8b2a7351f660455bd669a8dd8f6d23cb2591a680` 并原子切换 `current`；
两份资产 `source_sha == runtime_sha`（`c88c7f8f2bc16b6c` / `4a11535352a3156f`）。

### 5.3 部署后失败：投影生产者身份绑定

刷新作业（launchd `com.omostation.panorama-dashboard-refresh`，每 240 s）随即失败：

```
File ".../current/panorama-collect-main.py", line 519, in collect_projection_producer_identity
    raise RuntimeError("projection_collector_not_at_bound_commit")
```

根因（`panorama-collect.py:505-519`）：采集器自校验「正在执行的采集器字节 == 生产者代码根 HEAD 上的
`bin/panorama/panorama-collect.py` 字节」。宿主生产者代码根是
`~/.local/share/zhixing-dashboard/code-main`（HEAD `92183b49`），其采集器 sha = `45046a1a…`；
而本次发布的是 `8b2a7351` 的新版采集器（`4a115353…`）⇒ 字节不等 ⇒ 采集器**主动拒绝运行**。

连锁后果：刷新作业不再发布 revision ⇒ live server 投影过期 ⇒ `/health` 报
`code_drift: true` / `projection_status: CODE_DRIFT` ⇒ 全部路由（含静态 JS）返回
503 `{"error":"projection_code_drift","read_only":true}`。

**这不是新缺陷，是发布顺序约束**：`code-main` 由 `bin/ssot/anchor-install-root.sh` 推进，
本机安装位与 `code-main` 都锚在 `92183b49`（origin/main 的祖先），落后 main ⇒
「用比 code-main 更新的提交发布采集器」必然触发该自校验。

### 5.4 回滚与宿主复原

```
python3 bin/gac/zhixing-host-sync.py restore        # current 切回 8f43efed
launchctl kickstart -k gui/$(id -u)/com.omostation.zhixing-dashboard
launchctl kickstart -k gui/$(id -u)/com.omostation.panorama-dashboard-refresh
```

复原后读数：

| 读数 | 值 |
|------|-----|
| `current` 指向 | `releases/8f43efedc4e04e80e7612a68c6be046f4950c6cb`（发布器原版） |
| `/health` | `code_drift: false`，`projection_status: BOUND_FRESH`，`dashboard_code_oid: 8f43efed…` |
| 静态资源 | `GET /workbench_ui.js` → 200，244571 bytes（发布器原版，含 1 处 `pending_publications`） |
| 刷新作业 | 04:03:38 恢复发布 revision `ef429c90…`，此后按 240 s 节奏继续 |

### 5.5 本次尝试留下的足迹已清除

| 足迹 | 处置 | 复核 |
|------|------|------|
| `releases/8b2a7351…`（本次新建，含绑定不通过的采集器） | 已删除（本次会话自建产物，无引用） | 目录不存在 |
| `releases/.current-history.json` 的 `previous_version` | 复原为部署前值 `4ac84471…`（原指向被回滚掉的 `8b2a7351…`，会让下一次 `restore` 切到坏版本） | 已复原 |
| `current` 软链 | 指向 `8f43efed…` | 已复核 |
| 刷新日志中的 2 行 `projection_collector_not_at_bound_commit` | 保留（日志是历史证据，不改写） | — |

### 5.6 上宿主的两步（留待 principal / 运行时重锚窗口）

```bash
# ① 先把运行时安装位与 code-main 重锚到含本改动的提交（机器级：安装位 + code-main + 子模块 + omo venv）
bash bin/ssot/anchor-install-root.sh origin/main
# ② 再从同一提交发布两份资产
python3 bin/gac/zhixing-host-sync.py publish --file workbench_ui.js --file panorama-collect-main.py
launchctl kickstart -k gui/$(id -u)/com.omostation.zhixing-dashboard
launchctl kickstart -k gui/$(id -u)/com.omostation.panorama-dashboard-refresh
```

步骤 ① 是机器级运行时变更（影响所有常驻族看到的代码），超出本 BET 的写面，未执行。
步骤 ② 单独执行会重现 §5.3 的失败。

## 6. 结论

- done_when 四条全部达成（仓库面）：守卫覆盖 11 个被服务资产并逐资产报出缺席字段；
  `workbench_ui.js.asset` 的 `D.pending_publications` 计数 = 0；宿主资产镜像与源逐字一致；
  跨仓残留 6 处已登记且各自对到 payload 确切来源；判据 5 条正反用例通过。
- 宿主运行面**尚未**拿到本次改动，卡在「运行时重锚」这一个前置条件上（§5.6），
  且该前置条件此前无人写进发布面的书面契约 —— 本回执把它显式化。
