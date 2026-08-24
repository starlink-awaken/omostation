---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
created: 2026-08-24
last-reviewed: 2026-08-24
bet_id: BET-Y1Q3-T1-11
owner: human-principal
risk_level: L2
human_gate: false
---

# Platform-rebase 独立 clone 退役 provenance 收敛

## 1. 目的

让经过 GitHub `update-branch` 或等价 platform rebase 的独立 writer clone 能在不放宽默认
provenance guard 的前提下安全退役：平台基线引入的其他作者不属于本次 delivery，只有
`platform_base..platform_head` 的 delivery commits 必须匹配该 clone 冻结的作者身份。

同时恢复 current main 的脚本减法配额。不得通过提高 `script_baseline` 消除红灯；本 BET
归档一个已直接证明无消费者的旧 loader，保持“新增/深化能力必须伴随减法”的约束。

## 2. 当前事实

1. B4-D native execution receipt PR #2051 已合并，root main 到达
   `bd3d64cd88ff9c582e373eb5ff91cf44d969f82f`；随后规划与 attestation 变更继续前进。
2. 旧隔离 attempt 中已有 source commit
   `e3848f5f6a6801d28da7baef2d23ef78818c920a`，只修改：
   - `bin/gac/agent-clone.py`
   - `bin/gac/clone-lifecycle.py`
   - `tests/test_clone_lifecycle.py`
3. source attempt 已通过 focused tests、Ruff、Python 3.9 AST 和独立 review，但尚未在
   current main 重放；旧证据不能替代新基线验收。
4. current main 尚无 `retirement-provenance` 子命令，也没有 platform-aware author 范围、
   origin fetch/push 双向一致性和 quarantine 后 origin race 验证。
5. PR #2085 新增 `bin/ssot/attest-review.py` 后，活动脚本为 443、基线为 442；严格 GaC 与
   依赖它的 workflow doctor 均失败。
6. `bin/meta/vocabulary_loader.py` 没有 shebang、没有入口登记，仓库内除自身外不存在路径、
   import、`load_vocabulary` 或 `vocabulary_loader` 消费者；它可以保留历史但不应继续占活动面。

## 3. 架构约束

### 3.1 默认 guard 不变

普通 `agent-clone.py guard --require-clone` 必须继续检查：

- actor / delivery attempt / clone root / working branch；
- canonical repository 与 fetch/push transport；
- frozen root、live author、receipt digest；
- 所有 delivery commits 的作者均属于该 attempt。

普通 guard 禁止接受 `--platform-base` 或 `--platform-head`，避免把“忽略平台作者”变成通用
旁路。

### 3.2 专用 retirement provenance

新增窄入口：

```text
agent-clone.py retirement-provenance
  --clone <verified-clone>
  --platform-base <exact-pr-base-oid>
  --platform-head <exact-pr-head-oid>
```

它只允许在 `clone-lifecycle retire --platform-rebased-pr <number>` 内部使用。校验范围必须是
精确 `platform_base..platform_head`，不得使用当前 main、branch name 或模糊 merge-base
替代 GitHub PR 返回的 OID。

### 3.3 Repository 与竞态边界

退役必须至少两次读取并比较：

1. live origin 对应的精确 GitHub repository；
2. provenance receipt 的 canonical repository；
3. GitHub PR repository / owner / head branch / PR number / base branch=`main`；
4. origin 的唯一 fetch URL 与唯一 push URL，二者必须映射到同一 repository；
5. quarantine 后重新读取 PR 与 origin，任一变化均恢复原 clone 并拒绝退役。

### 3.4 减法边界

将：

```text
bin/meta/vocabulary_loader.py
```

移动到：

```text
bin/_archive/2026-08-t1-11/vocabulary_loader.py
```

只移动，不重写历史内容；禁止提高 `script_baseline`。如果实现时发现真实消费者，立即触发
断路器，不得为了配额继续归档。

## 4. 交付范围

允许修改且仅允许修改：

- `bin/gac/agent-clone.py`
- `bin/gac/clone-lifecycle.py`
- `tests/test_clone_lifecycle.py`
- `bin/meta/vocabulary_loader.py`
- `bin/_archive/2026-08-t1-11/vocabulary_loader.py`

