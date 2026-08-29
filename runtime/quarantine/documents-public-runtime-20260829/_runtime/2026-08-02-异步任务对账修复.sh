#!/bin/bash
# ============================================================
# 2026-08-02 异步任务对账修复 v2 — 重建 async-tasks.yaml 的 claude 段
# 用法: bash ~/Documents/_inbox/2026-08-02-异步任务对账修复.sh
# 背景: v1 脚本清理了 33 个僵尸目录, 但补登逻辑破坏了登记表结构。
#       v2 采用重建方案: 删除全部 claude 段 → 写入 12 条权威清单 → 其他段原样保留。
# 安全: 幂等, 可重复运行; 非 claude 段(cron/launchd/cronsvc/cronsrc) 不做任何改动。
# ============================================================
set -u

YAML=~/Documents/@驾驶舱/_control/async-tasks.yaml

echo "======================================"
echo "[1/1] 重建 async-tasks.yaml 的 claude 段"
echo "======================================"
if [ ! -f "$YAML" ]; then
  echo "  ❌ $YAML 不存在，先跑 async-audit --bootstrap"
  exit 1
fi

python3 - "$YAML" <<'PY'
import re, pathlib, sys
p = pathlib.Path(sys.argv[1])
SCHED = "/Users/xiamingxing/Documents/Claude/Scheduled"
# 权威 12 条（调度器 API 2026-08-02 确认）
TASKS = [
 ("neirong-caiji", "国转中心域", "内容采集周报 — AI订阅源RSS + 国转中心公众号存档（周二11:00）"),
 ("zhengce-jianbao", "国转中心域", "政策情报简报 V2 — 三源混合摄入（一/三/五12:02）"),
 ("sanyi-friday-report", "卫健委域", "三医联动·周五综合周报（周五15:00）"),
 ("vault-index-sync", "学习进化域", "INDEX 同步 — 月度执行（当月第一个周六）"),
 ("vault-daily-health", "学习进化域", "每日系统健康巡检 — Vault + 6域STATUS + DASHBOARD（每日7:30）"),
 ("weekly-compile-loop", "学习进化域", "知识编译循环 — inbox 扫描提炼概念卡与教训（周一8:30，写操作）"),
 ("daily-diet-reminder", "家庭生活域", "每日减重提醒 — 饮食+运动+16+8窗口（每日8:20）"),
 ("l4-governance-weekly", "l4-governance", "每周五 L4 治理周检 — domain-sync + session-brief + signals-rotate + CARDS 逾期扫描"),
 ("gzh-health-fetch", "卫健委域", "每日卫健委公众号增量抓取（健康房山/北京/中国，每日11:03）"),
 ("weijian-daily-health", "卫健委域", "每日卫健委健康巡检 — KEMS双检 + Dashboard（每日8:05）"),
 ("monday-kems-audit", "学习进化域", "周一 KEMS 深度审计 — G18 全量 + 概念衰减扫描（周一6:30）"),
 ("monday-vault-health", "学习进化域", "周一全域健康巡检 — 新鲜度 + 卫健委控制回路/双周审计 + 双周收敛（周一9:00）"),
]
lines = p.read_text(encoding="utf-8").splitlines()
# 1. 删除所有 claude 条目（key + 缩进字段，跨空行吸收悬空字段）
out, i, n = [], 0, len(lines)
while i < n:
    ln = lines[i]
    if re.match(r"^  claude:[^:]*:$", ln):
        i += 1
        while i < n and (re.match(r"^    ", lines[i]) or lines[i].strip() == ""):
            i += 1
        continue
    out.append(ln); i += 1
lines = out
# 2. 插入权威 claude 段到第一个 cron: 之前
anchor = next((i for i, ln in enumerate(lines) if re.match(r"^  cron:", ln)), None)
blk = []
for name, owner, purpose in TASKS:
    blk += [f"  claude:{name}:", "    plane: claude-scheduled",
            f'    detail: "{SCHED}/{name}"', f"    owner: {owner}",
            f"    purpose: {purpose}", '    log: "Claude App 内部"', ""]
if anchor is not None:
    lines = lines[:anchor] + blk + lines[anchor:]
else:
    lines = lines + blk
p.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
print(f"  ✅ claude 段重建为 {len(TASKS)} 条权威清单")
print(f"  ✅ 非 claude 段（cron/launchd/cronsvc/cronsrc）原样保留")
PY

echo ""
echo "======================================"
echo "[验证] 异步任务对账"
echo "======================================"
python3 ~/Documents/@公共/_runtime/async-audit.py

echo ""
echo "✅ 修复完成。若仍有漂移，把输出贴给 Agent。"
