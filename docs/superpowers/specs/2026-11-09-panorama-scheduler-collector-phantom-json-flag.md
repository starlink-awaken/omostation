---
schema_version: specification/v1
spec_version: 1.0.0
title: 修掉 Panorama scheduler 采集器传给 scheduler-compile.py 的不存在 flag（A9 永久 PARTIAL 的根因）
bet_id: BET-Y2Q4-T10-343
owner: governance-agent
status: accepted
lifecycle: contract
last-reviewed: 2026-11-09
---

# 契约：采集器只能传被调用脚本确实接受的 flag

## 背景与实测

Agent Brief（`runtime/dashboard/agent-brief.json`，2026-11-09T11:34:20Z）把 A9 列为待修失败门。
按 brief 自身的告警重跑底层探针 `collect_gates()` 实测，A9 报：

```
A9 evidence incomplete: cockpit_sources, documents=PARTIAL; strategy=PARTIAL;
scheduler=STALE_UNAVAILABLE(Collection failed for 'scheduler': diagnostic command exit 2)
```

顺着 detail 定位到 `bin/panorama/assets/host/scheduler_collector.py.asset`：

- `:83` 的守卫要求 argv 末尾必须正好是 `["--check", "--json"]`，否则 `unsupported diagnostic command`；
- `:127-136` 真的拼出 `... -- <root>/bin/scheduler-compile.py --check --json`；
- `:98-99` `parse_diagnostic()` 对 `returncode not in (0, 1)` 抛 `CollectionError("scheduler", f"diagnostic command exit {returncode}")`。

而被调用方 `bin/scheduler-compile.py` 的参数面是 `[-h] [--check] [--generate {crontab,launchd}] [--diff]`
（安装根那份多一个 `--no-resolve-interpreter`），**从来没有 `--json`**。2026-11-09 实测两种 root 各跑一次真实命令：

```
rc=2  stderr: scheduler-compile.py: error: unrecognized arguments: --json
```

两侧同时对同一契约各写各的：调用方强制要求一个被调用方不认识的 flag，
被调用方 `--check` 本身就已经输出 JSON 且以 rc=1 表达 not-ok。
结果是**这条采集器永远不可能成功**，A9 因此永久 PARTIAL，而失败被降级成
一个 source 级 `STALE_UNAVAILABLE`，没有任何人看到「坏在参数上」。

## 为什么既有测试没抓住

`tests/unit/test_scheduler_collector_registry_root.py::test_collect_actually_runs_against_the_resolved_root`
把 `_run_cmd` 整个 stub 掉（`:56-64` 的 `fake_run_cmd` 直接返回固定 JSON），
然后在 `:111` 断言 `seen["argv"][-2:] == ["--check", "--json"]` ——
把坏 flag 一起钉成了绿。基线实测 `5 passed`，全是按构造就绿。

## 契约条款

1. **采集器必须只传被调用脚本确实接受的 flag。** 目标 argv 尾段改为 `["--check"]`，
   守卫同步改为 `argv[-1:] != ["--check"]`。被调用方的 `--check` 已满足
   `parse_diagnostic()` 的两条不变量（stdout 是含 `ok: bool` 的 JSON、`ok == (rc==0)`）。
2. **新增真实契约回归，替掉「stub 里断言坏值」的形状。** 用例从采集器实际拼出的 argv 中
   取 flag 尾段，用真实解释器对被调用方执行一次，断言 `rc in (0, 1)` 且 stdout 可解析且
   `ok` 是 bool。把 `--json` 加回去，该用例当场红。
3. **既有 5 条根解析用例一字不动**，只把 `:111` 那条错误断言改成正值 —— 根解析语义
   （publisher 优先、缺编译器回落工作区、运行时取自工作区）由它们继续作证。
4. **不改 `bin/scheduler-compile.py`。** 不为了迁就调用方新增一个什么都不做的 `--json`
   兼容 flag；调用方是错的一侧。
5. **不碰 A9 其余 source**（`documents`、`strategy`、`cockpit_sources` 的 PARTIAL 是
   各自独立的证据缺口，本 BET 只修 `scheduler` 这一条链路）。

## 验收

- 反证成立：把 `--json` 重新塞回 argv，新增的契约用例当场红（必须实测红）。
- 正证成立：修好后同一用例绿，且该文件 6 条用例全绿。
- 真实通路成立：`collect_gates()` 重跑后 `scheduler` 源不再是
  `diagnostic command exit 2`；A9 detail 中不再出现该短语（其余 PARTIAL 项允许仍在）。
- 基线：修改前 `5 passed`，修改后 `6 passed`。
