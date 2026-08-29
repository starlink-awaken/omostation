#!/bin/bash
# ============================================================
# 2026-08-02 定时任务清理脚本 — mac 侧一键执行
# 用法: bash ~/Documents/_inbox/2026-08-02-定时任务清理.sh
# 作用: ①删除 Scheduled 僵尸目录 ②补登 3 个新合并任务 ③验证对账
# 安全: 白名单保护 12 个活跃任务，其余目录全部清理（幂等，可重复运行）
# ============================================================
set -u

SCHED=~/Documents/Claude/Scheduled
YAML=~/Documents/@驾驶舱/_control/async-tasks.yaml
# 活跃任务白名单（调度器 API 2026-08-02 确认 · 勿删）
KEEP="neirong-caiji zhengce-jianbao sanyi-friday-report vault-index-sync vault-daily-health weekly-compile-loop daily-diet-reminder l4-governance-weekly gzh-health-fetch weijian-daily-health monday-kems-audit monday-vault-health"

echo "======================================"
echo "[1/3] 清理 Scheduled 僵尸目录"
echo "      白名单: $(echo $KEEP | wc -w) 个活跃任务"
echo "======================================"
if [ ! -d "$SCHED" ]; then
  echo "  ❌ $SCHED 不存在，跳过"
else
  cd "$SCHED" || exit 1
  REMOVED=0
  for d in */; do
    d="${d%/}"
    if ! echo "$KEEP" | tr ' ' '\n' | grep -qx "$d"; then
      rm -rf "$d" && echo "  已删除: $d" && REMOVED=$((REMOVED+1))
    fi
  done
  echo "  ✅ 共删除 $REMOVED 个僵尸目录"
fi

echo ""
echo "======================================"
echo "[2/3] 补登 3 个新合并任务到 async-tasks.yaml"
echo "======================================"
if [ ! -f "$YAML" ]; then
  echo "  ❌ $YAML 不存在，跳过（先跑 async-audit --bootstrap）"
else
  python3 - "$YAML" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1])
t = p.read_text(encoding="utf-8")
entries = [
    ("claude:monday-kems-audit", "  claude:monday-vault-comprehensive:",
     '''  claude:monday-kems-audit:
    plane: claude-scheduled
    detail: "/Users/xiamingxing/Documents/Claude/Scheduled/monday-kems-audit"
    owner: l4-governance(2026-08-02合并建)
    purpose: 周一 KEMS 深度审计 — G18 全量 + 概念衰减扫描
    log: "Claude App 内部"
'''),
    ("claude:monday-vault-health", "  claude:monday-vault-comprehensive:",
     '''  claude:monday-vault-health:
    plane: claude-scheduled
    detail: "/Users/xiamingxing/Documents/Claude/Scheduled/monday-vault-health"
    owner: l4-governance(2026-08-02合并建)
    purpose: 周一全域健康巡检 — 新鲜度 + 卫健委控制回路/双周审计 + 双周收敛
    log: "Claude App 内部"
'''),
    ("claude:weijian-daily-health", "  claude:weijian-kems-daily:",
     '''  claude:weijian-daily-health:
    plane: claude-scheduled
    detail: "/Users/xiamingxing/Documents/Claude/Scheduled/weijian-daily-health"
    owner: 卫健委域(2026-08-02合并建)
    purpose: 每日卫健委健康巡检 — KEMS双检 + Dashboard 生成与汇报
    log: "Claude App 内部"
'''),
]
changed = False
for key, anchor, blk in entries:
    if f"{key}:" in t:
        print(f"  跳过(已存在): {key}")
    elif anchor in t:
        t = t.replace(anchor, anchor + "\n" + blk, 1)
        changed = True
        print(f"  已登记: {key}")
    else:
        print(f"  ⚠️ 锚点未找到: {key}")
p.write_text(t, encoding="utf-8")
print("  ✅ 登记表更新完成" if changed else "  无需变更")
PY
fi

echo ""
echo "======================================"
echo "[3/3] 异步任务对账验证"
echo "======================================"
python3 ~/Documents/@公共/_runtime/async-audit.py

echo ""
echo "✅ 清理流程结束。若上一步输出仍有 ❌，按提示处理对应项。"
