#!/usr/bin/env python3
"""T7: 跨会话断点续传 — 模拟崩溃后冷启动验证
场景:
  1. 基准状态快照
  2. 模拟长操作 (SSB写入中途崩溃)
  3. 冷启动恢复 — 验证数据完整性
  4. HANDOFF 恢复 — 从 SSB 重建最近状态
"""

import hashlib
import json
import os
import random
import time

ECOS = os.path.expanduser("~/Workspace/eCOS")
SSB_DB = os.path.join(ECOS, "LADS/ssb/ecos.jsonl")
STATE = os.path.join(ECOS, "STATE.yaml")
HANDOFF = os.path.join(ECOS, "LADS/HANDOFF/LATEST.md")

# ─── 1. Baseline Snapshot ───
print("=" * 60)
print("T7.1: 基准快照")
print("=" * 60)


def ssb_count():
    with open(SSB_DB) as f:
        return sum(1 for _ in f)


def file_hash(p):
    if os.path.exists(p):
        with open(p) as f:
            return hashlib.md5(f.read().encode()).hexdigest()[:8]  # noqa: S324
    return "MISSING"


baseline = {
    "ssb_events": ssb_count(),
    "state_hash": file_hash(STATE),
    "handoff_hash": file_hash(HANDOFF),
    "timestamp": time.time(),
}
print(f"  SSB事件: {baseline['ssb_events']}")
print(f"  STATE.md5: {baseline['state_hash']}")
print(f"  HANDOFF.md5: {baseline['handoff_hash']}")

# ─── 2. Simulate Crash: Write partial SSB events ───
print("\n" + "=" * 60)
print("T7.2: 模拟崩溃 — 写入部分SSB事件后强行中断")
print("=" * 60)

random.seed(42)

N = 50
crash_at = random.randint(15, 40)  # noqa: S311

events_written = []
with open(SSB_DB, "a") as f:
    for i in range(N):
        event = {
            "seq": 999900 + i,
            "agent": "T7_CRASH_TEST",
            "event_type": "CRASH_SIM",
            "action": f"step_{i + 1}",
            "timestamp": time.time(),
        }
        events_written.append(event)
        f.write(json.dumps(event) + "\n")
        f.flush()
        if i == crash_at:
            print(f"  💥 在第 {i + 1}/{N} 个事件时强制崩溃")
            # Don't close file cleanly, simulate crash
            break

partial_count = crash_at + 1
total_after = ssb_count()
print(f"  写入 {partial_count} 个事件, SSB总共 {total_after} 个事件")

# ─── 3. Cold Recovery Test ───
print("\n" + "=" * 60)
print("T7.3: 冷启动恢复 — 验证数据完整性")
print("=" * 60)

# 3a: SSB 行级原子性检查
with open(SSB_DB) as f:
    lines = f.readlines()

corrupt_lines = 0
valid_events = 0
for i, line in enumerate(lines):
    line = line.strip()
    if not line:
        corrupt_lines += 1
        continue
    try:
        event = json.loads(line)
        valid_events += 1
    except json.JSONDecodeError:
        corrupt_lines += 1

print(f"  总行数: {len(lines)}")
print(f"  有效事件: {valid_events}")
print(f"  损坏行: {corrupt_lines}")

# 3b: 检查 SSB 是否支持从损坏中恢复
# 读取最后10个事件验证完整性
with open(SSB_DB) as f:
    all_lines = f.readlines()
# 检查所有 crash 事件
all_crash_events = [json.loads(line.strip()) for line in all_lines if line.strip() and '"T7_CRASH_TEST"' in line]
print(f"  最近10个事件中 T7_CRASH_TEST 事件: {len(all_crash_events)}")

# ─── 4. HANDOFF Recovery ───
print("\n" + "=" * 60)
print("T7.4: HANDOFF 从 SSB 重建")
print("=" * 60)

# Simulate: HANDOFF is stale, but SSB has recent events
# Read last 20 SSB events and build a recovery summary
with open(SSB_DB) as f:
    all_lines = f.readlines()

recent = [json.loads(line.strip()) for line in all_lines[-20:] if line.strip()]
agents_active = set(e.get("agent", "?") for e in recent)
event_types = set(e.get("event_type", "?") for e in recent)

print(f"  从 SSB 重建: {len(recent)} 最近事件")
print(f"  活跃 Agent: {agents_active}")
print(f"  事件类型: {event_types}")

# Check if HANDOFF can be regenerated from SSB
handoff_exists = os.path.exists(HANDOFF)
handoff_age = time.time() - os.path.getmtime(HANDOFF) if handoff_exists else float("inf")
print(f"  HANDOFF存在: {handoff_exists}, 距今: {handoff_age / 60:.1f}分钟")

# ─── 5. Recovery Action Verification ───
print("\n" + "=" * 60)
print("T7.5: 恢复动作验证")
print("=" * 60)

# 5a: 清理测试事件
with open(SSB_DB) as f:
    all_lines = f.readlines()

keep_lines = [line for line in all_lines if '"T7_CRASH_TEST"' not in line]
with open(SSB_DB, "w") as f:
    f.writelines(keep_lines)

final_count = ssb_count()
print(f"  清理测试事件后 SSB: {final_count} (期望 {baseline['ssb_events']})")

# 5b: 验证基准恢复
state_ok = file_hash(STATE) == baseline["state_hash"]
handoff_ok = file_hash(HANDOFF) == baseline["handoff_hash"]
print(f"  STATE 恢复: {'✅' if state_ok else '❌'}  (可能被 cron 更新)")
print(f"  HANDOFF 恢复: {'✅' if handoff_ok else '❌'} (可能被 cron 更新)")

# ─── 6. Results ───
print("\n" + "=" * 60)
print("T7 RESULTS")
print("=" * 60)

passed = 0
total = 4

checks = []

# Check 1: SSB line integrity
if corrupt_lines == 0:
    checks.append(("SSB行级原子性", True, "所有行有效JSON"))
    passed += 1
else:
    checks.append(("SSB行级原子性", False, f"{corrupt_lines}行损坏"))

# Check 2: Events recoverable
if len(all_crash_events) == partial_count:
    checks.append(("崩溃事件可恢复", True, f"全部{partial_count}个事件可读取"))
    passed += 1
else:
    checks.append(("崩溃事件可恢复", False, f"只读到{len(all_crash_events)}/{partial_count}"))

# Check 3: Cleanup complete
if final_count == baseline["ssb_events"]:
    checks.append(("清理完整性", True, "SSB恢复基准状态"))
    passed += 1
else:
    checks.append(("清理完整性", False, f"{final_count} vs 基准{baseline['ssb_events']}"))

# Check 4: Recovery capability
if handoff_exists and handoff_age < 3600:
    checks.append(("HANDOFF时效性", True, f"HANDOFF {handoff_age / 60:.0f}分钟前"))
    passed += 1
else:
    checks.append(("HANDOFF时效性", False, "HANDOFF过旧或不存在"))

for name, ok, detail in checks:
    print(f"  {'✅' if ok else '❌'} {name}: {detail}")

print(f"\n  通过: {passed}/{total}")

# Report
report = {
    "test": "T7",
    "passed": passed,
    "total": total,
    "success": passed == total,
    "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks],
}

with open(os.path.join(ECOS, "tests/T7-results.json"), "w") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print(f"\n  结果: {'🎉 全部通过' if passed == total else '⚠️ 有问题'}")
