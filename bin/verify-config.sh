#!/bin/bash
# PAI 配置验证脚本
# 用于验证 PAI 配置是否完整

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 计数器
PASSED=0
FAILED=0
WARNINGS=0

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   PAI 配置验证工具${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查函数
check_file() {
    local file=$1
    local description=$2
    local required=$3

    if [ -f "$file" ]; then
        echo -e "${GREEN}✅ PASS${NC}: $description"
        echo -e "   路径: $file"
        ((PASSED++))
        return 0
    else
        if [ "$required" = "required" ]; then
            echo -e "${RED}❌ FAIL${NC}: $description"
            echo -e "   路径: $file"
            ((FAILED++))
            return 1
        else
            echo -e "${YELLOW}⚠️  WARN${NC}: $description"
            echo -e "   路径: $file"
            ((WARNINGS++))
            return 0
        fi
    fi
}

check_dir() {
    local dir=$1
    local description=$2
    local required=$3

    if [ -d "$dir" ]; then
        echo -e "${GREEN}✅ PASS${NC}: $description"
        echo -e "   路径: $dir"
        ((PASSED++))
        return 0
    else
        if [ "$required" = "required" ]; then
            echo -e "${RED}❌ FAIL${NC}: $description"
            echo -e "   路径: $dir"
            ((FAILED++))
            return 1
        else
            echo -e "${YELLOW}⚠️  WARN${NC}: $description"
            echo -e "   路径: $dir"
            ((WARNINGS++))
            return 0
        fi
    fi
}

check_command() {
    local cmd=$1
    local description=$2

    if command -v "$cmd" &> /dev/null; then
        echo -e "${GREEN}✅ PASS${NC}: $description"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}❌ FAIL${NC}: $description"
        ((FAILED++))
        return 1
    fi
}

# 获取 PAI 目录
PAI_DIR="${PAI_DIR:-$HOME/.claude}"

echo -e "${BLUE}[1/6] 检查必需软件${NC}"
echo "---"
check_command "bun" "Bun 运行时"
check_command "claude" "Claude Code CLI"
echo ""

echo -e "${BLUE}[2/6] 检查核心配置文件${NC}"
echo "---"
check_file "$PAI_DIR/settings.json" "settings.json（主配置文件）" "required"
check_file "$PAI_DIR/CLAUDE.md" "CLAUDE.md（Claude 入口指令）" "required"
check_file "$PAI_DIR/.env" ".env（环境变量文件）" "optional"
echo ""

echo -e "${BLUE}[3/6] 检查目录结构${NC}"
echo "---"
check_dir "$PAI_DIR" "PAI 根目录" "required"
check_dir "$PAI_DIR/skills" "技能目录" "required"
check_dir "$PAI_DIR/skills/PAI" "PAI 核心技能目录" "required"
check_dir "$PAI_DIR/hooks" "钩子目录" "required"
check_dir "$PAI_DIR/MEMORY" "记忆目录（自动生成）" "optional"
check_dir "$PAI_DIR/agents" "智能体目录" "optional"
check_dir "$PAI_DIR/plugins" "插件目录" "optional"
echo ""

echo -e "${BLUE}[4/6] 检查核心技能文件${NC}"
echo "---"
check_file "$PAI_DIR/skills/PAI/SKILL.md" "PAI 核心技能文档" "required"
check_file "$PAI_DIR/skills/PAI/SYSTEM/PAISYSTEMARCHITECTURE.md" "系统架构文档" "required"
check_file "$PAI_DIR/skills/PAI/SYSTEM/AISTEERINGRULES.md" "AI 行为准则" "required"
check_file "$PAI_DIR/skills/PAI/USER/DAIDENTITY.md" "AI 身份配置" "optional"
echo ""

