#!/bin/bash
# ============================================================
# 2026-08-02 async-audit.py 心跳阈值修复
# 作用: 增加低频任务豁免 — 心跳文件名以 .low 结尾的任务(双周/月度)
#       跳过 8 天心跳检查，避免误报「心跳超 8 天」
# 用法: bash ~/Documents/_inbox/2026-08-02-async-audit-心跳补丁.sh
# 安全: 目标代码段不存在时安全退出(不破坏文件); 幂等可重跑
# ============================================================
set -e
TARGET=~/Documents/@公共/_runtime/async-audit.py

echo "======================================"
echo "[1/1] 应用心跳豁免补丁"
echo "======================================"
python3 - "$TARGET" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
text = p.read_text(encoding="utf-8")
OLD = '''    hb = [f for f in hb_dir.glob("*") if f.name.lower() != "readme.md"] if hb_dir.is_dir() else []
    hb_note = f"Claude 心跳 {len(hb)} 个已接入" if hb else "Claude 定时任务心跳未接入 (灰区, 见 heartbeats/README)"
    for f in hb:
        if now.timestamp() - f.stat().st_mtime > 8 * 86400:
            issues.append(f"claude:{f.name} 心跳超 8 天")'''
NEW = '''    hb = [f for f in hb_dir.glob("*") if f.name.lower() != "readme.md"] if hb_dir.is_dir() else []
    # 低频豁免 (2026-08-02): 心跳文件名以 .low 结尾(双周/月度任务)跳过 8 天检查
    hb_live = [f for f in hb if not f.name.endswith(".low")]
    hb_note = f"Claude 心跳 {len(hb_live)} 个已接入" if hb_live else "Claude 定时任务心跳未接入 (灰区, 见 heartbeats/README)"
    for f in hb_live:
        if now.timestamp() - f.stat().st_mtime > 8 * 86400:
            issues.append(f"claude:{f.name} 心跳超 8 天")'''
if OLD not in text:
    print("❌ 未找到目标代码段(应在行 221-225)，文件可能已被修改，请人工检查 async-audit.py health()")
    sys.exit(1)
p.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
print("  ✅ 补丁已应用: 低频心跳(.low 后缀)豁免")
PY

echo ""
echo "======================================"
echo "[验证]"
echo "======================================"
grep -n "\.low" "$TARGET"
echo ""
echo "✅ 完成。约定: 低频任务(双周/月度)心跳写为 touch heartbeats/<任务名>.low"
echo "   （非 .low 结尾的心跳仍按 8 天阈值检查，行为不变）"
