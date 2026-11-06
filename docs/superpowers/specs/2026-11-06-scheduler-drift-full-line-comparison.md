---
schema_version: specification/v1
spec_version: 1.0.0
title: A4 Scheduler 登记↔安装态按整行比对
bet_id: BET-Y2Q4-T10-291
owner: governance-agent
status: accepted
lifecycle: contract
last-reviewed: 2026-11-06
---

# A4 Scheduler 登记↔安装态按整行比对

## 问题与证据

`bin/scheduler-compile.py` 的 `check_drift()` 在两侧都把比对键截到 120 字符
（登记侧 `:231`、安装侧 `:244`，`[:120]`）。这不是显示截断，而是**判据截断**：
120 字符之后的任何差异都不参与相等判断。

基线 `a59a966e7` 实测读数：

- 登记侧：`status=active` 且 `planes` 含 `crontab` 的条目 48 条，其中 **35 条**的归一化键长度超过 120（最长 530 字符）。
- 安装侧：本机 crontab 有效行 58 条，整行去重 **53** 条，截断去重 **47** 条 —— 6 条被截断折叠。
- 折叠集中在 2 个键上：`*/2 … omo.cli resident daemon --once --role <X>`（5 个角色折成 1 个键）与 `*/5 … resident {inbox,ingest,signals}`（3 折 1）。
- 后果一（欠计）：本机真实未登记安装行 **10** 条，门禁读数为 `known_orphan_count: 4`。债账少记 6 条。
- 后果二（假绿）：以注入缝复现 —— 取登记侧最长条目 `mcptool-drift-report-daily`（键长 530），把安装态里对应行的 120 字符之后一段改掉（`.log` → `.MUTATED.log`），
  `check_drift()` 读数仍为 `ok=True drift=0 orphan=0`；同批基线行（未改动）读数为 `ok=True`。
  即：**声明与实装不一致时门禁照样放行**，且失败形态是「读数正常」而不是报错。

## 判据口径

AGENTS.md §7「六类会让判定静默失效的形状」第 ⑥ 类（管道判据的匹配词必须能在被检对象实际文本上命中）与第 ⑧ 类
（检测器报出「集合相等」可能是检测器少认形状）的同一形状：判据的键宽度小于被检对象的实际宽度时，
「相等」是截断的产物而不是事实。本仓对 launchd 平面已按此口径处理（`missing_installed` 按 label 全串比对），
crontab 平面是这条判据的最后一处截断位。

## 修复范围（in）

1. `check_drift()` 两侧比对键改为**归一化整行**，取消 `[:120]`。归一化本身（解释器归一 `_normalize_interpreter`、
   `$HOME/Workspace` 展开 `_expand_workspace`、`harness-cron.sh` 包装行展开）**一字不改** —— 它们消除的是
   等价写法差异，截断消除的是真实差异，两者不能混为一谈。
2. 输出面：`drift_count` / `orphan_count` / `known_orphan_count` 改为按整行计数；三个键名、类型与
   `ok` 的语义保持不变；`launchd` 段（shadow）不受影响，仍不参与 `ok` 判定（ADR-0457 三段式）。
3. 用例（`tests/unit/test_scheduler_compile_launchd_plane.py` 内新增，一正一反，两条互不共享失效模式）：
   - 反例：合成一对整行不同、前 120 字符相同的登记/安装行；用例先断言这个前提本身成立
     （`key_full_a != key_full_b` 且 `key_full_a[:120] == key_full_b[:120]`），再断言
     `check_drift(installed_lines=[...])` 报 `ok=False`、`drift_count>=1`、`orphan_count>=1`。
   - 正例：同一对改成整行相同 ⇒ `ok=True`、两侧计数为 0。
   - 欠计反例：注入 5 条仅角色名不同且差异落在 120 字符之后的安装行 + `known_orphans` 覆盖 ⇒
     `known_orphan_count == 5`（而不是 1）。

## 非目标（out）

- 不改 crontab / launchd / 任何调度实装，不启停服务，不删任何安装行。
- 不新增 `known_orphans` 条目：本机 10 条未登记安装行已由既有条目逐条覆盖（实测 `not-covered=0`），
  本 BET 只把计数改准，不扩债账。
- 不改 `_normalize_interpreter` 的解释器识别正则，不改 `compile_crontab()` 产物。
- 不引入严格度开关或 observe-only 中间态：本修复在同一份源码上把已声明事实的读数改准，
  不新增判定类别。

## 验收（done_when 对应）

1. 整行比对生效可由注入用例复现：改动前该用例 `ok=True`（假绿），改动后 `ok=False`（点名差异）。
2. 本机读数迁移有据：`drift_count` 改动前后同为 0，`orphan_count` 同为 0，
   `known_orphan_count` 由 4 → 10 且新增的 6 条全部命中既有 `known_orphans` 模式（逐条列出覆盖项）。
3. `test_shadow_segment_never_blocks_the_gate` 仍绿，且安装态由 `compile_crontab()` 注入时
   `ok=True` 不依赖本机 crontab（hermetic）。
4. 门禁调用方（`bin/gac/gate-health-check.py` A4）读数可解释：`ok` 值不因本 BET 改变，
   只有计数改变；如改变必须能指到具体的 120 字符之后差异行。
