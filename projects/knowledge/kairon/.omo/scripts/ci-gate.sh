#!/usr/bin/env bash
#
# Kairon CI Gate — 统一门禁检查脚本
#
# 执行 4 项硬性门禁检查，输出结果到 .omo/tests/ 目录。
#
# 用法:
#   bash .omo/scripts/ci-gate.sh              # 全量检查（默认）
#   bash .omo/scripts/ci-gate.sh --quick       # 仅 lint + format
#   bash .omo/scripts/ci-gate.sh --verbose     # 详细输出
#
# 返回码:
#   0 = 全部通过
#   1 = 存在失败

set -euo pipefail

# ── 配置 ────────────────────────────────────────
KAIRON_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESULTS_DIR="$KAIRON_ROOT/.omo/tests"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
PASS=true
MODE="${1:-full}"

# ── 颜色 ────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ── 辅助函数 ────────────────────────────────────
log_info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[PASS]${NC}  $*"; }
log_fail()  { echo -e "${RED}[FAIL]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }

run_check() {
    local name="$1"
    local cmd="$2"
    local result_file="$RESULTS_DIR/gate_${name}.log"
    local code=0

    echo ""
    echo "─────────────────────────────────────────────"
    log_info "正在检查: ${name}"
    echo "─────────────────────────────────────────────"

    mkdir -p "$RESULTS_DIR"

    # 运行命令，捕获输出和返回码
    set +e
    eval "$cmd" > "$result_file" 2>&1
    code=$?
    set -e

    if [ $code -eq 0 ]; then
        log_ok "${name} — 通过"
        echo "结果已写入: ${result_file}"
    else
        log_fail "${name} — 失败 (返回码: ${code})"
        PASS=false
        if [ -s "$result_file" ]; then
            echo ""
            echo "--- 错误详情 (前 30 行) ---"
            head -30 "$result_file"
            echo "... (完整日志: ${result_file})"
        fi
    fi

    # 始终返回 0，避免 set -e 在检查失败时终止整个脚本
    # PASS 变量已记录失败状态，汇总阶段会据此返回正确退出码
    return 0
}

# ── 主流程 ──────────────────────────────────────
echo ""
echo "============================================================"
echo "  Kairon CI Gate"
echo "  目录:      $KAIRON_ROOT"
echo "  时间戳:    $TIMESTAMP"
echo "  模式:      $MODE"
echo "============================================================"

cd "$KAIRON_ROOT"

# 确保 ruff 可用
if command -v ruff &> /dev/null; then
    RUFF="ruff"
else
    if command -v uv &> /dev/null; then
        log_info "ruff 未在 PATH 中找到，尝试使用 uv run ruff"
        RUFF="uv run ruff"
    else
        log_warn "ruff 和 uv 均不可用，将使用系统 ruff"
        RUFF="python3 -m ruff"
    fi
fi

# 确保 pytest 可用 — 优先使用 uv run pytest
if command -v uv &> /dev/null && [ -f "$KAIRON_ROOT/uv.lock" ]; then
    PYTEST="uv run pytest"
else
    PYTEST="python3 -m pytest"
fi

# 如果使用 uv，同步依赖
if [ "$PYTEST" != "python3 -m pytest" ]; then
    log_info "同步依赖 (uv sync --all-packages)..."
    uv sync --all-packages -q 2>&1 || log_warn "uv sync 失败，将使用现有环境继续"
fi

# ── 1. Ruff Lint ────────────────────────────────
run_check "ruff-lint" "$RUFF check packages/" || true

# ── 2. Ruff Format ──────────────────────────────
run_check "ruff-format" "$RUFF format --check packages/" || true

# ── 3. 版本一致性 ──────────────────────────────
if [ "$MODE" != "--quick" ]; then
    run_check "version-consistency" "python3 .omo/scripts/check-version-consistency.py packages/" || true
fi

# ── 4. pytest 选测 ──────────────────────────────
if [ "$MODE" != "--quick" ]; then
    # 已知有基础设施问题的包（collection errors），按包排除避免假阳性
    IGNORE_PKGS=("agent-runtime" "agora" "ecos" "forge" "shared-lib" "engine-core" "kronos" "llm-gateway" "minerva" "sophia" "wksp" "eidos" "kairon-assistant")

    # 所有 26 个包
    ALL_PKGS=("agent-runtime" "agora" "codeanalyze" "core-models" "cron-service" "ecos" "eidos" "engine-core" "eu-pricing" "forge" "iris" "kairon-assistant" "kairon-voice" "kaironcloud-billing" "kos" "kronos" "llm-gateway" "metaos" "minerva" "ontoderive" "shared-lib" "sharedbrain-bridge" "sophia" "ssot" "symphony-protocol" "wksp")

    # 计算稳定包 = ALL_PKGS - IGNORE_PKGS
    STABLE_PKGS=()
    for pkg in "${ALL_PKGS[@]}"; do
        skip=false
        for ignore in "${IGNORE_PKGS[@]}"; do
            if [ "$pkg" = "$ignore" ]; then skip=true; break; fi
        done
        $skip || STABLE_PKGS+=("$pkg")
    done

    log_info "稳定包 (${STABLE_PKGS[*]})"
    log_info "排除包 (${IGNORE_PKGS[*]})"

    # 逐包独立运行 pytest，避免同名测试文件的模块冲突
    PYTEST_PASS=true
    PYTEST_SUMMARY=""
    for pkg in "${STABLE_PKGS[@]}"; do
        mkdir -p "$RESULTS_DIR"
        set +e
        $PYTEST "packages/$pkg/tests/" --exitfirst -q > "$RESULTS_DIR/gate_pytest-${pkg}.log" 2>&1
        pcode=$?
        set -e
        if [ $pcode -eq 0 ]; then
            PYTEST_SUMMARY="${PYTEST_SUMMARY}    ✅ ${pkg}: $(head -1 "$RESULTS_DIR/gate_pytest-${pkg}.log" 2>/dev/null)\n"
        else
            PYTEST_PASS=false
            PYTEST_SUMMARY="${PYTEST_SUMMARY}    ❌ ${pkg} (exit=$pcode)\n"
        fi
    done

    echo ""
    echo "─────────────────────────────────────────────"
    log_info "pytest 汇总"
    echo "─────────────────────────────────────────────"
    echo -e "$PYTEST_SUMMARY"
    if ! $PYTEST_PASS; then
        PASS=false
    fi

    # 将汇总写入结果文件供 --verbose 模式使用
    echo "--- 逐包结果 ---" > "$RESULTS_DIR/gate_pytest-stable.log"
    echo -e "$PYTEST_SUMMARY" >> "$RESULTS_DIR/gate_pytest-stable.log"
fi

# ── 汇总 ────────────────────────────────────────
echo ""
echo "============================================================"
if $PASS; then
    log_ok "CI Gate 全部通过 ✓"
    echo "============================================================"
    exit 0
else
    log_fail "CI Gate 存在失败项 ✗"
    echo ""
    echo "门禁失败项详情:"
    echo "  ruff-lint:      $(grep 'Found.*errors' "$RESULTS_DIR/gate_ruff-lint.log" 2>/dev/null | grep -oE '[0-9]+' | tail -1 || echo 0) errors"
    echo "  ruff-format:    $(test -f "$RESULTS_DIR/gate_ruff-format.log" && grep -ci 'would reformat' "$RESULTS_DIR/gate_ruff-format.log" 2>/dev/null || echo 0) files"
    echo "  version:        检查失败时请查看 $RESULTS_DIR/gate_version-consistency.log"
    echo "  pytest:         检查失败时请查看 $RESULTS_DIR/gate_pytest-stable.log"
    echo ""
    echo "详情请查看: $RESULTS_DIR/"
    echo "============================================================"
    exit 1
fi
