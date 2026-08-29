#!/bin/bash
# ============================================================
# 2026-08-02 Documents 文档治理脚本 — 目录健康检查与清理
# 用法: bash ~/Documents/_inbox/2026-08-02-文档治理.sh          # 仅诊断
#       bash ~/Documents/_inbox/2026-08-02-文档治理.sh --clean   # 诊断 + 删除空目录
# 覆盖: ①空目录 ②_inbox 滞留 ③顶层散落 ④大文件审计
# ============================================================
set -u
DOCS=~/Documents
CLEAN="${1:-}"

echo "═══════════════════════════════════════════"
echo " Documents 文档治理诊断 ($(date +%F))"
echo "═══════════════════════════════════════════"

echo ""
echo "【1】空目录扫描（清理候选）"
EMPTY=$(find "$DOCS" -type d -empty \
  -not -path "*/.git/*" -not -path "*/.venv/*" -not -path "*/node_modules/*" \
  -not -path "*/.Trash/*" -not -path "*/Zotero/*" 2>/dev/null)
if [ -z "$EMPTY" ]; then
  echo "  ✅ 无空目录"
else
  N=$(echo "$EMPTY" | wc -l | tr -d ' ')
  echo "  📋 发现 $N 个空目录:"
  echo "$EMPTY" | sed "s|$DOCS/|    |" | head -40
  if [ "$CLEAN" = "--clean" ]; then
    echo "$EMPTY" | while read -r d; do
      rmdir "$d" 2>/dev/null && echo "  🗑 已删: ${d#$DOCS/}"
    done
  else
    echo "  ⚠️ 加 --clean 参数执行删除"
  fi
fi

echo ""
echo "【2】_inbox 缓冲区滞留（>3 天未路由 = 长草）"
STALE=$(find "$DOCS/_inbox" -maxdepth 1 -type f -mtime +3 \
  ! -name "FLOW-LOG.md" ! -name "hourly_runner*" ! -name ".DS_Store" \
  ! -name "*.sh" ! -name "2026-08-02*" 2>/dev/null)
if [ -z "$STALE" ]; then
  echo "  ✅ 无滞留（缓冲区干净）"
else
  echo "$STALE" | sed "s|$DOCS/|    |"
  echo "  ⚠️ 建议归档到 _inbox/_archive/ 或确认路由"
fi

echo ""
echo "【3】顶层散落文件（Documents 根下非域文件）"
TOP=$(find "$DOCS" -maxdepth 1 -type f 2>/dev/null)
if [ -z "$TOP" ]; then
  echo "  ✅ 顶层干净（仅 8 域目录 + 应用目录）"
else
  echo "$TOP" | sed "s|$DOCS/|    |" | head -10
  echo "  ⚠️ 顶层文件应移入对应域或归档"
fi

echo ""
echo "【4】大文件审计（>200MB，存储卫生，排除 Zotero/venv/git）"
BIG=$(find "$DOCS" -type f -size +200M \
  -not -path "*/.venv/*" -not -path "*/.git/*" -not -path "*/node_modules/*" \
  -not -path "*/Zotero/*" -not -path "*/.Trash/*" 2>/dev/null)
if [ -z "$BIG" ]; then
  echo "  ✅ 无大文件"
else
  echo "$BIG" | while read -r f; do
    sz=$(du -h "$f" 2>/dev/null | cut -f1)
    echo "  📦 $sz  ${f#$DOCS/}"
  done | head -20
fi

echo ""
echo "═══════════════════════════════════════════"
echo " 诊断完成。清理空目录加 --clean 参数重跑"
echo "═══════════════════════════════════════════"
