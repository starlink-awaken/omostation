---
schema: md/v1
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-10-19
type: ssot
id: ADR-0466
related:
  - ./0456-dev-runtime-profile-root.md
tags: [authenticity, zero-mock, test-isolation, honesty, resident-agent, governance]
---

# ADR-0466 — 全系统真实性契约与零 Mock 治理规范

- **Status**: ACCEPTED（经夏明星 2026-10-19 审议决断生效）
- **Date**: 2026-10-19
- **Owner**: governance-team

---

## 1. 背景与问题定义 (Context)

在 2026-10-19 全系统真实性地毯式审查中，查明了长久积累的一系列严重失真与暗病：
1. **伪造执行结果**：`worker.py` 在找不到工作树时硬编码写入假 Diff（`1 file changed, 14 insertions...`）与假跑测通过数据，并强行标记为 `ready_for_review`，欺骗用户签名；
2. **测试反噬生产环境**：常驻单元测试（`test_resident_*.py`）未做环境隔离，直接向宿主真实目录 `~/.local/share/omostation/cards/` 倾倒了 79 张假卡片，并向主仓 `.omo/_truth/task-center/dispatches/` 写入了 83 个测试假任务；
3. **展示层虚假美容**：SwiftBar 菜单栏在未取到数据时，输出写死的美观文本（`39G/128G`、`690ms`、`24h 稳定`），切断了系统的物理痛觉神经，掩盖了机器 102.5G 内存重负与网络超时降级；
4. **探活与观察面泥潭**：`applenotes` 连接器遍历 22 个文件夹串行执行 23 次 `osascript` 子进程，耗时长达 150 秒，超出预算被强杀，致使 Launchd 观察面周期性报 exit 1。

为了彻底维护人机信任与系统健壮性，特制定本 ADR 作为全仓强制遵守的最高治理法条。

---

## 2. 治理决策与法条 (Decisions)

### 法条 1：零假数据与诚实执行契约（No Cosmetic Mocks）
- **严禁伪造执行**：任何 Worker、Agent 或自动修复流水线，在依赖缺失、环境未就绪或未产生真实变更时，必须忠实返回 `worktree_missing`、`no_changes_detected` 或显式失败；严禁伪造 git diff、单测通过日志或虚拟工件向 Action Desk 推送待审批卡片。
- **签名保护底线**：呈递给人类署名批准的每一项变更，必须具备可审计的物理 Git 提交或工作树 Diff。伪造签名依据视作最高级故障。

### 法条 2：单测零公害与全沙箱隔离（Zero Production Pollution Assertion）
- **严禁向生产物理目录写数据**：常驻测试及所有单元测试严禁向宿主实际生产路径（如 `~/.local/share/omostation/`）或主仓数据面（`.omo/_truth/task-center/`）写入任何持久化文件。
- **强制多重沙箱重定向**：测试环境必须由 `conftest.py` 统一拦截并注入 `OMO_CARDS_DIR`、`OMO_PATROL_DIR`、`OMO_ALERTS_DIR` 与 `OMOSTATION_STATE_ROOT` 指向 `tmp_path`。
- **会话收尾硬阻断**：测试套件在 `pytest_sessionfinish` 时必须核验宿主生产目录与主仓目录的文件增量；若有泄漏，测试套件直接判定为 **FAIL** 并阻断提交。

### 法条 3：诚实暴露与物理痛觉穿透（Honest Degradation & Zero Cosmetic Masking）
- **绝不使用美容兜底**：SwiftBar 菜单栏、Web 驾驶舱及各类仪表盘，在底层数据缺失或网络探测失败时，必须真实显示原始状态（如 `102.5G 内存`、`1330ms 变慢`、`探测超时(已降级)`）；严禁使用写死的“健康文本”掩盖异常。
- **分级告警机制**：
  - 物理性能抖动、临时网络降级：在 SwiftBar / 驾驶舱如实以黄/红标呈现，保持痛觉神经通畅，但不骚扰用户；
  - 守护进程心跳停摆、系统性崩溃或需要人工介入决策：方可向 Action Desk 推送核心告警卡片。

### 法条 4：探活与采集禁止 O(N) 进程循环（Subprocess O(1) Constraint）
- **禁止在探活中循环拉起外部进程**：凡涉及 `osascript`、`curl`、`ssh` 等外部系统调用的采集逻辑，严禁使用循环方式逐项调用；必须汇聚为单次单指令批量查询（如 AppleScript 的 `count of notes`）。
- **硬性超时预算**：单次本地探活超时必须严格限制在 `≤ 5s` 内，全量观察面单项收集必须限制在 `≤ 45s` 内，坚决防止局部卡死拖垮全局守护链路。

---

## 3. 防反弹防御体系 (Enforcement & Verification)

本 ADR 通过**三层立体防线**实现自动化硬拦截：

1. **第一道防线（测试即时断言）**：`projects/omo/tests/conftest.py` 注入全局物理目录指纹检查，只要发生宿主目录文件净增，单测自动报红阻断；
2. **第二道防线（治理门禁）**：`bin/gac/check-test-host-hygiene.py` 纳入门禁流水线，扫描主仓与宿主目录，阻断测试假任务；
3. **第三道防线（周期守护巡检）**：Launchd 与常驻守护进程巡检关键目录，对历史归档执行 7 天生命周期管理。

---

## 4. 历史遗留数据生命周期 (Data Retention)

- **当前归档**：本次清理的 79 张假卡片（`~/.local/share/omostation/cards_archive/`）与 83 个假任务（`.omo/tasks/archived/dispatches_test_archive/`）设立 7 天保留期（至 2026-10-26）；
- **物理销毁**：到期后由清理工具彻底物理销毁（`rm -rf`），不留任何历史垃圾。
