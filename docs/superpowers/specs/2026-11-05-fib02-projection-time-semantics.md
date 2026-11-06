---
schema_version: specification/v1
spec_version: 1.0.0
title: FIB-02 投影租约、内容与复制时间分开展示
bet_id: BET-Y2Q4-T10-290
owner: governance-agent
status: accepted
lifecycle: contract
last-reviewed: 2026-11-05
---

# FIB-02 投影租约、内容与复制时间分开展示

## 准入状态

本文件是仓外待登记的 accepted-spec 字节草稿。用户已批准产品意图；本文件和建议 BET ID 尚未进入正式台账，不赋予任何写产品代码的权限。仅在用户明确批准一次性登记豁免后，才将相同字节复制到隔离 Workspace worktree 的本路径并经原登记器登记。登记成功或失败，豁免立即终止；代码编辑继续要求正常 bootstrap、start bet-execution --profile engineering-agent --bet、claim。

## 用户结果与边界

在 Panorama 的状态展示中分开回答：投影服务租约是否有效、绑定内容最后观测于何时、当前文件副本何时复制/读到。租约续期不能把旧内容显示成新鲜，文件副本时间不能冒充数据观测时间。保留现有内容新鲜度 300 秒 TTL、投影绑定和 fail-closed 行为；不发布、部署、启停服务或修改生产产物。

## KOS 先例

2026-11-05 已经 KOS search_knowledge 检索 HawkUI（0 项）与 data_observed_at（3 项但片段未证明本改动）；宽检索命中 kos::default::BET-Y1Q4-T8-24A.md（Observatory 统一数据面收敛与增量流式投影服务历史复盘）。其可见片段只证明既有投影背景，不证明当前运行行为。当前权威代码与本仓 BET-Y2Q4-T10-223/227 的历史契约明确区分续租与数据刷新，本项复用该边界，不新增 publisher、dispatcher、ledger 或 gateway。

## 写面

实施文件严格限于：

- `bin/panorama/assets/host/live_server.py.asset`
- `bin/panorama/assets/host/template.html`
- `tests/unit/test_live_server_payload_freshness.py`
- `tests/unit/test_dashboard_panel_assets.py`
- `tests/unit/test_live_server_time_semantics.py`（新增；独立时间语义/API边界夹具）

治理登记只新增本 spec 与 `BET-Y2Q4-T10-290` 条目；不改变任何其他 BET 的状态或证据。绝对路径映射另见 execution-scope.json；代码与模板始终在独立 worktree 修改，不在共享主树写产品代码。

## 验收条件

1. 后端返回独立、具有来源语义的租约时间、内容观测时间与可用副本时间。字段缺失、解析失败、未来时钟等情况明确显示 UNKNOWN/不可判，不用 now 或 0 伪造观测。
2. 内容新鲜度以绑定内容中的既有可信时间判定，300 秒 TTL 的数值及边界行为不变；租约 fresh_until 的更新不能覆盖该时间。
3. 副本时间只作为复制/文件观察时间展示，必须标注来源；不得据此恢复旧内容健康状态。
4. 页面分别显示这些时间及状态；原有 revision_id、manifest/code/bundle 摘要可见且不被新时间字段替换或缩短到不可核验。
5. 既有 CODE_DRIFT、过期租约、损坏 artifact、未知内容时间等状态保持 fail-closed；不通过 fallback 新文件把旧或损坏 revision 洗绿。
6. 定向测试覆盖新租约+旧内容、新副本+旧内容、缺失/非法时间、现有 300 秒边界，以及 revision 摘要保留；既有 HTTP/SSE freshness 测试通过。
7. 结果分清静态/夹具测试与实际部署；本项无生产部署证据时明确 operational NOT_PROVEN，不声明现网已生效。

## 非目标与中止条件

不更改 TTL、revision 生成/摘要算法、读端身份验证、生产 manifest、republisher、调度、services.yaml、external-write-roots 或任何其他 BET。不得启动/重启服务、部署、commit、push 或派出未获授权的 Multica 写任务。缺有效 BET、run、范围 claim 或导入根/状态根不明时停止编辑并报告；保留其他会话文件与锁，不接管。

## 验证与恢复

在获准且正确隔离的 Workspace worktree 运行 `/Users/xiamingxing/Workspace/.venv/bin/python -m pytest tests/unit/test_live_server_payload_freshness.py tests/unit/test_live_server_time_semantics.py tests/unit/test_dashboard_panel_assets.py -q`，并检查差异只覆盖本写面。测试命令通过不等于部署通过。回滚只撤回本次工作差异，禁止 reset/clean 共享树。新增依赖或扩大写面需先修订本契约与 claim。
