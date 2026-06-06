# XX — 各设备操作步骤（逐条执行）

> 更新日期：2026-05-20
> **重要：执行前先通读全文，理解每步含义再操作。**

---

## 通用准备：所有设备

### ① 安装 Tailscale

```bash
# Mac mini / MBP
brew install --cask tailscale
open -a Tailscale
# 登录同一账号（Google/GitHub）

# ✅ 验证
tailscale status
# 应看到所有设备在线
```

### ② 安装 Ollama

```bash
brew install ollama
```

---

## 一、Mac mini M4 — 操作步骤

### 现状

```
外接 SSD 分区：
  /Volumes/Work/    ← 空，等分配
  /Volumes/Model/   ← 已有 Docker 镜像、Ollama 模型、LM Studio 模型
```

### Step 1 — 确认外接盘

```bash
# 确认两个分区都能看到
ls /Volumes/
# 应显示：Model  Work

# 确认 Model 下已有内容
ls /Volumes/Model/
# 应有：Docker 镜像目录、Ollama 模型、LM Studio 模型等
```

### Step 2 — 配置 Ollama 模型路径到 Model 盘

```bash
# 设置模型存储到 /Volumes/Model
launchctl setenv OLLAMA_MODELS /Volumes/Model

# 持久化（重启不丢）
mkdir -p ~/Library/LaunchAgents
cat > ~/Library/LaunchAgents/com.ollama.models.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ollama.models</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/launchctl</string>
        <string>setenv</string>
        <string>OLLAMA_MODELS</string>
        <string>/Volumes/Model</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
EOF
launchctl load ~/Library/LaunchAgents/com.ollama.models.plist

# 允许 MBP 远程调用
launchctl setenv OLLAMA_HOST 0.0.0.0:11434
brew services restart ollama

# ✅ 验证
echo $OLLAMA_MODELS
# 输出：/Volumes/Model
```

### Step 3 — 拉取最新模型（更新旧模型）

```bash
# 首选：Qwen3.6-35B-A3B（MoE，~21GB，Mac mini 24GB 首选）
ollama pull qwen3.6:35b-a3b

# 嵌入模型（RAG 用）
ollama pull bge-m3

# OCR 模型（可选）
ollama pull glm-ocr

# ✅ 验证已安装的模型
ollama list

# 清理旧的 Qwen2.5 模型（如果空间不够）
# ollama rm qwen2.5:7b
# ollama rm qwen2.5:14b
# ollama rm deepseek-coder-v2
```

### Step 4 — 安装 Docker + 部署 New API

```bash
# 安装 Docker（推荐 OrbStack，比 Docker Desktop 轻量）
brew install orbstack

# 建 New API 数据目录（放到 Work 盘，因为 Model 盘已满）
mkdir -p /Volumes/Work/DockerData/NewAPI

# 启动 New API（Go 二进制 ~30MB）
docker run --name new-api -d \
  --restart always \
  -p 3000:3000 \
  -e TZ=Asia/Shanghai \
  -e RELAY_PROXY=http://127.0.0.1:7890 \
  -v /Volumes/Work/DockerData/NewAPI:/data \
  calciumion/new-api:latest

# ✅ 验证
curl http://localhost:3000/api/status
```

### Step 5 — 配置 New API

```
1. 浏览器 → http://localhost:3000
2. 默认账号 root / 123456 → 立即改密码
3. 添加渠道（5 个）：
   - DeepSeek V4 Flash
   - DeepSeek V4 Pro
   - GLM-4.7
   - Kimi K2
   - MiniMax M2.5
4. 生成令牌 → 复制 sk-xxx
```

### Step 6 — 验证全链路

```bash
# 本地 Ollama 推理
ollama run qwen3.6:35b-a3b "你好"

# New API 网关（走代理调云端）
curl http://localhost:3000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-xxx" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"hi"}]}'
```

### Step 7 — 安装 PaddleOCR（可选）

```bash
pip install paddleocr

# ✅ 测试
paddleocr --image_dir 测试图片.png --lang ch
```

### Step 8 — 配置 Chezmoi（接收 MBP 配置）

```bash
brew install chezmoi
# 等 MBP 建好 dotfiles 仓库后执行：
chezmoi init --apply git@github.com:starlink-awaken/dotfiles.git
```

---

## 二、MBP M5 Max — 操作步骤

### 现状

```
内置 SSD：系统 + 应用 + 当前项目
外接 SSD：/Volumes/Model/  ← 已有 Docker 镜像、Ollama 模型、LM Studio 模型
```

### Step 1 — 确认外接盘

```bash
ls /Volumes/
# 应看到 Model（外接 SSD）

# 查看已有哪些模型
ollama list
# 或
ls /Volumes/Model/
```

### Step 2 — 配置 Ollama

```bash
# 默认模型路径在内置 SSD 的 ~/.ollama
# 插上外接 SSD 时才切到外部
# 编写切换脚本
```

### Step 3 — 拉取最新模型

```bash
# 首选：Qwen3-Coder-Next（80B MoE，~38GB Q4，本地最强代码模型）
ollama pull qwen3-coder-next

# Mac mini 同款通用推理（高精度版）
ollama pull qwen3.6:35b-a3b

# 嵌入模型
ollama pull bge-m3

# OCR 模型
ollama pull glm-ocr

# ✅ 验证
ollama list
```

### Step 4 — 安装 Tailscale（如果未装）

```bash
brew install --cask tailscale
open -a Tailscale
```

### Step 5 — 验证远程调用 Mac mini

