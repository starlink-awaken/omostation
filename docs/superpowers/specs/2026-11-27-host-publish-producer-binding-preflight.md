---
schema: md/v1
schema_version: specification/v1
bet_id: BET-Y2Q4-T10-365
spec_version: 1.0.0
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-11-27
accepted: "2026-11-27 governance-agent 会话延续轮 —— BET-Y2Q4-T10-364 回执 §5 登记的发布面自伤 (发布字节未绑定生产者代码根)"
title: 宿主发布前置条件机器化 —— 发布采集器前先验生产者字节绑定
created: 2026-11-27
---

# BET-Y2Q4-T10-365: 宿主发布前置条件机器化

## 背景与问题

`BET-Y2Q4-T10-364` 把驾驶舱契约守卫覆盖面扩到全部被服务 JS 资产, 随后尝试把该
改动**部署到宿主**。发布本身成功 (`publish` 返回 `ok: true`, 两份资产 sha 与源一致),
但刷新作业随即失败:

```
RuntimeError: projection_collector_not_at_bound_commit
```

⇒ 投影不再刷新 ⇒ live server `CODE_DRIFT` ⇒ **静态资源 503**
(`{"error":"projection_code_drift","read_only":true}`) ⇒ 驾驶舱整站不可用。
本 BET 收口时已 `restore` 回滚, 宿主复原 (`code_drift=false` / `BOUND_FRESH` / 静态 200)。

**根因是半边契约**: 采集器自带身份自校验
(`bin/panorama/panorama-collect.py:473` `collect_projection_producer_identity()`)
要求「**正在执行的字节** == `PANORAMA_CODE_ROOT` HEAD 上的
`bin/panorama/panorama-collect.py`」, 不等即抛错**主动拒绝运行**; 而发布器
(`bin/gac/zhixing-host-sync.py` `publish()`) 只校验「**发布的字节** == 仓库资产字节」。
两边都不完整: 发布器不检查生产者绑定 ⇒ 允许发布一份**必然让采集器拒绝运行**的字节。

契约里的这条前置条件**从未被写进任何文档或检查**, 只存在于采集器的自校验里。

## 方案

在发布器的「准备版本目录之后、原子切换 `current` 之前」插入**生产者绑定前置检查**:

1. **解析生产者代码根** (三级回退, 顺序固定):
   1. refresh 作业 plist 的 `PANORAMA_CODE_ROOT`
      (`~/Library/LaunchAgents/com.omostation.panorama-dashboard-refresh.plist`)
      —— 运行采集器的真实上下文;
   2. 进程环境 `PANORAMA_CODE_ROOT`;
   3. 默认 `~/.local/share/zhixing-dashboard/code-main`。
2. **取绑定字节**: `git -C <producer_root> show HEAD:bin/panorama/panorama-collect.py`。
3. **取待发布字节**: 新版本目录内的 `panorama-collect-main.py`
   (即宿主 refresh 作业实际执行的 `current/panorama-collect-main.py`)。
4. **判定**:
   - 两侧 sha256 **相等** ⇒ 绑定成立, 放行;
   - **不等** ⇒ **拒绝发布**: 不切换 `current`, 丢弃本次新建版本目录, 返回
     `ok: false` / `reason: producer_binding_unsatisfied`, `detail` 给出两侧 sha256
     与处置顺序「**先重锚 code-main, 再发布资产**」;
   - 生产者根**不可用 / 非 git 仓 / HEAD 无该路径** ⇒ 判定**不可验证**, **跳过**
     检查 (不阻断), 在返回值里标注 `producer_binding_unverifiable` 与原因 ——
     无法自证时不得反手阻断发布 (采集器自身在这些情形下同样无法自证)。

检查读的是**新版本目录里的实际字节**, 因此对「只发布部分资产」(例如只发
`workbench_ui.js`) 同样成立: 未被本次覆盖的采集器从当前 release 复制而来, 仍要过
同一条绑定。

## 验收

| 项 | 判据 |
|----|------|
| 绑定成立时放行 | 单测: 两侧字节相同 ⇒ 检查通过 |
| 绑定不成立时拒绝 | 单测: 字节不同 ⇒ `ok=false` + `reason=producer_binding_unsatisfied`, 且 `current` 未被切换 |
| 不可验证时不阻断 | 单测: 生产者根缺失 / 非 git 仓 ⇒ 跳过并标注, 不报错 |
| 发布面不回归 | `tests/unit/test_zhixing_release_identity.py` 全绿 |
| 判据自证 | 新单测跑通 (`tests/unit/test_zhixing_publish_producer_binding.py`) |

## 非目标

- 不改采集器的身份自校验语义 (它是正确的, 是发布器缺了另一半)。
- 不动 `code-main` 的重锚 (`bin/ssot/anchor-install-root.sh` 属机器级运行时变更,
  属 principal 窗口)。
- 不改宿主发布面「只告警不阻断」的其他既有语义 (本检查是发布器内部的**前置拒绝**,
  不改变驾驶舱契约守卫的告警语义)。

## 影响面

- `bin/gac/zhixing-host-sync.py` (+ 前置检查函数与 `publish()` 接线)
- `tests/unit/test_zhixing_publish_producer_binding.py` (新)
- `docs/plans/3y-bet-ledger.yaml` (台账条目)
- `docs/superpowers/specs/2026-11-27-host-publish-producer-binding-preflight.md` (本规格)
- `.omo/_knowledge/retros/BET-Y2Q4-T10-365.md` (复盘)
- `docs/reports/2026-11-27-t10-365-publish-producer-binding-closeout.md` (收口回执)
