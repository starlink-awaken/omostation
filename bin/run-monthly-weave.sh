#!/bin/bash
# 概念孤岛编织 — 月度维护封装（2026-10-09 按 MAINTENANCE-概念孤岛编织.md §六之一 重建）
# 链路: detect → mesh → bridge → exec-bridge → report + Workspace decay 只读扫描
#
# ⚠️ 位置变更（TCC 根因修复）：原封装在 ~/Documents 内，2026-08-01 起 launchd
#    因 macOS TCC 拦截（Operation not permitted）无法执行 Documents 内脚本。
#    本封装改放 ~/Workspace/bin/（launchd 可执行区）。launchd 自动运行仍需在
#    系统设置→隐私与安全性→完全磁盘访问权限 中授予 /bin/bash（或改用
#    grant-full-disk-access 的解释器），否则子进程读写 ~/Documents 仍会被拦。
#    launchd 自身日志落 ~/Workspace/logs/（同因）；vault 日志由脚本内容写入。

set -u
VAULT="$HOME/Documents/@学习进化"
# 2026-10-10：日志迁 runtime state 目录（L4-CONTENT-009：派生/可变存储不滞留 Documents）
LOG_DIR="$HOME/.local/state/omostation/runtime/control/logs"
LOG="$LOG_DIR/concept-weave.monthly.log"
HISTORY="$LOG_DIR/concept-weave.history.json"
WEAVE="$HOME/Workspace/bin/concept-weave.py"
RUNTIME="$HOME/Workspace/projects/runtime/.venv/bin/runtime"
export PATH="$PATH:/usr/local/bin"

ts() { date "+%Y-%m-%d %H:%M:%S"; }
mkdir -p "$LOG_DIR" "$HOME/Workspace/logs"

# runtime documents-plane 的可选 job（learning-decay 等）按 binding registry 声明注册，
# 必须显式指向 SSOT，否则静默不注册（2026-10-09 修复）
export DOCUMENTS_DOMAIN_PROJECTS_REGISTRY="$HOME/Workspace/.omo/_truth/registry/documents-domain-projects.yaml"

echo "────────────────" >> "$LOG"
echo "===== [$(ts)] 概念库月度维护开始 =====" >> "$LOG"

cd "$VAULT" || { echo "[$(ts)] 无法进入 vault" >> "$LOG"; exit 2; }

python3 "$WEAVE" detect      >> "$LOG" 2>&1
python3 "$WEAVE" mesh        >> "$LOG" 2>&1
python3 "$WEAVE" bridge      >> "$LOG" 2>&1
python3 "$WEAVE" exec-bridge >> "$LOG" 2>&1
REPORT=$(python3 "$WEAVE" report 2>&1)
echo "$REPORT" >> "$LOG"

ORPHANS=$(printf '%s' "$REPORT" | /usr/bin/grep -o '孤儿: [0-9]*' | /usr/bin/grep -o '[0-9]*')
CONN=$(printf '%s' "$REPORT" | /usr/bin/grep -o '连通率: [0-9.]*%' | /usr/bin/grep -o '[0-9.]*')
ORPHANS=${ORPHANS:-0}
CONN=${CONN:-0.0}

# ── decay 只读健康度扫描（绝不自动 apply，见手册安全边界）──
DECAY_CAND=0
if [ -x "$RUNTIME" ]; then
  DECAY_OUT=$("$RUNTIME" documents run documents-learning-decay --json 2>/dev/null | \
    python3 -c "import json,sys;print(json.load(sys.stdin).get('stdout',''))" 2>/dev/null || true)
  if [ -n "$DECAY_OUT" ]; then
    printf '%s\n' "$DECAY_OUT" >> "$LOG"
    DECAY_CAND=$(printf '%s' "$DECAY_OUT" | /usr/bin/grep -cE '🟠|🔴' || true)
  fi
fi

# ── 跨月对比（history JSON：ts/month/orphans/decay/connectivity）──
MONTH=$(date "+%Y-%m")
python3 - "$HISTORY" "$MONTH" "$ORPHANS" "$DECAY_CAND" "$CONN" <<'PYEOF' >> "$LOG" 2>&1
import json, sys, datetime
from pathlib import Path
path, month, orphans, decay, conn = Path(sys.argv[1]), *sys.argv[2:]
raw = path.read_text() if path.exists() else ""
data = json.loads(raw) if raw.strip() else {}
runs = data.get("runs", []) if isinstance(data, dict) else data  # 兼容 {"runs": [...]} 与裸列表
prev = next((e for e in reversed(runs) if isinstance(e, dict) and e.get("month") != month), None)
runs.append({"ts": datetime.datetime.now().isoformat(timespec="seconds"),
             "month": month, "orphans": int(orphans), "decay": int(decay), "connectivity": float(conn)})
out = data if isinstance(data, dict) else {}
out["runs"] = runs
path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
def arrow(now, before, lower_better):
    if before is None: return ""
    return "↓改善" if now < before else ("↑恶化" if now > before else "→持平")
if prev:
    print(f"跨月对比: 上月({prev['month']}) 孤岛{prev.get('orphans')} 衰减{prev.get('decay')} 连通{prev.get('connectivity')}%"
          f" → 本月 孤岛{orphans}{arrow(int(orphans), prev.get('orphans'), True)}"
          f" 衰减{decay}{arrow(int(decay), prev.get('decay'), True)}"
          f" 连通{conn}%{arrow(float(conn), prev.get('connectivity'), False)}")
else:
    print(f"跨月对比: 首次记录({month}) 孤岛{orphans} 衰减{decay} 连通{conn}%")
PYEOF

# ── 通知判定：孤岛/衰减候选 >0 才弹窗，健康则静默 ──
echo "[$(ts)] 通知判定: 孤岛=$ORPHANS 衰减候选=$DECAY_CAND → $([ "$ORPHANS" -gt 0 ] || [ "$DECAY_CAND" -gt 0 ] && echo 弹窗 || echo 静默（健康）)" >> "$LOG"
if [ "$ORPHANS" -gt 0 ] || [ "$DECAY_CAND" -gt 0 ]; then
  osascript -e "display notification \"孤岛=$ORPHANS 衰减候选=$DECAY_CAND 连通率=$CONN%\" with title \"概念库月度维护\" subtitle \"需要人工编织\"" >/dev/null 2>&1 || true
fi

echo "===== [$(ts)] 概念库月度维护完成 =====" >> "$LOG"