echo -e "${BLUE}[5/6] 检查钩子文件${NC}"
echo "---"
check_file "$PAI_DIR/hooks/StartupGreeting.hook.ts" "启动问候钩子" "required"
check_file "$PAI_DIR/hooks/LoadContext.hook.ts" "上下文加载钩子" "required"
check_file "$PAI_DIR/hooks/FormatReminder.hook.ts" "格式提醒钩子" "required"
check_file "$PAI_DIR/hooks/SecurityValidator.hook.ts" "安全验证钩子" "required"
check_file "$PAI_DIR/hooks/SessionSummary.hook.ts" "会话总结钩子" "optional"
echo ""

echo -e "${BLUE}[6/6] 检查配置内容${NC}"
echo "---"

# 检查 settings.json 格式
if [ -f "$PAI_DIR/settings.json" ]; then
    if command -v jq &> /dev/null; then
        if jq empty "$PAI_DIR/settings.json" 2>/dev/null; then
            echo -e "${GREEN}✅ PASS${NC}: settings.json 格式正确"
            ((PASSED++))

            # 检查关键配置项
            if jq -e '.paiVersion' "$PAI_DIR/settings.json" &> /dev/null; then
                PAI_VERSION=$(jq -r '.paiVersion' "$PAI_DIR/settings.json")
                echo -e "   PAI 版本: $PAI_VERSION"
            fi

            if jq -e '.principal.name' "$PAI_DIR/settings.json" &> /dev/null; then
                PRINCIPAL_NAME=$(jq -r '.principal.name' "$PAI_DIR/settings.json")
                echo -e "   用户名称: $PRINCIPAL_NAME"
            fi

            if jq -e '.daidentity.name' "$PAI_DIR/settings.json" &> /dev/null; then
                DA_NAME=$(jq -r '.daidentity.name' "$PAI_DIR/settings.json")
                echo -e "   AI 名称: $DA_NAME"
            fi
        else
            echo -e "${RED}❌ FAIL${NC}: settings.json 格式错误"
            ((FAILED++))
        fi
    else
        echo -e "${YELLOW}⚠️  WARN${NC}: jq 未安装，无法验证 JSON 格式"
        ((WARNINGS++))
    fi
fi

# 检查 .env 文件
if [ -f "$PAI_DIR/.env" ]; then
    if grep -q "ELEVENLABS_API_KEY" "$PAI_DIR/.env"; then
        echo -e "${GREEN}✅ PASS${NC}: ElevenLabs API 密钥已配置"
        ((PASSED++))
    else
        echo -e "${YELLOW}⚠️  WARN${NC}: ElevenLabs API 密钥未配置（语音功能不可用）"
        ((WARNINGS++))
    fi
else
    echo -e "${YELLOW}⚠️  WARN${NC}: .env 文件不存在（语音功能不可用）"
    ((WARNINGS++))
fi

# 检查语音服务器
if curl -s http://localhost:8888/health &> /dev/null; then
    echo -e "${GREEN}✅ PASS${NC}: 语音服务器运行中"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠️  WARN${NC}: 语音服务器未运行"
    ((WARNINGS++))
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   验证结果汇总${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✅ 通过: $PASSED${NC}"
echo -e "${RED}❌ 失败: $FAILED${NC}"
echo -e "${YELLOW}⚠️  警告: $WARNINGS${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 配置验证通过！PAI 系统已正确配置。${NC}"
    echo ""
    echo "下一步："
    echo "  1. 启动 Claude Code: cd $PAI_DIR && claude"
    echo "  2. 如果需要语音功能，确保语音服务器运行：cd $PAI_DIR/VoiceServer && bun run start"
    echo ""
    exit 0
else
    echo -e "${RED}❌ 配置验证失败！请检查上述错误并修复。${NC}"
    echo ""
    echo "建议："
    echo "  1. 运行安装向导: cd $PAI_DIR && bun run INSTALL.ts"
    echo "  2. 查看完整配置指南: cat $PAI_DIR/CLAUDE_COMPLETE_SETUP_GUIDE.md"
    echo ""
    exit 1
fi
