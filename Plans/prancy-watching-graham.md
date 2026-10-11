# 修复 guard 语法错误恢复 :4000 门面 + 打通 tts 本地链路（P0 收口）

## Context

P0 清单最后一项：tts 经 aetherforge 门面(:4000) 401。根因已定位：oMLX(:8000) 启用 API key 鉴权后，gateway 的 media_proxy 转发 `/v1/audio/*`、`/v1/rerank` 到 oMLX 时不带 Bearer key（直连 oMLX 已验证 200 + 50KB 音频，能力本体完好）。

guard 脚本（`~/.local/bin/aetherforge-gw-guard`）的密钥纪律：**密钥从 Keychain 进程注入，不落 plist/YAML/命令行**。此前误往 plist 塞 env 的方案与此冲突且未生效。

本轮已落地的部分（事故前已完成，无需回滚）：
- Keychain 条目 `omlx-api-key` 已建（值 = `~/.omlx/settings.json` 的 `auth.api_key`）
- guard 已追加 oMLX key 注入段（模仿既有 unsloth-studio 段的写法）
- plist 里误加的 `AETHERFORGE_MEDIA_AUDIO_API_KEY` / `AETHERFORGE_RERANK_API_KEY` 两个 env 已删除（回归设计原则）

**事故**：补丁新增的 `if` 块漏了外层 `fi` → guard 语法错误（line 89 unexpected EOF）→ launchd 反复 spawn 失败（last exit 2）→ **:4000 门面 down**，kairon/cockpit/bin-gac 走门面的图像/vision/语音/决策路由全部中断。修复优先级最高。

## 修复步骤

1. **补 `fi`（一行）**：`~/.local/bin/aetherforge-gw-guard` 中，`unset AETHERFORGE_MEDIA_AUDIO_API_KEY AETHERFORGE_RERANK_API_KEY` 行下方的 `fi`（内层闭合）之后，补外层 `if [ -z "${AETHERFORGE_MEDIA_AUDIO_API_KEY:-}" ]` 的闭合 `fi`。用 python 精确替换，不动其他内容。

2. **语法验证 + 重启**：`bash -n` 通过后 `launchctl bootout` + `bootstrap`（gui domain）。guard 内含 Tailscale 网卡等待循环（最长 90s），health 探测循环最长等 ~2min。

3. **复测 tts 经门面**：
   ```bash
   curl -sS -X POST http://127.0.0.1:4000/v1/audio/speech \
     -H "Content-Type: application/json" \
     -d '{"model":"tts-qwen3","input":"贾维斯语音链路打通","voice":"vivian"}' \
     -o /tmp/tts-gw-test.bin -w "%{http_code} %{size_download}B"
   ```
   期望 200 + ~50KB（与直连产物 `/tmp/tts-test.bin` 对比）。

4. **`aictl verify quick` 冲全绿**（当前 1 fail 即 tts）。若 asr 因模型被 idle 卸载而 fail，先 `aictl load omlx asr-whisper` 再测；是否常驻（omlx_keep）待看 verify 结果决定。

## 验证清单

- `bash -n ~/.local/bin/aetherforge-gw-guard` 无输出
- `curl :4000/health` → 200
- tts 经门面 → 200 + 字节数与直连量级一致
- `aictl verify quick` → 0 fail
- tts→asr 回环：`/tmp/tts-gw-test.bin` 喂 asr，转写文本应含"贾维斯语音链路打通"（作 P0 演示物）

## 风险与备选

- 若补 fi 后 tts 仍 401：读发布副本 `~/.local/share/aetherforge-release` 中 media_proxy 的实现，确认 env 名 `AETHERFORGE_MEDIA_AUDIO_API_KEY` / `AETHERFORGE_RERANK_API_KEY` 确实被代码消费；按实际消费方式调整。
- guard 是本机部署副本，未来 deploy 流程可能覆盖补丁 → 修复后把注入段同步回上游部署源，记入 P0 遗留清单。

## 后续（P0 收尾，本轮不做）

- observer 日报首跑并送达；度量基线入驾驶舱
- aictl heal `loop_alive` KeyError 既有 bug 记档
- dotfiles / local-ops 未 commit 改动的整理与提交（等用户确认）
- 百炼演示资源清理、magpie webdav 凭据轮换确认