实现必须从 current main 新建 v2 independent clone；旧 attempt 只作为 source patch 与历史
证据读取，不允许本地 rebase 后直接交付。

## 5. 验收标准

1. current-main 新 attempt 重放 `e3848f5f6` 的语义，保留三个目标文件中的后续主线行为。
2. platform base 的其他作者被排除；delivery 范围内错误作者 fail-closed。
3. receipt repository 与 PR repository 不一致时拒绝。
4. base branch 非 `main`、PR 未合并、head/branch/owner/number 不匹配时拒绝。
5. origin 多 fetch URL、多 push URL、fetch/push repository 不一致或验证后漂移时拒绝。
6. quarantine 后 PR 或 origin 变化时恢复 clone，不能留下半退役目录。
7. 默认 guard parser 不接受 platform 参数。
8. `vocabulary_loader.py` 仅移动到 archive；活动脚本数回到不高于 442，baseline 不变。
9. clone lifecycle focused tests、Ruff、Python 3.9 AST、GaC、平台 CI 与独立 review 全绿。
10. source commit/tag/PR/merge 全部可追溯；旧 attempt 只通过 lifecycle receipt 退役。

## 6. 负向测试

- platform delivery author 与 clone author 不同；
- receipt canonical repository 被篡改；
- origin fetch 与 push 指向不同仓库；
- origin 在 guard 后、quarantine 前后变化；
- GitHub PR base 不是 `main`；
- platform base/head 缺任一个参数；
- 普通 guard 传 platform 参数；
- quarantine 复核失败后原路径未恢复；
- archive 前再次扫描出现 `vocabulary_loader` 真实消费者。

## 7. 验证命令

```bash
uv run --with pyyaml --with pytest python -m pytest tests/test_clone_lifecycle.py -q
uv run ruff check bin/gac/agent-clone.py bin/gac/clone-lifecycle.py tests/test_clone_lifecycle.py
python3 - <<'PY'
import ast
from pathlib import Path
for path in ("bin/gac/agent-clone.py", "bin/gac/clone-lifecycle.py", "tests/test_clone_lifecycle.py"):
    ast.parse(Path(path).read_text(encoding="utf-8"), feature_version=(3, 9))
PY
python3 bin/gac/agent-clone.py --help | grep -q retirement-provenance
python3 bin/gac/gac-validate.py --gate
test ! -f bin/meta/vocabulary_loader.py
test -f bin/_archive/2026-08-t1-11/vocabulary_loader.py
```

## 8. 非目标与断路器

非目标：修改 clone identity schema、改变 writer admission、自动删除远程分支、修改
plist/crontab/service/runtime、提高配额基线、处理 T7 evidence digest、把 BET 标 done。

出现任一条件立即停止：

- 重放需要超出五个 write surfaces；
- 必须放宽默认 guard 或接受未知 author；
- 无法从 GitHub PR 获得精确 base/head；
- `vocabulary_loader.py` 被证明仍有真实消费者；
- 退役无法在竞态失败后恢复原路径；
- platform CI 不能区分实现失败与机器/外部环境失败。

## 9. Decision Log

1. 选择专用 `retirement-provenance` 子命令，不给普通 guard 增加可选旁路参数。
2. 选择 GitHub PR 精确 base/head OID，不从当前 main 或本地 merge-base 猜平台范围。
3. 选择 guard 前后与 quarantine 后多次复读 origin/PR，以可恢复失败换取退役竞态安全。
4. 选择归档零消费者 loader，不提高 script baseline，也不删除 human attestation 新入口。
5. 选择 current-main 新 attempt 重放，不在旧 source clone 做本地 rebase 后直接交付。

## 10. 反指标

- 不以新增测试数、代码行数、guard 分支数或退役 clone 数宣称完成。
- 不以 `script_baseline` 上调、非 required check 被忽略或 `input_accepted` 作为绿色证据。
- 不以文件不存在证明 clone 已合规退役；必须有 merged PR、origin tag 与 retirement receipt。
- 不以 source attempt 的历史测试替代 current-main 重放后的直接验证。
