# Iris 连接器凭据矩阵

> 配套：`projects/kairon/packages/iris` · 抓取全景见 [external-ingest-callchain.md](./external-ingest-callchain.md)  
> 配置文件：`~/.iris/config.json`（本机路径，勿提交密钥）

## 盘点方法

```bash
# 列表状态（无密钥时 wpsnote 仅 warning，不抛 traceback）
uv run --directory projects/kairon --project packages/iris iris list

# 环境变量是否存在（不打印值）
for k in IRIS_WPSNOTE_API_KEY IRIS_ZHIHU_COOKIE WEREAD_API_KEY IRIS_WEREAD_API_KEY \
  DINGTALK_WEBHOOK_URL FEISHU_WEBHOOK_URL TELEGRAM_BOT_TOKEN POLAR_API_KEY; do
  eval "v=\${$k-}"
  printf '%s: %s\n' "$k" "${v:+SET}${v:-unset}"
done
```

## 矩阵（本机实证 2026-07-23）

| 连接器 | 可用性 | 凭据 / 配置 | 说明 |
|--------|--------|-------------|------|
| **local_files** | ✅ | `local_files.directory` → `@学习进化` | 2363+ md |
| **obsidian** | ✅ | iCloud Obsidian vault | 33 notes |
| **applenotes** | ✅ | macOS 本地 | 系统权限即可 |
| **github** | ✅ | `gh auth` | authenticated |
| **wechat** | ✅ stub | `~/.iris/data/wechat` | export_stub，非真同步 |
| **zhihu** | ✅ 未登录 | `IRIS_ZHIHU_COOKIE` | 未设 cookie 时可用但未鉴权 |
| **wpsnote** | ❌ | `IRIS_WPSNOTE_API_KEY` 或 config `wpsnote.api_key` | 缺 key → 401；需 WPS 云笔记 OpenAPI key |
| **wxread** | ❌ | `WEREAD_API_KEY` / `IRIS_WEREAD_API_KEY` | 微信读书开放平台 |
| **dingtalk** | ❌ | `DINGTALK_WEBHOOK_URL` | push-only；已实现 `is_available/status/sync` |
| **feishu** | ❌ | `FEISHU_WEBHOOK_URL` | push-only；同上 |
| **telegram** | ❌ | bot token + chat | 未配置 |
| **openhuman** | ❌ | host:7788 | 服务未起 |
| **notebooklm** | ❌ | adapter | 未加载 |
| **pocket / polar** | ❌ | 各 API key | 未配置 |
| **rss** | ❌ | blogwatcher-cli | 未安装 |

## 优先补齐建议

1. **WPS Note**：设 `IRIS_WPSNOTE_API_KEY`（与 MCP `wps-note` 同源体系）后 `iris list` 应变 ✅  
2. **飞书/钉钉**：若只需通知推送，export 对应 Webhook 即可  
3. **知乎/微信读书**：按需 cookie/API，非阻塞 local 知识闭环  

## 相关修复

| 项 | 状态 |
|----|------|
| dingtalk/feishu 缺 `is_available` → `AttributeError` | 已修（BaseConnector 接口） |
| `iris list` WPS 401 全量 traceback | 已改为 `logger.warning` |
| Obsidian/local_files 指到临时目录 | 已改回真实 vault / `@学习进化` |
