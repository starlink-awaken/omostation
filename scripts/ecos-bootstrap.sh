#!/usr/bin/env bash
# ============================================================================
# eCOS v5 — 新用户体系引导 (ecos-bootstrap.sh)
# ============================================================================
# 为全新用户在一台新机器上搭建完整的 5+4+1 架构体系。
# 不包含 夏明星 的任何个人数据——生成一个干净的空白系统。
#
# 用法:
#   # 在当前目录生成空白体系
#   bash ecos-bootstrap.sh
#
#   # 在指定目录生成
#   bash ecos-bootstrap.sh --target ~/Documents
#
#   # 生成后立即初始化
#   bash ecos-bootstrap.sh --target ~/Documents --init
# ============================================================================

set -euo pipefail

TARGET="${HOME}/Documents"
FROM="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo "")"  # 默认为脚本所在目录
DO_INIT=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target) TARGET="$2"; shift 2 ;;
        --from) FROM="$2"; shift 2 ;;
        --init) DO_INIT=true; shift ;;
        *) echo "未知参数: $1"; exit 2 ;;
    esac
done

if [ -z "$FROM" ]; then
    FROM="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
fi

# 解析 FROM 为绝对路径
FROM="$(cd "$FROM" 2>/dev/null && pwd || echo "$FROM")"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  eCOS v5 — 新用户体系引导                               ║"
echo "║  为全新用户生成一张空白的 5+4+1 架构画布                  ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

mkdir -p "${TARGET}"
cd "${TARGET}"
TARGET="$(pwd)"

echo "  目标: ${TARGET}"
echo ""

# ── 目录结构 ──
echo "── 1/8: 创建目录结构 ──"

mkdir -p "${TARGET}/驾驶舱/scripts"
mkdir -p "${TARGET}/驾驶舱/CARDS"
mkdir -p "${TARGET}/学习进化/1-active/自我剖析"
mkdir -p "${TARGET}/学习进化/1-active/收件箱"
mkdir -p "${TARGET}/学习进化/2-knowledge/体系"
mkdir -p "${TARGET}/学习进化/2-knowledge/基建架构"
mkdir -p "${TARGET}/学习进化/2-knowledge/经验积累/lessons"
mkdir -p "${TARGET}/学习进化/3-archive/资料库"
mkdir -p "${TARGET}/学习进化/3-archive/灵感顿悟"
mkdir -p "${TARGET}/工具箱"
mkdir -p "${TARGET}/领域知识库"
mkdir -p "${TARGET}/工作文档"
mkdir -p "${TARGET}/家庭生活"

echo "  ✅ 13 个目录已创建"
echo ""

# ── L4 网关 ──
echo "── 2/8: 创建 L4 网关 ──"

cat > "${TARGET}/CLAUDE_COWORK_GLOBAL.md" << 'GATEWAY'
# CLAUDE_COWORK_GLOBAL.md — L4 自我层网关

> **L4 网关** — 身份锚 + 域路由 + 执行纪律 + 治理入口
> eCOS v5 | 5.0.0 | $(date +%Y-%m-%d)

---

## §0 我是谁

**[你的名字]** — **[你的身份描述]**

---

## §1 系统架构

本系统基于 **eCOS v5 (5+4+1)** 架构：

```
L4 自我层  ← 你在这里 (身份·宪法·文档体系)
L3 入口桥接 ← 多入口适配 (CLI/MCP)
L2 内核三平面 ← 治理+引擎+记忆
L1 运行时矩阵 ← 服务编排·健康监控
L0 协议编织 ← 协议注册·约束·映射

X1 治理安全 · X2 抗熵进化 · X3 价值堆栈
```

---

## §2 域路由

| 域 | 入口 | 作用 |
|----|------|------|
| **驾驶舱** | `驾驶舱/CLAUDE.md` | 全局状态·任务·治理 |
| **Vault** | `学习进化/CLAUDE.md` | 知识系统·创作·经验 |
| **工具箱** | `工具箱/CLAUDE.md` | 能力·模板·管线 |
| **领域知识库** | `领域知识库/CLAUDE.md` | 实体实例化 |
| **工作文档** | `工作文档/CLAUDE.md` | 业务文档 |
| **家庭生活** | `家庭生活/CLAUDE.md` | 日常管理 |

---

## §3 启动链

Agent 启动后按顺序执行：

