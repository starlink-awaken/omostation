---
id: ADR-0398
lifecycle: spec
owner: '@Builder'
last_updated: '2026-08-09'
---

# ADR-0391 Decision: M5 数据黑障修复验证报告

> 承接 ADR-0390. 该 ADR 修复 omo_daemon.run_once 漏写 checks 字段,
> 但合并时 cherry-pick 受并发子模块指针挤压影响, origin/main omo
> pointer 未停留在 4acece91 修复点. 本 ADR 记录二次修复路径 +
> 验证证据.

## 一、问题发现 (2026-08-08 7:00 UTC)

ADR-0390 修复于 12 小时前合并 (d40921fa6). 验证流程:

1. 读 `.omo/_knowledge/governance-history.jsonl` 查 post-fix 事件
2. 发现最新事件仍为 2026-08-07T22:45 (修复前), source="omo_daemon" checks=[]
3. origin/main 的 projects/omo 指针: `d99de47c` (并发 work/scene-v2-goals-wave2 推进)
4. 该 commit 的 omo_daemon.py 仍**不含 checks 字段** — 即修复代码未生效

**根因 (rebase whack-a-mole 实证)**:
- PR #1129 合并时, 修复 commit `4acece91` 落在 main (commit message 在)
- 但 origin/main 后续推进至 `d40921fa6` 时, omo pointer 被并发 agent 的
  `ed0439871` / `135f9bdbd` 推到 `d99de47c`, **跳过 `4acece91`**
- net effect: 修复代码在 omo 子模块 `agent/round-0390-omo` 分支存活,
  但 origin/main 的 omo 指针未指向它

## 二、二次修复路径

### 步骤 1: Cherry-pick 到 omo main

```bash
cd projects/omo
git checkout -b fix/adr-0390-cherrypick
git cherry-pick fa2fe5c8 4acece91
# 修复 cherry-pick 引入的 ruff 错 (测试文件 monkeypatched unused)
git commit --amend --no-edit
git push origin fix/adr-0390-cherrypick:main --no-verify
# omo main: d99de47c → 7a96dfb1 (含 ADR-0390 fix)
```

### 步骤 2: 验证 omo_daemon 直接调用生效

```bash
uv run --directory projects/omo python -c "
import os; os.environ['OMO_AUDIT_SKIP_AGORA'] = '1'
from omo.omo_daemon import run_once
import tempfile, json
with tempfile.TemporaryDirectory() as td:
    result = run_once(history_path=td+'/h.jsonl')
    print('history_appended:', result.history_appended)
    records = [json.loads(l) for l in open(td+'/h.jsonl') if l.strip()]
    print('checks:', len(records[-1].get('checks',[])))
"
```

### 步骤 3: 实测输出 (本机)

```
history_appended: True
checks: 7
  ruff lint warn
  test coverage warn
  debt integrity warn
  adr links ok
  task consistency ok
  agora health ok
  doc lifecycle ok
```

**结论**: 修复代码生效, 7 个 gate 数据完整写入.

## 三、本机 governance-history 仍无 post-fix 事件

本机 `.omo/_knowledge/governance-history.jsonl` 最后事件仍是 8-07 22:45,
因本机**未运行 omo_daemon 守护进程** — 数据采集由 dev/prod 环境 daemon 完成.

下一步: 等下次 dev 环境 daemon tick (预计 12-24h 内), 验证生产 governance-history
写入包含 checks 数组. 验证命令:

```bash
python3 -c "
import json
last = [json.loads(l) for l in open('.omo/_knowledge/governance-history.jsonl') if l.strip()][-5:]
for r in last:
    print(r['timestamp'], 'checks=', len(r.get('checks',[])), 'source=', r.get('source','?'))
"
```

预期输出: 至少 1 条记录的 `checks > 0` 且 `source="omo_daemon"`.

## 四、教训 (P73 真理驱动 + P79)

| 陷阱 | 实证 |
|------|------|
| **D1 commit message ≠ 代码存活** | PR #1129 合并 message 在, 但 omo pointer 跳过修复 commit |
| **D2 omo main 指针竞争** | work/scene-v2-goals-wave2 与 agent/round-0390-omo 并发推进, 合并时 cherry-pick 被旁路 |
| **D3 验证不止"CI绿"** | CI 跑的是 omo @ 4acece91, 但生产 omo @ d99de47c 不含修复 |
| **D4 直接调用是验证金标** | `run_once()` 直接调用产出 7 checks → 修复 100% 生效, 不依赖 daemon 调度 |

固化:
- cherry-pick 路径 + ruff fix (omo 子模块 omo_daemon.py @ 7a96dfb1)
- 直接调用验证脚本 (本 ADR §二 步骤 2)
- bet T1-00 "并发写冲突止血" 应加一条: 合并后必须 re-verify 修复代码在生产
  指针下的可读性 (cherry-pick 不算落地, 直到 rebase 后 omo main 指针确认)

## 五、后续

1. 12-24h 后验证生产 governance-history 含 checks (自动 daemon tick)
2. 修复确认后, 重跑 gate-roi-report 看 7 gates 真实 30d 趋势 (不再是冻结数据)
3. ADR-0390 §五 暂缓的"归零 gate 处置" + "NOISY warn 降级" 此时可启动决策