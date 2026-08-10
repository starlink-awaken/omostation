# launchd 常驻方案（待你审阅，未实施）

目标：让 omlx 默认编码服务**自动常驻 / 崩溃自拉起**，免去每次手动 `omlx serve`。

## 一个必须先解决的前提：外接盘依赖

你的模型在外接盘 `/Volumes/Model`。如果登录时盘还没挂载、或平时拔插，服务会加载失败并被 launchd 反复重启刷日志。所以方案里都带一个**挂载守卫**：盘在才启动，盘不在就安静退出等下一次。

---

## 三种模式（选一个）

| 模式 | RunAtLoad | KeepAlive | 行为 | 适合 |
|------|:---------:|:---------:|------|------|
| **A 全自动常驻** | 是 | 是 | 开机即加载默认主力(devstral ~23GB 常驻)，崩了自动拉起 | 你几乎每天都用、内存不在乎 |
| **B 守护不自启**（推荐） | 否 | 是 | 开机不占内存；你 `omlx serve` 起一次后，launchd 负责崩溃自愈、盘恢复后自愈 | 想要稳定但按需占内存 |
| **C 纯手动** | 否 | 否 | 就是现在这样，全靠 `omlx` | 偶尔用 |

推荐 **B**：兼顾「不无谓吃 23GB」和「服务稳」。下面给 A/B 通用的文件，靠两个开关切换。

---

## 文件 1：挂载守卫 + 启动包装 `bin/omlx-guard`

```bash
#!/usr/bin/env bash
# 盘挂了才启动指定服务，前台运行(交给 launchd 托管)
SVC="${1:-coding}"
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH
if [ ! -d /Volumes/Model/omlx ]; then
  echo "[omlx-guard] /Volumes/Model 未挂载，跳过 $SVC"; exit 0   # exit 0 → launchd 不视为崩溃
fi
exec omlx serve "$SVC" -f      # -f 前台，stdout/stderr 由 launchd 收集
```

## 文件 2：LaunchAgent `~/Library/LaunchAgents/com.omlx.coding.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key>            <string>com.omlx.coding</string>
  <key>ProgramArguments</key> <array>
    <string>/Volumes/Model/omlx/bin/omlx-guard</string>
    <string>coding</string>
  </array>
  <key>RunAtLoad</key>        <false/>   <!-- 模式A 改 true -->
  <key>KeepAlive</key>       <dict>
    <key>SuccessfulExit</key> <false/>   <!-- 非正常退出才重启 -->
  </dict>
  <key>ThrottleInterval</key> <integer>30</integer>  <!-- 重启间隔，防刷 -->
  <key>WatchPaths</key>      <array>
    <string>/Volumes/Model/omlx</string>  <!-- 盘恢复挂载时触发 -->
  </array>
  <key>StandardOutPath</key>  <string>/Volumes/Model/omlx/logs/launchd-coding.out</string>
  <key>StandardErrorPath</key><string>/Volumes/Model/omlx/logs/launchd-coding.err</string>
</dict></plist>
```

## 安装 / 卸载命令（确认方案后我来执行）

```bash
# 安装
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.omlx.coding.plist
# 模式A 立即起 / 模式B 仍用 `omlx serve coding`，崩溃由 launchd 兜
launchctl kickstart -k gui/$(id -u)/com.omlx.coding
# 状态
launchctl print gui/$(id -u)/com.omlx.coding | head
# 卸载
launchctl bootout gui/$(id -u)/com.omlx.coding
```

---

## 几个取舍点，你定一下

1. **模式 A / B / C？**（推荐 B）
2. **常驻哪个服务？** 默认 `coding`(devstral)。要不要把 `embedding` 也常驻（仅 7.3GB，RAG 常用）？
3. **多服务常驻？** 可以为每个 key 各来一份 plist（com.omlx.embedding 等），独立自愈。
4. **内存红线**：要不要在 guard 里加一道「可用内存低于 X 就不启动」的保护？

> 确认后我会把 guard 脚本和 plist 落到盘上并 `launchctl` 装好、验证自愈（kill 进程看是否自动拉起、卸载盘看是否安静退出）。
