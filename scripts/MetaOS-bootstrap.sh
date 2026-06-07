#!/bin/bash
# MetaOS Bootstrap v2.0 — 新机器首次初始化
# 用法: bash ~/Documents/学习进化/MetaOS-bootstrap.sh
set -e
echo "╔══════════════════════════════════════╗"
echo "║     MetaOS Bootstrap v2.0            ║"
echo "╚══════════════════════════════════════╝"

# 0. 前置检查
echo ""; echo "[0/6] iCloud Documents 同步检查..."
[ -d "$HOME/Documents/学习进化" ] && echo "  ✅ 学习进化 vault 已同步" || { echo "  ⚠️  未找到，确认 iCloud 同步完成"; exit 1; }

# 1. 检查 iCloud 软链 (.ai .agents 已移入 iCloud)
echo ""; echo "[1/6] iCloud 软链检查..."
for link in ".ai" ".agents"; do
  if [ -L "$HOME/$link" ]; then
    target=$(readlink "$HOME/$link")
    echo "  ✅ ~/$link → $target"
  elif [ -d "$HOME/$link" ]; then
    echo "  ⚠️  ~/$link 是真实目录，建议移入 iCloud 并建软链"
  else
    echo "  ❌ ~/$link 不存在。请从 iCloud 建软链："
    echo "     ln -s /path/to/iCloud/$link ~/$link"
  fi
done

# 2. 工具链
echo ""; echo "[2/6] 工具链..."
mkdir -p ~/workspace/projects
if [ ! -d "$HOME/workspace/projects/kairon" ]; then
  cd ~/workspace/projects
  git clone git@github.com:xia-mingxing/kairon.git kairon 2>/dev/null || \
  git clone https://github.com/xia-mingxing/kairon.git kairon 2>/dev/null || \
  echo "  ⚠️  kairon clone 失败，手动处理"
  cd kairon && pip install -e . --break-system-packages 2>/dev/null || true
  echo "  ✅ kairon"
fi
mkdir -p ~/Workspace/projects
if [ ! -d "$HOME/Workspace/projects/gbrain" ]; then
  cd ~/Workspace/projects
  git clone git@github.com:xia-mingxing/gbrain.git gbrain 2>/dev/null || \
  echo "  ⚠️  gbrain clone 失败，手动处理"
  cd gbrain && bun install 2>/dev/null || true
  echo "  ✅ gbrain"
fi

# 3. 环境变量
echo ""; echo "[3/6] 环境变量..."
grep -q "KOS_HOME" ~/.zshrc 2>/dev/null || echo 'export KOS_HOME=$HOME/Workspace/kos' >> ~/.zshrc
grep -q "kairon/bin" ~/.zshrc 2>/dev/null || echo 'export PATH="$HOME/workspace/projects/kairon/bin:$PATH"' >> ~/.zshrc
echo "  ✅ 环境变量"

# 4. 验证
echo ""; echo "[4/6] 验证..."
C=0
[ -d "$HOME/Documents/学习进化/驾驶舱" ] && ((C++)) || echo "  ⚠️  驾驶舱未找到"
[ -d "$HOME/Documents/学习进化/工具箱" ] && ((C++)) || echo "  ⚠️  工具箱未找到"
[ -d "$HOME/Documents/学习进化/领域知识库" ] && ((C++)) || echo "  ⚠️  领域知识库未找到"
[ -d "$HOME/Documents/学习进化/经验积累/lessons" ] && ((C++)) || echo "  ⚠️  经验积累未找到"
[ -d "$HOME/workspace/projects/kairon" ] && ((C++))
[ -L "$HOME/.ai" ] && ((C++))
echo "  通过: $C/6"

# 5. 完成
echo ""; echo "[5/6] 待手动完成:"
echo "  1. Cowork 设置 → 全局指令 ← 复制 CLAUDE_COWORK_GLOBAL.md"
echo "  2. Cowork MCP 配置"
echo "  3. ~/.claude/skills/graphify"
echo "  4. 确认 Obsidian vault 正常打开"
echo ""; echo "╔══════════════════════════════════════╗"
echo "║  Bootstrap 完成！欢迎进入 MetaOS。    ║"
echo "╚══════════════════════════════════════╝"