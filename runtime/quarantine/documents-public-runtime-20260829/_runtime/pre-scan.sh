#!/bin/bash
# pre-scan.sh — KEMS v7.1 治理前扫描模板
# ========================================
# 解决问题: 认知偏差误判(看 1 文件就下结论)
# 落地位置: @公共/_runtime/pre-scan.sh
# 触发: 任何"治理 / 评估 / 决策"前
# 原则: "扫描优先于结论"
#
# 用法:
#   bash pre-scan.sh <target_path> [max_depth]
#   bash pre-scan.sh @工作文档/合同法规 3
#   bash pre-scan.sh @工作文档/卫健委 4
#
# 输出: 深度结构 + 关键统计 + 风险提示
# ========================================

set -e

TARGET="${1:-.}"
MAX_DEPTH="${2:-3}"

if [ ! -d "$TARGET" ]; then
    echo "❌ 目标路径不存在: $TARGET"
    exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  KEMS v7.1 · 治理前扫描(M-α 机制)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  目标: $TARGET"
echo "  最大深度: $MAX_DEPTH"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

# 1. 基础统计
echo "## §1 基础统计"
echo
echo "  📁 总目录数:$(find "$TARGET" -type d 2>/dev/null | wc -l)"
echo "  📄 总文件数:$(find "$TARGET" -type f 2>/dev/null | wc -l)"
echo "  📝 .md 文件:$(find "$TARGET" -name "*.md" 2>/dev/null | wc -l)"
echo "  🐍 .py 文件:$(find "$TARGET" -name "*.py" 2>/dev/null | wc -l)"
echo "  📊 .yaml:$(find "$TARGET" -name "*.yaml" -o -name "*.yml" 2>/dev/null | wc -l)"
echo "  📦 其他:$(find "$TARGET" -type f ! -name "*.md" ! -name "*.py" ! -name "*.yaml" ! -name "*.yml" 2>/dev/null | wc -l)"
echo

# 2. 深度结构(关键)
echo "## §2 深度结构(前 $MAX_DEPTH 层)"
echo
find "$TARGET" -maxdepth "$MAX_DEPTH" -type d 2>/dev/null | sort | while read dir; do
    rel="${dir#$TARGET/}"
    [ -z "$rel" ] && rel="(root)"
    n_md=$(find "$dir" -maxdepth 1 -name "*.md" 2>/dev/null | wc -l)
    n_f=$(find "$dir" -maxdepth 1 -type f 2>/dev/null | wc -l)
    n_d=$(find "$dir" -maxdepth 1 -type d 2>/dev/null | wc -l)
    [ "$n_d" -gt 0 ] && n_d=$((n_d - 1))  # 排除自己
    printf "  %-50s  📁%-3d  📄%-4d(md %d)\n" "$rel" "$n_d" "$n_f" "$n_md"
done
echo

# 3. KEMS 六平面扫描(如果目标在 Documents 工作区)
echo "## §3 KEMS 六平面扫描"
PLANES=("_control" "_meta" "_knowledge" "_entities" "_runtime" "_storage")
echo
printf "  %-30s " "(目标域)"
for p in "${PLANES[@]}"; do
    printf "%-12s " "$p"
done
echo
echo "  ──────────────────────────────────────────────────────────────"
find "$TARGET" -maxdepth 2 -type d -name "_*" 2>/dev/null | sort -u | while read plane_dir; do
    rel="${plane_dir#$TARGET/}"
    parent=$(dirname "$rel")
    parent="${parent#$TARGET/}"
    parent="${parent#./}"
    [ -z "$parent" ] && parent="(root)"
    printf "  %-30s " "$parent"
    for p in "${PLANES[@]}"; do
        if [ -d "$TARGET/$parent/$p" ]; then
            printf "✅ %-10s " ""
        else
            printf "❌ %-10s " ""
        fi
    done
    echo
done
echo

# 4. 控制器扫描(KEMS 7/7 跨域部署)
echo "## §4 控制器扫描(KEMS v7.0 兑现)"
echo
echo "  控制器: sensors.md / control-rules.md / executor-rules.md / l4-kernel.md"
echo
for d in $(find "$TARGET" -maxdepth 2 -type d -name "_control" 2>/dev/null); do
    parent=$(dirname "$d")
    parent="${parent#$TARGET/}"
    parent="${parent#./}"
    [ -z "$parent" ] && parent="(root)"
    n=0
    ctrl_status=""
    for c in sensors.md control-rules.md executor-rules.md l4-kernel.md; do
        if [ -f "$d/$c" ]; then
            ctrl_status="$ctrl_status✅ "
            n=$((n + 1))
        else
            ctrl_status="$ctrl_status❌ "
        fi
    done
    printf "  %-30s  %s  (%d/4)\n" "$parent" "$ctrl_status" "$n"
done
echo

# 5. 特殊文件检测
echo "## §5 关键文件存在性"
echo
for f in CLAUDE.md STATE.md STATUS.md signals.md; do
    if [ -f "$TARGET/$f" ]; then
        echo "  ✅ $f"
    else
        echo "  ❌ $f(缺失)"
    fi
done
echo

# 6. 风险提示
echo "## §6 风险提示(基于扫描结果)"
echo

# 风险 1:文件数 < 5 但子域多
md_count=$(find "$TARGET" -name "*.md" 2>/dev/null | wc -l)
sub_count=$(find "$TARGET" -maxdepth 1 -type d 2>/dev/null | wc -l)
if [ "$md_count" -lt 5 ] && [ "$sub_count" -gt 3 ]; then
    echo "  ⚠️  风险 1:md 文件 < 5 但子目录 > 3 → 可能是'僵尸域'误判"
    echo "     验证:请深入扫描每个子目录的真实文件数"
    echo
fi

# 风险 2:声称 vs 实际
if grep -q "已实现\|全部\|7/7\|完成" "$TARGET"/*.md 2>/dev/null; then
    echo "  ⚠️  风险 2:CLAUDE.md 含'已实现/全部/7/7'等宣称词"
    echo "     验证:用 claim-audit.py 验证'宣称 vs 实际'"
    echo
fi

# 风险 3:CLAUDE.md 与实际结构不符
if [ -f "$TARGET/CLAUDE.md" ]; then
    claim_md=$(grep -c "\.md" "$TARGET/CLAUDE.md" 2>/dev/null || echo 0)
    actual_md=$(find "$TARGET" -name "*.md" 2>/dev/null | wc -l)
    if [ "$actual_md" -gt 10 ] && [ "$claim_md" -eq 0 ]; then
        echo "  ⚠️  风险 3:CLAUDE.md 提及其他 md 但实际目录无相关文件"
        echo "     验证:核对 CLAUDE.md 引用的文件路径"
        echo
    fi
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  扫描完成 · 在做任何判断前,请先核对 §1-§6"
echo "  KEMS v7.1 原则: 扫描优先于结论"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
