---
schema: md/v1
schema_version: specification/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-11-22
accepted: "2026-11-22 Principal 授权连续处置（「你处理吧」）— 同一阻塞链上的存量检查器假阳性, 与 BET-Y2Q4-T10-348 连续落地"
bet_id: BET-Y2Q4-T10-349
spec_version: 1.0.0
---

# gen-service-configs --check plist drift 假阳性修复 — 注释非配置语义

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-349`

## 目标

`bin/mof/gen-service-configs.py --check` 在本机 plist 与 services.yaml 生成版
**仅存在 XML 注释差异**时必须报 0 drift；实质字段差异仍如实报 drift。

## 根因（2026-11-22 实测证据, 两层）

**第一层 · 对比层假阳性**：check 判定对本机文件与 `gen_launchd_plist()` 现场生成版
做**逐文本对比**。2026-11-10 模板 `bin/ops/launchd/*.plist` 手工补了解释器 NOTE
文档（python3 → .venv/bin/python 的 3.9.6 ImportError 硬伤记录）并整份覆盖本机 ——
这是 LAUNCHD-PLIST-INSTALLED-DIVERGED 的正确处置；而生成器从不产注释, 本机另有
紧凑排版 —— 注释/排版差异被误报为 drift。

**第二层 · 声明层真漂移**：11-10 手工修复新增的 `WorkingDirectory` /
`EnvironmentVariables`(PATH + no_proxy 防 ClashX 代理超时) / `StartCalendarInterval`
(每小时 :05/:35) 未回填 services.yaml, 生成器也不支持渲染 —— plistlib 语义对比下
依然不等, 属真漂移（初判"仅剩 <!-- / --> 定界符差异"系过滤脚本口径错误, 已修正）。

影响面：自 11-10 起阻塞一切本机 gac-local-gate 全绿与 workflow closeout
（含 BET-Y2Q4-T10-348 的 closeout 链）。

## 修复方案

- `gen-service-configs.py`：`--check` 改用 **plistlib 语义等价判定**
  （解析后深比较, 注释/排版自然忽略; malformed 回退剥注释文本对比, 保守判 drift）；
  `--write` 生成行为不变。
- 生成器补 `working_directory` 渲染与 `calendar: list[dict]` 多时刻支持；单 dict
  声明保持单 dict 渲染（与本机存量/launchd 等价形态一致, 避免 dict≠[dict] 新假 drift）。
- `services.yaml` 的 omostation.omo-debt-refresh 条目回填三字段, SSOT 与 11-10
  手工修复对齐（worktree 分支变更镜像主仓工作区未提交副本, PR 合并后收敛）。
- `tests/test_gen_service_configs.py` 新增 4 用例：仅注释差异等价 / 紧凑排版等价 /
  实质字段差异仍报 / working_directory+calendar-list 渲染。

## 验证

- `uv run --with pyyaml python -m pytest tests/test_gen_service_configs.py -q`
- `uv run --with pyyaml python bin/mof/gen-service-configs.py --check` — 本机
  现状（仅注释漂移）exit 0。

## 回滚

`git revert` 单文件还原；无状态写入、无接口变更。

## 非目标

- 不改 gen_launchd_plist 生成行为（不产注释保持现状）。
- 不删 bin/ops/launchd/*.plist 模板注释（11-10 NOTE 文档保留）。
- 不处理 --write 安装路径与本机 plist 同步（部署侧另案）。
