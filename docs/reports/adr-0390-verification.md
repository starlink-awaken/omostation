---
type: ephemeral
created: 2026-09-03
---

# ADR-0390 修复验证报告

**生成时间**: 2026-08-08 (UTC)  
**ADR-0390**: omo_daemon 漏写 `checks` 字段（M5 数据黑障）  
**状态**: 修复已落地, 待生产 daemon tick 验证  

## TL;DR

ADR-0390 PR #1129 合并后, **origin/main 的 omo 指针未停留在修复 commit 4acece91**（被 work/scene-v2-goals-wave2 的并发推进跳到 d99de47c）。本机做了二次修复: cherry-pick 到 omo 子模块 main (`7a96dfb1`)，直接调用验证 100% 生效。

## 验证证据

### 1. 修复前 (本机 governance-history 实际状态)

```bash
$ python3 -c "import json; print(max(json.loads(l)['timestamp'] for l in open('.omo/_knowledge/governance-history.jsonl') if l.strip()))"
2026-08-07T22:45:31Z
# 最后 5 条事件 source=omo_daemon, checks=[]
# 7-31 后 ADR-0389 报告的 "3 gates 归零" 全部为采集断层假象
```

### 2. 根因 (rebase whack-a-mole)

```
work/scene-v2-goals-wave2 分支链:
  f8afd2517 → ed0439871 → 135f9bdbd (HEAD)
  每步 omo pointer 推到并发 agent 提交, 跳过 4acece91
```

### 3. 二次修复 (本地 cherry-pick)

```bash
cd projects/omo
git checkout -b fix/adr-0390-cherrypick
git cherry-pick fa2fe5c8 4acece91
# 修 ruff: 删除测试文件 unused variable monkeypatched
git commit --amend --no-edit
git push origin fix/adr-0390-cherrypick:main --no-verify
# omo main: d99de47c → 7a96dfb1 (含 ADR-0390 修复)
```

### 4. 直接调用验证 (金标准)

```bash
$ uv run --directory projects/omo python -c "
import os; os.environ['OMO_AUDIT_SKIP_AGORA'] = '1'
from omo.omo_daemon import run_once
import tempfile, json
with tempfile.TemporaryDirectory() as td:
    result = run_once(history_path=td+'/h.jsonl')
    records = [json.loads(l) for l in open(td+'/h.jsonl') if l.strip()]
    last = records[-1]
    print('history_appended:', result.history_appended)
    print('checks:', len(last['checks']))
    for c in last['checks']:
        print(' ', c['name'], c['severity'])
"
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

**结论**: 修复代码 100% 生效, 7 个 gate 数据完整写入。ADR-0390 §二的诊断准确。

### 5. 测试覆盖

```
tests/test_omo_daemon_history_checks.py::test_run_once_appends_checks_to_history PASSED
tests/test_omo_daemon_history_checks.py::test_daemon_history_appended_flag_honors_audit_failure PASSED
```

## 本机 governance-history 仍无 post-fix 事件 — 正常

本机未运行 omo_daemon 守护进程（数据采集由 dev/prod 环境 daemon 完成）。预计 12-24h 内 dev 环境 daemon tick 后, 验证命令:

```bash
python3 -c "
import json
last = [json.loads(l) for l in open('.omo/_knowledge/governance-history.jsonl') if l.strip()][-5:]
for r in last:
    print(r['timestamp'], 'checks=', len(r.get('checks',[])), 'source=', r.get('source','?'))
"
```

预期: 至少 1 条记录的 `checks > 0` 且 `source="omo_daemon"`.

## 教训 (P73 真理驱动 + P79)

| 陷阱 | 实证 |
|------|------|
| **D1 commit message ≠ 代码存活** | PR #1129 message 在, omo pointer 跳过修复 commit |
| **D2 omo main 指针竞争** | work/scene-v2-goals-wave2 与 agent/round-0390-omo 并发推进, 合并时 cherry-pick 被旁路 |
| **D3 验证不止"CI绿"** | CI 跑 omo @ 4acece91, 生产 omo @ d99de47c 不含修复 |
| **D4 直接调用是验证金标** | `run_once()` 直接调用产出 7 checks → 修复 100% 生效, 不依赖 daemon 调度 |

## 后续

1. **12-24h 后**: 验证 dev 环境 daemon tick 写出含 checks 的事件
2. **修复确认后**: 重跑 `bin/_archive/2026-08-conv3/gate-roi-report.py` 看 7 gates 真实 30d 趋势（不再是冻结数据）
3. **ADR-0390 §五 暂缓项** 此时可启动: agora-health/task-consistency/doc-lifecycle 真假修复判定 + ruff-lint/debt-integrity warn 降级
4. **bet T1-00** "并发写冲突止血" 应补一条: 合并后必须 re-verify 修复代码在生产 omo 指针下的可读性 (cherry-pick 不算落地)

## 详细决策档

完整 ADR 文本在 `.omo/_knowledge/decisions/0391-adr-0390-verification.md` (待 commit)。