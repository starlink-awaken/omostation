#!/bin/bash
# MetaOS CLAUDE.md 合规性检查
# 检查: 所有模块CLAUDE.md存在 | §0 SSOT声明 | 维护节 | 路径一致性

echo "╔══════════════════════════════════════╗"
echo "║  MetaOS CLAUDE.md 合规检查           ║"
echo "╚══════════════════════════════════════╝"

VAULT="$HOME/Documents/学习进化"
DOCS="$HOME/Documents"
FAIL=0; PASS=0

check() {
  if [ "$2" = "file" ]; then
    [ -s "$1" ] && { ((PASS++)); echo "  ✅ $1"; } || { ((FAIL++)); echo "  ❌ $1 — $3"; }
  elif [ "$2" = "section" ]; then
    grep -q "$3" "$1" 2>/dev/null && { ((PASS++)); echo "  ✅ $(basename $1) 含 $3"; } || { ((FAIL++)); echo "  ❌ $(basename $1) 缺 $3"; }
  fi
}

echo ""; echo "=== 文件存在性检查 ==="
check "$DOCS/驾驶舱/CLAUDE.md" file
check "$DOCS/工具箱/CLAUDE.md" file
check "$DOCS/领域知识库/CLAUDE.md" file
check "$VAULT/CLAUDE.md" file
# Anti-check: 学习进化/CLAUDE_COWORK_GLOBAL.md 应已删除（L0 副本收敛）
if [ -f "$VAULT/CLAUDE_COWORK_GLOBAL.md" ]; then
  ((FAIL++)); echo "  ❌ 冗余L0副本: $VAULT/CLAUDE_COWORK_GLOBAL.md（应删除）"
else
  ((PASS++)); echo "  ✅ L0副本已删除"
fi
check "$VAULT/AGENTS.md" file
# L2 — 正确路径（适配三层 Vault 结构）
check "$VAULT/1-active/自我剖析/CLAUDE.md" file
check "$VAULT/1-active/收件箱/CLAUDE.md" file
check "$VAULT/2-knowledge/体系/CLAUDE.md" file
check "$VAULT/2-knowledge/基建架构/CLAUDE.md" file
check "$VAULT/2-knowledge/创意创作/CLAUDE.md" file
check "$VAULT/2-knowledge/渠道传播/CLAUDE.md" file
check "$VAULT/2-knowledge/经验积累/CLAUDE.md" file
check "$VAULT/3-archive/灵感顿悟/CLAUDE.md" file
check "$VAULT/3-archive/知识订阅/CLAUDE.md" file
check "$VAULT/3-archive/资料库/CLAUDE.md" file
# OMO 迁移验证：旧路径不应存在
if [ -f "$VAULT/2-knowledge/经验积累/OMO/CLAUDE.md" ]; then
  ((FAIL++)); echo "  ❌ 过时文件: 经验积累/OMO/CLAUDE.md（已迁到体系/OMO）"
else
  ((PASS++)); echo "  ✅ 过时文件已清理: 经验积累/OMO"
fi

echo ""; echo "=== §0 SSOT 声明检查（核心域） ==="
for f in "$DOCS/驾驶舱/CLAUDE.md" "$DOCS/工具箱/CLAUDE.md" "$DOCS/领域知识库/CLAUDE.md" \
         "$VAULT/1-active/自我剖析/CLAUDE.md" "$VAULT/2-knowledge/体系/CLAUDE.md" \
         "$VAULT/2-knowledge/创意创作/CLAUDE.md" "$VAULT/2-knowledge/渠道传播/CLAUDE.md" \
         "$VAULT/2-knowledge/经验积累/CLAUDE.md" "$DOCS/工作文档/CLAUDE.md"; do
  check "$f" section "SSOT"
done

echo ""; echo "=== 维护节检查 ==="
# Check L0 is unique (no duplicate CLAUDE_COWORK_GLOBAL in vault)
if [ -f "$VAULT/CLAUDE_COWORK_GLOBAL.md" ]; then
  ((FAIL++)); echo "  ❌ 冗余副本: $VAULT/CLAUDE_COWORK_GLOBAL.md (应已删除)"
else
  ((PASS++)); echo "  ✅ L0 唯一: 无副本"
fi

for f in "$DOCS/驾驶舱/CLAUDE.md" "$DOCS/工具箱/CLAUDE.md" "$VAULT/CLAUDE.md" "$DOCS/家庭生活/CLAUDE.md"; do
  check "$f" section "维护"
done

echo ""; echo "=== L2 §0 SSOT 覆盖率 ==="
for f in "$VAULT/1-active/收件箱/CLAUDE.md" "$VAULT/1-active/自我剖析/CLAUDE.md" \
         "$VAULT/2-knowledge/体系/KEMS/CLAUDE.md" "$VAULT/2-knowledge/体系/OMO/CLAUDE.md" \
         "$VAULT/2-knowledge/体系/四平面知识工程体系/CLAUDE.md" "$VAULT/2-knowledge/体系/基建架构体系/CLAUDE.md" \
         "$VAULT/3-archive/灵感顿悟/CLAUDE.md" "$VAULT/3-archive/知识订阅/CLAUDE.md" \
         "$DOCS/工作文档/国转中心/CLAUDE.md" "$DOCS/工作文档/卫健委/CLAUDE.md"; do
  check "$f" section "§0 SSOT"
done

