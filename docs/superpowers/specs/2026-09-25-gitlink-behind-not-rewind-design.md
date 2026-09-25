---
schema_version: specification/v1
spec_version: 1.0.0
title: "gitlink ancestry gate: 区分『落后于 main』与『回退指针』"
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-25
---

# gitlink ancestry gate: 区分「落后于 main」与「回退指针」

## 问题（实测，非推断）

`bin/gac/check-submodule-rewind.py --range <base> <head>` 的判定循环
（`run_ancestry_gate`，第 428–446 行）只读两端的 gitlink 值：

```python
old = _gitlink_pointer_at(base, path, cwd=root)
new = _gitlink_pointer_at(head, path, cwd=root)
...
if _run_in(subdir, "merge-base", "--is-ancestor", old, new).returncode == 0:
    continue
violations.append({"path": path, "old_sha": old, "new_sha": new})
```

它从不问一个先决问题：**head 有没有碰过这条 gitlink**。pre-push 的实际调用是
`.omo/_truth/registry/hook-manifest.yaml:108`
`check-submodule-rewind.py --range origin/main $PUSH_LOCAL_SHA` —— base 恒为 origin/main。
于是任何「从旧 main 切出、尚未 rebase、且期间 main  bump 了某个子模块」的分支，
都会被判定为指针回退，尽管该分支的 gitlink 与它自己的 merge-base 完全一致。

2026-09-25 在 `ws-gitlink-behind-not-rewind` 上复现（对象是已合并的 `93b19c8a1`）：

| 测量 | 值 |
|------|-----|
| `git merge-base origin/main 93b19c8a1` | `312d67082` |
| `projects/aetherforge` 指针 @ merge-base | `d24ef719665e` |
| `projects/aetherforge` 指针 @ head(`93b19c8a1`) | `d24ef719665e`（同一值） |
| `projects/aetherforge` 指针 @ origin/main | `37e7af86e003` |
| `git log 312d67082..93b19c8a1 -- projects/aetherforge` | 空（没有任何 commit 碰过它） |
| 子模块内 `--is-ancestor d24ef7196 37e7af86e0` | rc=0（main 是线性前进，无改写） |
| 门禁输出 | `FAIL ... 指针由 37e7af86e003 回退至 d24ef719665e (非前进)`，exit=1 |

即：**方向恰好相反的事实被报成回退** —— `37e7af86e0` 是 `d24ef7196` 的后代，
分支只是落后，没有回退任何东西。

代价（可测量）：`.omo/_truth/registry/gate-known-debt.yaml` 里
`kind: gitlink-regress` 的豁免指纹已有 **31 条**（`recorded_at` 自 2026-08-25 起）。
这 31 条里有多少是本误判造成的，**当前无法事后判定** —— 每条只存了
`fingerprint/reason/range`，`range` 里写的是 `origin/main..<head>` 这种当时才解析得动的
移动 ref，没有记录 merge-base 及其指针值。误判与真回退在同一份账里不可区分，
这本身就是第二个缺陷（本次不改登记格式，见「非目标」）。

真实后果：本误判给出的两条「修复指引」都会把交付推向错误动作 ——

1. 「恢复子模块前进指针并重新 commit 主仓 gitlink」= 让 agent 把**别人**的 gitlink
   变更塞进**自己**这次交付（越出 write_surfaces，且 squash 合并时可能与 main 的 bump 冲突）；
2. 「加 `[gitlink-regress: <理由>]` 豁免标签」= 为一个并不存在的回退**登记一条 known-debt 指纹**。

`BET-Y2Q3-T10-202` 的 I10 记录了这次误判；正确动作是 rebase，两条指引都不对。

## 契约

「回退」的定义必须只描述 head 的**行为**，而不是描述 head 与 base 的相对新旧：

> 对每条声明的子模块，令 `P_at =` gitlink@base、`P_head =` gitlink@head、
> `P_mb =` gitlink@merge-base(base, head)。
> 仅当 `P_head ≠ P_mb`（head 确实改动了这条指针）**且** `P_at` 不是 `P_head` 的祖先时，
> 判定为回退。`P_head == P_mb` 时分支从未触碰该 gitlink，属「落后」，不判违规。

保留全部现有行为：
- 真回退（head 主动把指针改成非后代）依旧 exit 1，豁免标签与 known-debt 路径不变；
- 未初始化子模块跳过、缺对象跳过、base/head 不可解析跳过 —— 三条 WARN 语义不动；
- index 模式（无 `--range`）与 `is_descendant_or_equal` 的 8 层容忍完全不动。

## 修复

1. `run_ancestry_gate`：在 append violation 之前，取 parent 仓
   `git merge-base base head`，读该 commit 的 gitlink 指针；等于 `new` 即 `continue`，
   并追加一条只读 INFO/WARN（说明「分支未改动该 gitlink，main 侧 bump 待 rebase」），
   使被抑制的原因在输出里可见 —— 抑制必须可解释，不能静默。
2. `_format_rewind_block`：修复指引补第 3 条 —— 若分支从未触碰该指针，动作是
   `git rebase <base>`，不是 commit 别人的 gitlink、也不是登记豁免。

## 非目标

- 不碰 `.omo/_truth/registry/governance-checks.yaml`（CR-SUBMODULE-REWIND 的注册描述写的是
  index 模式「对比 index 当前指针与上一次 commit 的指针」，本改动不涉及，无需改 SSOT）。
- 不追溯重判那 31 条 known-debt 指纹（登记格式缺 merge-base，重判需要另案）。
- 不改登记格式、不改 hook-manifest 的 base 选择、不引入新豁免类型。
- 不放宽真回退：本改动只增加一个前置条件（head 是否触碰过），不删任何现有判定。

## 验收

1. 复现场景转绿：`--range origin/main 93b19c8a1` → exit 0，且输出含该子模块的「未改动/落后」说明。
2. 真回退仍拦：head 主动 commit 一个非后代指针 → exit 1，violation 列表含该项。
3. 上述两条各有一个可在 `tmp_path` 里确定性构建的合成仓库（真 parent 仓 + 真 submodule）测试，
   不依赖本仓历史，也不依赖网络。
4. `tests/unit/gac/test_check_submodule_rewind.py` 全绿；`python3 bin/gac/check-submodule-rewind.py`
   （index 模式）与 `--json` 行为不变。
5. `make gac-local-gate` 不因本改动新增问题；共享门禁退出码不变。
6. 交付零 gate 豁免、零 waiver 文件、零 `--no-verify`、不提交任何 gitlink。
7. 本次以 G5 对称豁免（`chain_bind.start_requires_bet` 对 `GOVERNANCE_EVOLVE_WORKFLOWS`
   采用与 `evaluate_closeout` 同一谓词）第一次真实启动 run：`start` 不带 `--bet`
   且 verdict 为 `governance_evolve_exempt`，据此**不新开 bet** —— 新开一条与治理演进
   重复的 bet 才是 F1 要消灭的纸面绑定。
