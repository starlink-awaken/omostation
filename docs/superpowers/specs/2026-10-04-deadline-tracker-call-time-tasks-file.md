---
schema_version: specification/v1
spec_version: 1.0.0
title: Deadline Tracker Resolves Its Tasks File at Call Time (ADR-0456 B4b precondition)
bet_id: BET-Y2Q4-T10-229
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-04
adr: ADR-0456
---

# ADR-0456 B4b 前置 — 督办台账路径在调用时刻解析

> 契约正文只写不变量。所有数字为撰写时点（2026-10-04T15:18Z）在隔离 worktree
> `~/ws-t10-226-test-order-pollution` 上的一次实测，用于说明前提，不构成判据。
> 引用所在 ADR 必须写文件名 `.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md`
> （`ADR-0456` 标识冲突：同 id 另有 `ADR-0456-governance-downshift-closeout-grading.md`）。

## 1. 缺陷形状（不是用例写错）

`bin/ssot/deadline_tracker.py:31` 把沙箱重定向变量求值成**模块级常量**：

```python
TASKS_FILE = Path(os.environ.get("OMO_TRACKED_TASKS") or (ROOT / ".omo" / "state" / "tracked-tasks.json"))
```

于是该常量的值由**导入时刻**的进程环境决定，而 `OMO_TRACKED_TASKS` 的声明时刻在进程生命周期里
没有保证。两种后果，实测各中一次：

1. **测量装置**：`sys.modules` 只导入一次。谁先被导入，`TASKS_FILE` 就永久冻在谁的 env 上。
   最小复现（同一 worktree、同一 Python）——`tests/unit/test_deadline_tracker_ledger.py:13` 在
   collect 期导入，`tests/unit/test_reporting_reads_ledger.py:31` 之后才设置 env：

   ```
   python3 -m pytest tests/unit/test_deadline_tracker_ledger.py tests/unit/test_reporting_reads_ledger.py \
     -q -p no:randomly    →  4 failed, 5 passed
   python3 -m pytest tests/unit/test_reporting_reads_ledger.py -q    →  6 passed
   ```

   即「单跑绿 / 全量红」。失败是 `r["ledger"]["total"] == 3` 与 `risk_level == "medium"` 读到
   真实台账而非沙箱台账——**断言没错，是被测模块在说谎**。
2. **生产路径**：常驻 daemon 在 env 注入之前导入即永久读错面。`bin/bc-os/policy_radar.py:167-168`
   已用「模块可能早于环境变量被导入, 调用时再套一遍」绕过同一缺陷；那句注释是缺陷存在的自证，
   也是本轮的第二个消费者证据。

## 2. 不变量

- **I1 调用时解析**：`deadline_tracker` 的读面（`load_tasks`）与写面（`save_tasks`）必须经
  `tasks_file()` 在**调用时刻**取值；模块级不得再出现由 env 派生的路径常量。
- **I2 优先级**：`tasks_file()` 依次取①显式覆盖（模块属性 `TASKS_FILE`，仅当被显式赋值）
  ②`OMO_TRACKED_TASKS` ③`ROOT/.omo/state/tracked-tasks.json`。保留①是为了让既有 5 处
  `monkeypatch.setattr(deadline_tracker, "TASKS_FILE", …)` 语义不变——它们表达的是"覆盖"，
  而覆盖恰恰是该属性过去承担不了的职责。
- **I3 无需 reload**：env 重定向生效**不得**依赖 `importlib.reload`。既有
  `test_env_redirect` 用 reload 才让断言成立，那是把被测缺陷写进了验收；本轮改为不 reload 直接断言。
- **I4 两份副本同形**：`bin/ssot/deadline_tracker.py` 与 `runtime/ssot-stable/deadline_tracker.py`
  的解析段逐字一致（本仓 SSOT 双副本纪律，只改一份会让 stable 面继续带病）。
- **I5 绕不过第二套机制**：`bin/bc-os/policy_radar.py` 的调用时改写随 I1 成为死码，必须删除，
  不得保留成"双保险"。

## 3. 边界

- 不改 `tracked-tasks.json` 的磁盘 schema 与任务生命周期语义。
- 不碰 launchd plist / cron 改道（那是 B4b 批次 2+，需逐批授权）。
- 不把 `TASKS_FILE` 改名——改名会把 5 处 patch 变成断链，且掩盖 I2 的职责划分。

## 4. 为什么这是 B4b 的前置

B4b 的每批验收是「切完这批，`--reality-check` E2 仍为 0」。批次切换后 profile env 将由
plist/cron 注入，声明时刻与 daemon 导入时刻的**先后关系由 launchd 决定，不由代码决定**——
正是本缺陷的触发条件。留着 import 时冻结的写面路径去做改道，等于把测量装置建在沙上。