echo ""; echo "=== X1 审计（变更可追溯）==="
# 检查 Vault 是否在 Git 中
if git -C "$VAULT" rev-parse --git-dir >/dev/null 2>&1; then
  AUDIT_COUNT=$(git -C "$VAULT" log --since="7 days ago" --oneline 2>/dev/null | wc -l | tr -d ' ')
  if [ "$AUDIT_COUNT" -gt 0 ]; then
    ((PASS++)); echo "  ✅ Vault Git 审计: 近7天 $AUDIT_COUNT 次变更"
  else
    ((PASS++)); echo "  ✅ Vault Git 审计: 近7天无变更"
  fi
else
  echo "  ⚠️  Vault 不在 Git 中 — X1 审计不可用（建议: git init $VAULT）"
fi

# 检查 CARDS 审计表
if [ -f "$HOME/Workspace/data/cards/cards.db" ]; then
  HISTORY_COUNT=$(sqlite3 "$HOME/Workspace/data/cards/cards.db" "SELECT COUNT(*) FROM card_history" 2>/dev/null)
  if [ -n "$HISTORY_COUNT" ] && [ "$HISTORY_COUNT" -gt 0 ]; then
    ((PASS++)); echo "  ✅ CARDS 审计: $HISTORY_COUNT 条历史记录"
  else
    ((FAIL++)); echo "  ❌ CARDS 审计表为空"
  fi
fi

echo ""; echo "=== X2 保鲜（CLAUDE.md staleness）==="
STALE_COUNT=0
for f in $(find "$DOCS" -name "CLAUDE.md" -not -path "*/\.*/*" 2>/dev/null); do
  if grep -q "下次审查" "$f" 2>/dev/null; then
    REVIEW_DATE=$(grep "下次审查" "$f" | head -1 | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}')
    if [ -n "$REVIEW_DATE" ]; then
      REVIEW_EPOCH=$(date -j -f "%Y-%m-%d" "$REVIEW_DATE" "+%s" 2>/dev/null)
      NOW_EPOCH=$(date "+%s")
      if [ $((NOW_EPOCH - REVIEW_EPOCH)) -gt $((60*24*3600)) ]; then
        ((STALE_COUNT++))
        echo "  ⚠️  STALE: $(basename $(dirname $f))/CLAUDE.md — 审查日期 $REVIEW_DATE（>2月）"
      fi
    fi
  fi
done
if [ "$STALE_COUNT" -eq 0 ]; then
  ((PASS++)); echo "  ✅ CLAUDE.md 保鲜: 0 个 stale"
else
  ((FAIL++)); echo "  ❌ CLAUDE.md 保鲜: $STALE_COUNT 个 stale（>2月未审查）"
fi

# 检查 hooks.yaml / kos-index.yaml 存在
echo ""; echo "=== L4 新增资产检查 ==="
check "$DOCS/驾驶舱/hooks.yaml" file "生命周期钩子结构化定义"
check "$DOCS/驾驶舱/kos-index.yaml" file "KOS Vault 索引配置"

echo ""; echo "=== CARDS 健康检查 ==="
if [ -f "$HOME/Workspace/data/cards/cards.db" ]; then
  CARD_COUNT=$(sqlite3 "$HOME/Workspace/data/cards/cards.db" "SELECT COUNT(*) FROM cards WHERE status NOT IN ('done','resolved','discarded','archived','superseded','cancelled')" 2>/dev/null)
  if [ -n "$CARD_COUNT" ]; then
    ((PASS++)); echo "  ✅ CARDS DB 存在 · $CARD_COUNT 张活跃卡片"
  else
    ((FAIL++)); echo "  ❌ CARDS DB 不可读"
  fi
else
  ((FAIL++)); echo "  ❌ CARDS DB 不存在"
fi

# CLAUDE.md 保鲜检查 (Phase X1 / DEBT-X-003)
echo ""; echo "=== CLAUDE.md 保鲜检查 ==="
FRESHNESS_SCRIPT="$DOCS/驾驶舱/scripts/check-claude-freshness.py"
if [ -f "$FRESHNESS_SCRIPT" ]; then
  if python3 "$FRESHNESS_SCRIPT" --root "$DOCS" --max-age-days 60 --json 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
stale = data.get('stale', 0)
total = data.get('total', 0)
print(f'  {total} 文件 · {stale} 过期 · 最旧 {max((f[\"age_days\"] for f in data[\"files\"]), default=0)}d')
if stale > 0:
    for f in data['files']:
        if f['stale']:
            print(f'  ⚠️  [{f[\"domain\"]}] {f[\"age_days\"]}d {f[\"path\"]}')
    sys.exit(1)
" 2>/dev/null; then
    ((PASS++)); echo "  ✅ CLAUDE.md 保鲜: 全部新鲜"
  else
    ((FAIL++)); echo "  ❌ CLAUDE.md 保鲜: 存在过期文件"
  fi
else
  echo "  ⏭️  保鲜脚本未部署 ($FRESHNESS_SCRIPT)"
fi

# Run daemon to refresh views
echo "  → 刷新视图..."
cd "$HOME/Workspace" && uv --directory projects/omo run cards daemon 2>&1 | tail -1

echo ""; echo "╔══════════════════════════════════════╗"
echo "║  通过: $PASS   |   失败: $FAIL        ║"
echo "╚══════════════════════════════════════╝"