0. **`python3 ~/Documents/驾驶舱/scripts/ecos-brief.py --force`**
1. **`驾驶舱/brief.md`** — 读会话简报
2. **本文件** — 身份锚 + 域路由
3. **`驾驶舱/DASHBOARD.md`** — 全局状态
4. **`驾驶舱/CLAUDE.md` §2.5** — CARDS
5. **目标域 CLAUDE.md**

---

## §4 治理系统

```bash
# 一键健康检查
python3 ~/Documents/驾驶舱/scripts/ecos-health-check.py

# 会话简报
python3 ~/Documents/驾驶舱/scripts/ecos-brief.py --force

# 系统自述
python3 ~/Documents/驾驶舱/scripts/ecos-whoami.py
```

---

## §5 运营手册

- 运营 SOP: `驾驶舱/OPS.md`
- 部署指南: `驾驶舱/DEPLOY.md`
- 接入引导: `驾驶舱/ONBOARD.md`

---

## §6 核心原则

1. **SSOT** — 每个事实一个权威位置
2. **CARDS 优先** — 任务走 SQLite
3. **治理可验证** — 一键 health-check
4. **启动链必读** — 每次会话从 brief 开始

---

_此文件由 ecos-bootstrap.sh 生成。编辑 §0 填入你的身份。_
GATEWAY

echo "  ✅ CLAUDE_COWORK_GLOBAL.md"
echo ""

# ── 驾驶舱入口 ──
echo "── 3/8: 创建驾驶舱 ──"

cat > "${TARGET}/驾驶舱/CLAUDE.md" << 'COCKPIT'
# 驾驶舱 — Agent 操作契约

> L2 | 定义 Agent 在驾驶舱/ 的行为规则

## §0 SSOT 声明

| 内容类型 | SSOT 位置 |
|---------|----------|
| 域健康度 | 各域 STATE.md |
| 跨域信号 | SIGNALS.md |
| 活跃任务 | CARDS SQLite |

## §1 快速路由

| 意图 | 动作 |
|------|------|
| 看全局状态 | 读 DASHBOARD.md |
| 看跨域信号 | 读 SIGNALS.md |
| 查看任务 | MCP cards_status / SQLite cards.db |

## §2 维护

最后更新: $(date +%Y-%m-%d) | ecos-bootstrap 生成
COCKPIT

echo "  ✅ 驾驶舱/CLAUDE.md"

# ── 空 DASHBOARD ──
cat > "${TARGET}/驾驶舱/DASHBOARD.md" << 'DASHBOARD'
# DASHBOARD — 全局状态

> Agent 每次会话启动必读。
> 更新: $(date +%Y-%m-%d) | ecos-bootstrap 生成

## 域健康度

| 域 | 状态 | 信号 |
|----|:----:|:----:|
| 驾驶舱 | 🟢 | — |
| Vault | 🟢 | — |
| 工具箱 | 🟢 | — |
| 领域知识库 | 🟢 | — |
| 工作文档 | 🟢 | — |
| 家庭生活 | 🟢 | — |
DASHBOARD

echo "  ✅ 驾驶舱/DASHBOARD.md"

# ── 空 SIGNALS ──
cat > "${TARGET}/驾驶舱/SIGNALS.md" << 'SIGNALS'
# SIGNALS — 跨域信号

> 按时间倒序。跨域影响在此登记。
> $(date +%Y-%m-%d) | ecos-bootstrap 生成
SIGNALS

echo "  ✅ 驾驶舱/SIGNALS.md"
echo ""

# ── Vault 入口 ──
echo "── 4/8: 创建 Vault 入口 ──"

cat > "${TARGET}/学习进化/CLAUDE.md" << 'VAULT'
# 学习进化 — Vault 入口

> L1 | 知识面主体。1-active / 2-knowledge / 3-archive 三层。

## §0 Vault 结构

```
学习进化/
├── 🔴 1-active/    ← 自我剖析·收件箱
├── 🟡 2-knowledge/ ← 方法论·基建·创作
└── 🟢 3-archive/   ← 资料·灵感·
```

## §1 快速路由

| 意图 | 动作 |
|------|------|
| 看全局状态 | 读 STATE.md |
| 查方法 | `2-knowledge/体系/` |
| 开始创作 | `2-knowledge/创意创作/` |

## §2 维护

最后更新: $(date +%Y-%m-%d) | ecos-bootstrap 生成
VAULT

echo "  ✅ 学习进化/CLAUDE.md"

# ── 空 STATE.md ──
cat > "${TARGET}/学习进化/STATE.md" << 'STATE'
# STATE — 学习进化 Vault 状态

> Vault 级健康度。

## 子模块健康度

