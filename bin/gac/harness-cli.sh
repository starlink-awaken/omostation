#!/bin/bash
# harness-cli.sh — Harness 全生命周期合规 CLI 入口
#
# 用法:
#   bin/gac/harness-cli.sh compliance    # 运行 12 章节合规检查
#   bin/gac/harness-cli.sh mof           # 运行 MOF 约束联动检查
#   bin/gac/harness-cli.sh omo           # 运行 OMO 状态同步检查
#   bin/gac/harness-cli.sh enforce       # 运行统一约束与驱动
#   bin/gac/harness-cli.sh perceive      # 运行架构感知预编辑检查
#   bin/gac/harness-cli.sh full          # 运行全量检查 (所有引擎)
#   bin/gac/harness-cli.sh status        # 显示 Harness 合规状态总览
#
# BOS URI 映射:
#   bos://harness/compliance/check   → harness-cli.sh compliance
#   bos://harness/mof/bridge          → harness-cli.sh mof
#   bos://harness/omo/bridge          → harness-cli.sh omo
#   bos://harness/constraint/enforce  → harness-cli.sh enforce
#   bos://harness/architecture/perceive → harness-cli.sh perceive

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CMD="${1:-help}"
shift || true

case "$CMD" in
  compliance)
    echo "=== Harness 12 章节合规检查 ==="
    python3 "$ROOT/bin/gac/harness-compliance-check.py" --report
    ;;
  mof)
    echo "=== MOF 约束联动检查 ==="
    python3 "$ROOT/bin/gac/harness-mof-bridge.py"
    ;;
  omo)
    echo "=== OMO 状态同步检查 ==="
    python3 "$ROOT/bin/gac/harness-omo-bridge.py"
    ;;
  enforce)
    echo "=== 统一约束与驱动 (CI 模式) ==="
    python3 "$ROOT/bin/gac/harness-constraint-enforcer.py" --ci
    ;;
  perceive)
    echo "=== 架构感知预编辑检查 ==="
    "$ROOT/.githooks/pre-edit-architecture.sh"
    ;;
  full)
    echo "=== 全量合规检查 ==="
    echo ""
    echo "── 1. Architecture Check ──"
    python3 "$ROOT/bin/gac/architecture-check.py" --gate
    echo ""
    echo "── 2. Harness Compliance ──"
    python3 "$ROOT/bin/gac/harness-compliance-check.py" --gate
    echo ""
    echo "── 3. MOF Bridge ──"
    python3 "$ROOT/bin/gac/harness-mof-bridge.py" --state
    echo ""
    echo "── 4. OMO Bridge ──"
    python3 "$ROOT/bin/gac/harness-omo-bridge.py"
    echo ""
    echo "── 5. Constraint Enforcer ──"
    python3 "$ROOT/bin/gac/harness-constraint-enforcer.py" --ci
    echo ""
    echo "✅ 全量检查完成"
    ;;
  status)
    echo "=== Harness 合规状态总览 ==="
    echo ""
    echo "── 架构标准 ──"
    python3 "$ROOT/bin/gac/architecture-check.py" --json 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
errors = len(data.get('errors', []))
warnings = len(data.get('warnings', []))
print(f'  错误: {errors}, 警告: {warnings}')
" 2>/dev/null || echo "  (检查失败)"
    echo ""
    echo "── Harness 合规 ──"
    python3 "$ROOT/bin/gac/harness-compliance-check.py" --json 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
errors = len(data.get('errors', []))
warnings = len(data.get('warnings', []))
print(f'  错误: {errors}, 警告: {warnings}')
" 2>/dev/null || echo "  (检查失败)"
    echo ""
    echo "── MOF 联动 ──"
    python3 "$ROOT/bin/gac/harness-mof-bridge.py" --json 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
errors = len(data.get('errors', []))
warnings = len(data.get('warnings', []))
print(f'  错误: {errors}, 警告: {warnings}')
" 2>/dev/null || echo "  (检查失败)"
    echo ""
    echo "── OMO 同步 ──"
    python3 "$ROOT/bin/gac/harness-omo-bridge.py" --json 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
errors = len(data.get('errors', []))
warnings = len(data.get('warnings', []))
print(f'  错误: {errors}, 警告: {warnings}')
" 2>/dev/null || echo "  (检查失败)"
    ;;
  help|--help|-h)
    echo "Harness 全生命周期合规 CLI"
    echo ""
    echo "用法: bin/gac/harness-cli.sh <command>"
    echo ""
    echo "命令:"
    echo "  compliance   运行 12 章节合规检查"
    echo "  mof          运行 MOF 约束联动检查"
    echo "  omo          运行 OMO 状态同步检查"
    echo "  enforce      运行统一约束与驱动"
    echo "  perceive     运行架构感知预编辑检查"
    echo "  full         运行全量检查 (所有引擎)"
    echo "  status       显示合规状态总览"
    echo "  help         显示此帮助信息"
    ;;
  *)
    echo "未知命令: $CMD"
    echo "运行 'bin/gac/harness-cli.sh help' 查看可用命令"
    exit 1
    ;;
esac
