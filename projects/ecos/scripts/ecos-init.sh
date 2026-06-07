#!/usr/bin/env bash
# ============================================================================
# eCOS v5 — 跨机器部署初始化 (ecos-init.sh)
# ============================================================================
# 在新机器上运行一次。创建运行时目录、检查依赖、部署 daemon、首次健康检查。
#
# 用法:
#   bash ~/Documents/驾驶舱/scripts/ecos-init.sh
#   bash ~/Documents/驾驶舱/scripts/ecos-init.sh --no-daemon   # 跳过 launchd
#   bash ~/Documents/驾驶舱/scripts/ecos-init.sh --check-only  # 仅检查
# ============================================================================

set -euo pipefail

DOCS="${HOME}/Documents"
ECOS="${HOME}/.ecos"
SCRIPTS="${DOCS}/驾驶舱/scripts"
PASS=0
FAIL=0
WARN=0

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  eCOS v5 — 跨机器部署初始化                              ║"
echo "║  $(date -u '+%Y-%m-%dT%H:%M:%SZ')                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── 参数 ──
NO_DAEMON=false
CHECK_ONLY=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-daemon) NO_DAEMON=true; shift ;;
        --check-only) CHECK_ONLY=true; shift ;;
        *) echo "未知参数: $1"; exit 2 ;;
    esac
done

# ── 检查 1: Documents 存在 ──
echo "── 1/8: 检查 Documents ──"
if [ -f "${DOCS}/CLAUDE_COWORK_GLOBAL.md" ]; then
    echo "  ✅ Documents 就绪"
    ((PASS++))
else
    echo "  ❌ Documents 未就绪 — 请先复制 Documents/ 到本机"
    echo "     从原机器: tar czf ecos-vault.tar.gz ~/Documents/"
    echo "     到本机:   tar xzf ecos-vault.tar.gz -C ~/"
    ((FAIL++))
fi

# ── 检查 2: Python ──
echo "── 2/8: 检查 Python ──"
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 --version 2>&1)
    echo "  ✅ ${PY_VER}"
    ((PASS++))
else
    echo "  ❌ python3 未安装"
    ((FAIL++))
fi

# ── 检查 3: Python 依赖 ──
echo "── 3/8: 检查 Python 依赖 ──"
MISSING=""
python3 -c "import yaml" 2>/dev/null || MISSING="${MISSING} pyyaml"
python3 -c "import sqlite3" 2>/dev/null || MISSING="${MISSING} sqlite3"
python3 -c "import json" 2>/dev/null || MISSING="${MISSING} json"
python3 -c "import subprocess" 2>/dev/null || MISSING="${MISSING} subprocess"

# 可选依赖
python3 -c "import mcp" 2>/dev/null || echo "  ⏭️  mcp 未安装 (runtime-mcp-server 需要)"
python3 -c "import watchdog" 2>/dev/null || echo "  ⏭️  watchdog 未安装 (event-watcher 降级需要)"

if [ -z "$MISSING" ]; then
    echo "  ✅ 全部核心依赖就绪"
    ((PASS++))
else
    echo "  ⚠️  缺失: ${MISSING}"
    echo "     运行: pip3 install ${MISSING}"
    ((WARN++))
fi

# ── 检查 4: ~/.ecos/ 目录 ──
echo "── 4/8: 初始化 ~/.ecos/ ──"
mkdir -p "${ECOS}/scripts"
mkdir -p "${ECOS}/runtime"
mkdir -p "${ECOS}/events"
mkdir -p "${ECOS}/sla"
mkdir -p "${ECOS}/sessions"
mkdir -p "${ECOS}/audit/minerva"
echo "  ✅ ~/.ecos/ 目录就绪"
((PASS++))

# ── 检查 5: runtime registry ──
echo "── 5/8: 初始化 Runtime Registry ──"
REGISTRY="${ECOS}/runtime/registry.json"
if [ ! -f "$REGISTRY" ]; then
    echo '{"services":[{"name":"ecos-daemon","type":"daemon","status":"active","registered_at":"'"$(date -u +'%Y-%m-%dT%H:%M:%SZ')"'"}],"updated_at":"'"$(date -u +'%Y-%m-%dT%H:%M:%SZ')"'"}' > "$REGISTRY"
    echo "  ✅ Registry 初始化完成"
else
    echo "  ✅ Registry 已存在"
fi
((PASS++))

# ── 检查 6: 脚本可执行性 ──
echo "── 6/8: 验证关键脚本 ──"
KEY_SCRIPTS=(
    "ecos-health-check.py"
    "ecos-brief.py"
    "ecos-sla-tracker.py"
    "ecos-daemon.py"
    "ecos-whoami.py"
)
SCRIPTS_OK=0
for s in "${KEY_SCRIPTS[@]}"; do
    if [ -f "${SCRIPTS}/${s}" ]; then
        ((SCRIPTS_OK++))
    fi
done
echo "  ✅ ${SCRIPTS_OK}/${#KEY_SCRIPTS[@]} 关键脚本就绪"
((PASS++))

# ── 检查 7: launchd daemon ──
echo "── 7/8: 部署 Daemon ──"
if [ "$NO_DAEMON" = false ] && [ -d "${HOME}/Library/LaunchAgents" ]; then
    PLIST_SRC="${ECOS}/com.ecos.daemon.plist"
    PLIST_DST="${HOME}/Library/LaunchAgents/com.ecos.daemon.plist"
    if [ -f "$PLIST_SRC" ]; then
        cp "$PLIST_SRC" "$PLIST_DST"
        if launchctl list | grep -q "com.ecos.daemon" 2>/dev/null; then
            echo "  ✅ Daemon 已在运行"
        else
            launchctl load "$PLIST_DST" 2>/dev/null && echo "  ✅ Daemon 已加载" || echo "  ⏭️  launchctl 不可用 (下次登录自动加载)"
        fi
    else
        echo "  ⚠️  plist 不存在: ${PLIST_SRC}"
        ((WARN++))
    fi
else
    echo "  ⏭️  跳过 daemon 部署"
fi
((PASS++))

# ── 检查 8: 首次健康检查 ──
echo "── 8/8: 首次健康检查 ──"
if [ "$CHECK_ONLY" = false ]; then
    if python3 "${SCRIPTS}/ecos-health-check.py" 2>/dev/null | grep -q "全部健康"; then
        echo "  ✅ 系统就绪"
    else
        echo "  ⚠️  健康检查未通过 — 运行 python3 ${SCRIPTS}/ecos-health-check.py 查看详情"
        ((WARN++))
    fi
else
    echo "  ⏭️  跳过 (--check-only)"
fi
((PASS++))

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  部署完成                                               ║"
echo "║  通过: ${PASS}  |  告警: ${WARN}  |  失败: ${FAIL}                   ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  下一步:"
echo "    python3 ${SCRIPTS}/ecos-whoami.py      # 系统自述"
echo "    python3 ${SCRIPTS}/ecos-brief.py --force  # 会话简报"
echo "    cat ${DOCS}/驾驶舱/OPS.md                # 运营手册"
echo ""

exit $FAIL