```bash
# Mac mini 的 Ollama
curl http://100.x.x.1:11434/api/tags

# Mac mini 的 New API
curl http://100.x.x.1:3000/api/status

# Mac mini 的 Qwen3.6 推理
curl http://100.x.x.1:11434/api/generate \
  -d '{"model":"qwen3.6:35b-a3b","prompt":"你好","stream":false}'
```

### Step 6 — 安装 Chezmoi（作为配置源端）

```bash
brew install chezmoi
chezmoi init

# 追踪配置文件
chezmoi add ~/.zshrc
chezmoi add ~/.gitconfig
chezmoi add ~/.config/hermes/config.yaml

# 生成 Brewfile
brew bundle dump --describe --file=~/Desktop/Brewfile
chezmoi add ~/Desktop/Brewfile

# 推送到 GitHub
cd ~/.local/share/chezmoi
gh repo create dotfiles --private
git add -A && git commit -m "init: dotfiles"
git push -u origin main
```

### Step 7 — 编写切换脚本

```bash
cat > ~/bin/switch-mode.sh << 'EOF'
#!/bin/bash
case "$1" in
  home)
    export OLLAMA_HOST_MM=http://100.x.x.1:11434
    export ONE_API=http://100.x.x.1:3000/v1
    echo "🏠 Home: Mac mini 推理 + New API 云端"
    ;;
  travel)
    export OLLAMA_MODELS=/Volumes/Model
    export OLLAMA_HOST=127.0.0.1:11434
    echo "🚗 Travel: 外接 SSD 本地推理"
    ;;
  office)
    export OLLAMA_HOST_MM=http://100.x.x.1:11434
    export ONE_API=http://100.x.x.1:3000/v1
    echo "🏢 Office: 同上，Tailscale 远程"
    ;;
esac
EOF
chmod +x ~/bin/switch-mode.sh
```

---

## 三、Y7000P — 操作步骤

### Y7000P 的定位

> **Y7000P 不做 AI 推理，不跑 Docker，不做任何服务端。**
> 它只做两件事：① 挂 WD_BLACK P10 开 SMB 共享 ② 打游戏

### Step 1 — 开启养护模式

```
1. 打开 Lenovo Vantage（联想电脑管家）
2. 硬件设置 → 电源 → 开启"养护模式"
3. 确认充电阈值显示 55%-60%
```

### Step 2 — 插好 WD_BLACK P10 + 开 SMB 共享

```
1. 将 WD_BLACK P10 插入 Y7000P USB 3.0 接口
2. 右键"此电脑" → 管理 → 磁盘管理
3. 确认 WD_BLACK 显示正常（盘符如 D: 或 E:）

4. 创建 Time Machine 目标目录：
   mkdir D:\MacMini_TM
   mkdir D:\MBP_TM

5. 右键 D:\MacMini_TM → 属性 → 共享 → 高级共享
   - 勾选"共享此文件夹"
   - 共享名：Mac_TimeMachine
   - 权限：当前用户 → 完全控制

6. ✅ 验证
   \\localhost\Mac_TimeMachine   # 应可访问
```

### Step 3 — 安装 Tailscale

```
1. 下载 https://tailscale.com/download → Windows 版
2. 安装 → 登录同一账号
3. ✅ 验证
   tailscale status
   # 看到 Mac mini + MBP 都在线
```

### Step 4 — GameMode / WorkMode 脚本（可选）

可以创建两个快捷方式放桌面，但这不重要——因为 Y7000P 不打游戏时就只是 SMB 文件服务器，不需要切换。

---

## 四、单位台式机 — 操作步骤

### 定位：纯 Tailscale 子网路由器

```
1. 安装 Tailscale（Windows 版）
2. 登录同一账号

3. 以管理员身份运行 cmd.exe：
   ipconfig
   # 记录单位局域网段（如 192.168.1.0/24）

4. 配置子网路由（假设网段 192.168.1.0/24）：
   tailscale up --advertise-routes=192.168.1.0/24

5. 浏览器访问 https://login.tailscale.com
   → Machines → 找到这台电脑
   → Edit Route Settings → 勾选并审批路由

6. ✅ 验证（从 MBP 或 Mac mini）
   ping 192.168.1.1   # 单位内网网关
   ping 192.168.1.xxx # 单位内网任意 IP
```

---

## 五、各设备操作耗时预估

| 设备 | 步骤数 | 预估耗时 | 关键操作 |
|------|--------|---------|---------|
| Mac mini | 8 步 | **~2 小时** | 配 Ollama 路径 + Docker New API + 拉模型 |
| MBP | 7 步 | **~1 小时** | 拉模型 + Chezmoi 配置 + 验证远程连通 |
| Y7000P | 4 步 | **~20 分钟** | 插 P10 + 开 SMB + 装 Tailscale |
| 单位台式机 | 6 步 | **~15 分钟** | 装 Tailscale + 配子网路由 + 审批 |

## 六、新旧模型对比

| 维度 | 旧方案 | 新方案（2026年5月） |
|------|--------|-------------------|
| Mac mini 推理模型 | Qwen2.5:7b/14b (~10GB) | **Qwen3.6-35B-A3B MoE (~21GB)** |
| MBP 推理模型 | DeepSeek-Coder-V2 (16B) | **Qwen3-Coder-Next (~38GB)** |
| 嵌入模型 | bge-m3 | bge-m3（不变，仍然最佳） |
| OCR | 无 | PaddleOCR + GLM-OCR + Apple Vision |
| Mac mini 推理能力 | 7B-14B 小模型 | **35B 级别知识（MoE）** |
| MBP 推理能力 | 16B-32B | **80B 级别代码推理（MoE）** |