| 模块 | 状态 | 备注 |
|------|:----:|------|
| 自我剖析 | 🟢 | 刚创建 |
| 收件箱 | 🟢 | 空 |
| 体系 | 🟢 | — |
| 基建架构 | 🟢 | — |
| 经验积累 | 🟢 | — |

## 更新记录

| 日期 | 更新 |
|------|------|
| $(date +%Y-%m-%d) | ecos-bootstrap 生成 |
STATE

# ── 空 ENTITIES.md ──
cat > "${TARGET}/领域知识库/ENTITIES.md" << 'ENTITIES'
# 领域知识库 — ENTITIES.md

> SSOT 实体实例化索引

## 子域

| 子域 | 内容 | 实体类型 |
|------|------|---------|
| 人物/ | — | Person |
| 组织/ | — | Organization |
| 系统/ | — | System |
| 关系/ | — | Relation |
ENTITIES

echo "  ✅ 学习进化/STATE.md"
echo "  ✅ 领域知识库/ENTITIES.md"
echo ""

# ── 安装脚本 ──
echo "── 5/8: 安装治理脚本 ──"

echo "  📍 脚本源: ${FROM}"

if [ -d "${FROM}" ]; then
    COUNT=0
    # 复制所有 .py 脚本 (排除 bootstrap 自身)
    for f in "${FROM}"/*.py; do
        fname="$(basename "$f")"
        if [ -f "$f" ] && [ "$fname" != "ecos-bootstrap.py" ] && [ "$fname" != "__init__.py" ]; then
            cp "$f" "${TARGET}/驾驶舱/scripts/" 2>/dev/null && ((COUNT++))
        fi
    done
    # 复制 .sh 脚本 (排除自身)
    for f in "${FROM}"/*.sh; do
        fname="$(basename "$f")"
        if [ -f "$f" ] && [ "$fname" != "ecos-bootstrap.sh" ]; then
            cp "$f" "${TARGET}/驾驶舱/scripts/" 2>/dev/null
        fi
    done
    echo "  ✅ ${COUNT} 个脚本已安装"
else
    echo "  ⚠️  脚本源目录不存在: ${FROM}"
    echo "     用法: bash ecos-bootstrap.sh --from /path/to/ecos/scripts/"
fi
echo ""

# ── 文档复制 ──
echo "── 6/8: 安装运营文档 ──"

echo "── 6/8: 安装运营文档 ──"
# 文档在 scripts/ 的父目录 (驾驶舱/)
DOCS_SRC="$(dirname "${FROM}")"  # 从 scripts/ → 驾驶舱/
DOC_COUNT=0
for doc in ACCESS.md ONBOARD.md OPS.md DEPLOY.md DEPLOY-CHECKLIST.md agent-manifest.yaml meta-model-ecos.yaml meta-model-ecos.schema.json x3-value-stack.yaml; do
    for try in "${DOCS_SRC}/${doc}" "${FROM}/${doc}" "${FROM}/../${doc}"; do
        if [ -f "$try" ]; then
            cp "$try" "${TARGET}/驾驶舱/" 2>/dev/null && ((DOC_COUNT++))
            break
        fi
    done
done
echo "  ✅ ${DOC_COUNT} 个文档已安装"
echo ""

# ── 符号链接 ──
echo "── 7/8: 创建入口符号链接 ──"

if [ ! -f "${TARGET}/claude.md" ]; then
    ln -sf "CLAUDE_COWORK_GLOBAL.md" "${TARGET}/claude.md"
    echo "  ✅ claude.md → CLAUDE_COWORK_GLOBAL.md"
fi
echo ""

# ── 初始化 ~/.ecos/ ──
echo "── 8/8: 初始化运行时 ──"

bash "${TARGET}/驾驶舱/scripts/ecos-init.sh" --no-daemon 2>/dev/null || {
    echo "  ⚠️  运行 ecos-init.sh 时出现问题，手动执行："
    echo "     bash ${TARGET}/驾驶舱/scripts/ecos-init.sh"
}
echo ""

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  🎉 eCOS v5 体系已就绪！                                ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  位置: ${TARGET}"
echo ""
echo "  第一步: 编辑 CLAUDE_COWORK_GLOBAL.md §0 填入你的身份"
echo "  第二步: python3 驾驶舱/scripts/ecos-brief.py --force"
echo "  第三步: python3 驾驶舱/scripts/ecos-whoami.py"
echo ""
echo "  开始使用: cat 驾驶舱/OPS.md"
echo ""
