---
schema_version: specification/v1
spec_version: 1.0.0
title: 全景收集器账本路径接入 profile 缝
bet_id: BET-Y2Q4-T10-279
owner: governance-agent
status: accepted
lifecycle: contract
last-reviewed: 2026-11-02
---

# 全景收集器账本路径接入 profile 缝

## 问题与范围

`.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md` 规定：读面跟随当前检出
（`code_root()` / `canonical_root()`），写面跟随 profile（`state_root()` /
`event_ledger_path()`）。`bin/panorama/panorama-collect.py` 是双根收敛清单里唯一未接入
`event_ledger_path()` 的消费方 —— 实测该文件对 `event_ledger_path` 零命中，而其 import 面
`:72` 只取 `canonical_root, state_file_read, state_root`。

缺陷形状有三层，必须同一次改：

1. **import 时冻结**：`:111-116` 把 `OMO_EVENT_LEDGER_DB` 的回落值算成
   `ROOT / "runtime/omo/event-ledger.sqlite3"`，而 `ROOT`（`:75`）由
   `Path(__file__).resolve().parents[2]` 或 `PANORAMA_ROOT` 得出 —— 是**检出根**，
   不是 profile 的 state 根。profile 晚于 import 声明就被冻在旧根上，且没有任何测试会红。
2. **默认参数二次冻结**：`:370`、`:381`、`:672` 三处以 `event_ledger: Path = EVENT_LEDGER`
   作默认值。默认值在**函数定义时刻**求值，即使把 `EVENT_LEDGER` 改成函数，这三处仍会冻结旧值。
3. **手写 env 判别的重复面**：`:3692` 与 `:3931` 各自写
   `state_root() if os.environ.get("OMOSTATION_STATE_ROOT") else CODE_ROOT/ROOT`，
   与缝的解析序（env 覆盖 → state 根 → 检出）不同源；账本位由第 1 层单独决定，
   于是同一进程内「投影落 state 根、账本落检出」可以长期并存而不报错。

本变更仅把上述三层收敛到既有缝，不新增 env 名、不改生产 profile 声明、不改 plist/crontab、
不做状态搬迁。

## 契约

- 模块级 `EVENT_LEDGER` 常量移除；改为在**调用时刻**经 `repo_root.event_ledger_path()` 解析。
- 三处默认参数改为 `event_ledger: Path | None = None`，在函数体内
  `event_ledger or event_ledger_path()` 解析；显式传入者行为不变（测试侧 setattr 缝保持可用）。
- `:3921` 调用点不传具体常量，交由上述调用时刻解析。
- 回落值与今日逐字节等价的根据：`event_ledger_path()` = `OMO_EVENT_LEDGER_DB` 否则
  `state_root() / Path("runtime") / "omo" / "event-ledger.sqlite3"`（`bin/lib/repo_root.py:59`），
  而未声明 profile 时 `state_root() == 当前检出`（由
  `tests/unit/test_repo_root_profile.py` 钉住）。

## 判据

1. **正向落点**（不能只靠「检出里不脏」这种否定式）：声明
   `OMOSTATION_STATE_ROOT=<假目录>` 后，`panorama-collect` 解析出的账本路径的父目录
   等于 `<假目录>/runtime/omo`，且**不**以当前检出为前缀。
2. **env 最高优先级**：同时声明 `OMO_EVENT_LEDGER_DB=<另一假路径>` 时取该路径。
3. **反基线读数由同一次扫描产出**：改前 `EVENT_LEDGER` 作为模块级常量的定义点计数为 1、
   默认参数冻结点为 3；改后均为 0，且 `event_ledger_path` 在该文件命中 ≥ 1。
   判据用 `git grep -E`（本仓实测 `\s` 在 git 的 ERE 引擎下恒不命中，一律用 `[[:space:]]`）。
4. **变异对照**：把调用时刻解析改回模块常量后，判据 1 的用例必须当场红；
   否则「绿」只是装置没命中。
5. 一次 dev profile 运行后 `git status --short` 不含本文件与检出根下的账本路径。

## 非目标

- 不改 `:3692` / `:3931` 之外的其他 `state_root()` 判别点（它们属投影与 task 面，
  由既有 ADR-0129/B5 腿负责）。
- 不迁移任何 ledger 数据，不改 `~/.local/state/omostation/**`。
- 不把 `PANORAMA_ROOT` 语义改为 profile 根。

## 回滚

单文件 + 单测试文件的重构，回滚为一次 `git revert`；无机器级副作用。
