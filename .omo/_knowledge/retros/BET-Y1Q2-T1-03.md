---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y1Q2-T1-03 复盘
type: retro
---
# BET-Y1Q2-T1-03 复盘

## Q1 实际耗时 vs appetite？超出比例？

单个编排 session 约 50 分钟完成实现、两轮独立审查、CI 修复、子模块 PR 合并与根仓集成，低于 1 day appetite，未超出。
主要耗时不在功能编码，而在负例补强、CI 格式门和子模块治理闭环。

## Q2 done_when 是否全部通过？哪条没过，为什么？

| done_when | 状态与证据 |
|---|---|
| import 仅经 `LedgerBroker.append`，logical source + canonical content hash 幂等 | ✅ 真实样本首次 healthy=701 / imported=700 / duplicates=1；二次 imported=0 / duplicates=701；30 条目标测试覆盖 append spy 与幂等 |
| 坏 JSON / 未知版本隔离且健康行继续 | ✅ 2055 个物理行中 1354 个跨行截断坏记录进入 quarantine，700 个唯一健康记录入账；NaN / Infinity 负例同样 fail closed |
| export 为合法只读 JSONL | ✅ 导出 700 行，逐行 `authority=ledger`、`read_only=true`、`projection=jsonl-shadow/v1`；伪装 projection 的既有文件不可被覆盖 |
| 拒绝 ledger/read-only 反向导入 | ✅ 顶层与 `_meta` 两种形式均隔离；导出再导入时 ledger 不增长 |
| compare 输出稳定计数 / 摘要 / 差异 | ✅ source_unique=ledger_rows=700，missing=extra=0，双方 digest 同为 `8633872c9bb1ed1a96c981fa0c06d1e0eca5beb4282a9e1ea71ff7ffb3a6797b` |
| hash chain、pytest、真实 CLI smoke | ✅ verify total=700 / ok=true；目标 30/30、回归 84/84；OMO PR #25 lint/test/test-cov 全绿 |

未过项：无。根仓 `ssot-guardian` 仍报告 5 个 2026-08-09 已入库的零字节 `bin/ssot/mail_*.py` / `doc_generator.py`，这是基线卫生债务，不是本 bet 引入。

## Q3 过程中发现的与 plan 不符的事实（打假）

1. **真实历史不是 2055 条合法 JSONL 记录**：文件有 2055 个物理行，其中 1354 行是跨行截断 JSON；本 bet 坚持逐行 shadow 契约并隔离，不擅自拼接或 upcast。
2. **第一轮实现存在多个 fail-open 边界**：Python `json.loads` 接受 NaN/Infinity、compare 缺 `--source-id`、不一致仍 exit 0、quarantine/output 可能覆盖源、缺失源可能先建 DB。独立审查发现后按 TDD 全部修复。
3. **最终 reviewer 仍漏掉 overwrite guard 绕过**：仅伪造 `projection` 即可冒充 adapter export。协调器追加反例并收紧为完整只读 envelope 校验。
4. **本地 Ruff 检查不等于 CI lint**：本地 `ruff check` 通过，但 CI 还执行 `ruff format --check`。PR #25 首轮 lint 失败后用 CI 等价命令格式化，第二轮三项 CI 全绿。
5. **登记的 BET smoke 会假绿**：`python -m omo.omo_ledger` 不执行 `main`，返回 0 且无输出。本次已把台账命令改为真实 `uv run --frozen omo ledger`，并用 `jq -e` 对幂等、只读 envelope、compare digest 与 hash chain 做硬断言。
6. **`bet-ledger complete` 的 D0 不穿透子模块**：三个 write surface 已在 omostation-omo PR #25 合并并由不可变 tags 固化，但根仓 `git ls-files` 仍判定“未入库”。本次以子模块 merge SHA、远端 tags 和根指针三层证据受控使用 `--force`；应另开 harness 修复，不把误判当成未交付。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）

本 bet 在 OMO 子模块净增 1326 行（+1329 / -3）：

- `jsonl_shadow.py` 新增 459 行；
- `omo_ledger.py` +138 / -3；
- `test_event_ledger_jsonl.py` 新增 732 行；
- 新增 2 个文件、修改 1 个文件；GaC 规则 +0、ADR +0、脚本 +0、顶级项目 +0。

`bet-ledger.py surface` 的仓库全景观察量：

```text
src_loc       836,701（相对 2026-08 基线 +110,289）
test_loc      377,957（+27,103，保护量未下降）
src_files       3,681（+477）
test_files      1,995（+168）
adr_total         372（+28；本 bet +0）
gac_rules         136（+0）
gac_required       26（+0）
bin_scripts       449（+139；本 bet +0）
standards          55（+2；本 bet +0）
```

## Q5 下一个认领本 track 的 agent 需要知道什么？

1. 真实命令入口是 `uv run --frozen omo ledger ...`，不要用不会执行 `main` 的 `python -m omo.omo_ledger`。
2. 默认 source identity 是 basename；跨目录同名源必须显式传同一个 `--source-id` 给 import 与 compare。
3. 1354 个 quarantine 行是当前真实历史的结构事实，不应偷偷拼接；若要修复旧历史，必须另建“多行重组/upcaster”明确 bet。
4. OMO 交付证据：PR #25，合并 SHA `b14c463beaade86b5ff3d15a374964d11e395c27`；远端标签 `delivery-w1-05-jsonl-shadow-20260811-v2` 指向 CI-green 分支提交。
5. harness 后续项：让 `bet-ledger verify` 校验 semantic output 而非只看 exit code；让 D0 guard 识别“子模块 write surface 已被合并 SHA 包含”。
