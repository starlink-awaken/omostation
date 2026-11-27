---
schema: md/v1
schema_version: specification/v1
bet_id: BET-Y2Q4-T10-364
spec_version: 1.0.0
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-11-27
accepted: "2026-11-27 governance-agent 会话「继续优化」延续轮 —— BET-Y2Q4-T10-354 收口回执中登记的发布面残留 (守卫覆盖面止于 template.html)"
title: 驾驶舱契约守卫覆盖面收口 —— 从 template.html 扩到全部被服务的 JS 资产
created: 2026-11-27
---

# BET-Y2Q4-T10-364: 驾驶舱契约守卫覆盖面收口

## 背景与问题

`BET-Y2Q4-T10-354` 把驾驶舱模板声明的 7 个退役字段收口 (模板引用清零 /
守卫 dry-run missing 7 → 0 / 发布面 in_sync)。该 BET 的收口回执
(`docs/reports/2026-11-27-t10-354-publish-closeout.md`) 同时登记了**残留面**:

发布器自带的契约守卫 `_check_template_data_consistency`
(`bin/panorama/panorama-collect.py:5703`) **只扫 `template.html` 一个文件**,
而被服务的前端资产是 **11 个 JS 文件** (`data_access.js` / `ecosystem_ui.js` /
`mof_ui.js` / `next_ui.js` / `panoramic_ui.js` / `strategy_ui.js` / `sw.js` /
`topology_ui.js` / `ui_extensions.js` / `v6_tab_code.js` / `workbench_ui.js`)。
模板之外, 资产读 `D.<field>` 的缺席字段**没有任何判据覆盖** ——
这正是 T10-354 那类缺陷 (页面渲染为空 / NaN) 的复发入口。

实测读数 (2026-11-27, 线上 release + 线上已发布 payload 114 顶层键):

| 面 | refs | missing | 说明 |
|----|------|---------|------|
| 被服务的 `template.html` | 55 | **0** | 发布链用的是 release 面模板, 已干净 |
| `data_access.js` | 10 | **1** | `safety_boundaries` |
| `ui_extensions.js` | 15 | **3** | `events` / `live_sources` / `submodules_summary` |
| `workbench_ui.js` | 16 | **3** | `local_server` / `pending_publications` / `safety_boundaries` |

其余 8 个资产 refs 数为 0 或全部在场。7 处缺席全部是**可选链 / 三元**写法
(不崩但恒空) —— 与 T10-354 同类。

## 方案

1. **守卫覆盖面**: `_check_template_data_consistency` 扩到「模板 + 全部被服务的
   JS 资产」—— 在同一 code root 下逐个 `*.js` 报告 `D.<field>` 在 payload 里
   缺席的字段; 保持**只告警不阻断**的既有语义 (发布是只读聚合面, 阻断会改
   发布行为, 超出本 BET 授权)。守卫的扫描根仍由 `ZHIXING_DASHBOARD_CODE_ROOT`
   决定 —— 发布链注入的正是被服务的 release 根, 因此扫描面 = 被管面。
2. **host 资产镜像**: 宿主跑的是 `bin/panorama/assets/host/panorama-collect-main.py.asset`
   (由 `bin/gac/zhixing-host-sync.py` 的 `HOST_FILES` 发布到宿主)。守卫扩展必须
   同步进该 asset 副本, 否则部署时会把宿主回退成旧守卫。
3. **omostation 侧死引用清零**: `workbench_ui.js.asset` 里 `D.pending_publications`
   分支删除 —— 该字段已在 T10-354 从 payload 退役 (线上 114 键无此项), UI 不得
   声明 payload 撑不起的能力。
4. **跨仓残留登记**: `zhixing-dashboard` 的 `ui_extensions.js` / `data_access.js`
   不在本仓写面内, 本轮只登记 (回执 + 守卫告警), 不改该仓。

## 验收

| done_when | 判据 |
|-----------|------|
| 守卫覆盖面扩到全部被服务 JS 资产 | 干跑守卫逐资产报出缺席字段 (3 资产 / 7 字段) |
| omostation 侧死引用清零 | `workbench_ui.js.asset` 中 `D.pending_publications` 计数 = 0 |
| host 资产镜像同步 | `panorama-collect-main.py.asset` 与 `panorama-collect.py` 逐字节一致 |
| 跨仓残留有登记 | 回执记录 `ui_extensions.js` / `data_access.js` 的缺席字段与线上 payload 读数 |
| 判据有正反用例 | 新增单测: 缺席字段被报出 / 全部在场时不报 / 模板面不回归 |

## 非目标

- 不改发布语义 (不把告警变成阻断) —— 阻断口径属判据接线变更, 留 principal;
- 不改 `zhixing-dashboard` 仓任何文件 (跨仓写面);
- 不动 `~/.local/share/zhixing-dashboard/` 宿主根的模板副本 (refs 62 / missing 7,
  属 T10-354 non_goals);
- 不执行宿主部署面写入 (`zhixing-host-sync publish` + `launchctl kickstart`
  进程重启) —— 部署面属 principal 授权, 本 BET 只把变更落到仓内 asset 源;
- 不改治理占比判据面 (`GOVERNANCE_CEILING` / `_classify`)。
