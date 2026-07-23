# 外部信息 / 数据抓取 — 调用白盒与 smoke

> 更新: 2026-07-23  
> 范围: 开放 URL 抓取 · 深度研究 · 平台同步 · ToolBox 自媒体爬虫  
> 配套: `docs/FUNCTIONAL-CAPABILITY-MAP.md` §1–2 · `projects/agora/etc/bos-services.yaml`

---

## 1. 端到端调用链

```text
用户 / Agent
  │
  ├─ cockpit import <url|file>          # L3 产品入口
  │     └─ URL → kronos.execute_fetch   # 优先多层抓取
  │           └─ fallback urllib
  │                 └─ cockpit research 存储
  │
  ├─ cockpit kairon kronos fetch <url>  # 显式摄取 CLI
  │     └─ projects/kairon/packages/kronos
  │
  ├─ cockpit kairon minerva research …  # 多源搜索研究
  │     └─ SearXNG / Metaso / Exa / Scholar / arXiv / DDG
  │
  ├─ cockpit kairon iris list|sync      # 账号侧连接器
  │
  ├─ bos://memory/kronos/* · kos/* · minerva/*
  │     └─ agora BOS resolve → stdio/MCP proxy
  │
  └─ bos://capability/media-crawler/crawl
  │     └─ $TOOLBOX_ROOT/pipelines/media-crawler/main.py
  └─ bos://capability/last30days-skill/fetch
        └─ Agent Skill 宿主加载 SKILL.md（非常驻 MCP）
```

### 1.1 Kronos 抓取层（进程内）

| 顺序 | 方法 | 说明 |
|------|------|------|
| 1 | `native_http` | httpx + 浏览器 UA |
| 2 | `scrapling` | TLS 指纹伪装 |
| 3 | `jina_reader` | `r.jina.ai/<URL>` |
| 4 | `cloakbrowser` | 反爬 Chromium |
| 5 | `playwright` | 通用浏览器 |

全失败 → 返回 MCP 方案链（L1 metaso / open-websearch / web_fetch 等），不硬崩。

### 1.2 BOS 路由（agora）

| URI | 状态 | 真执行面 |
|-----|------|----------|
| `bos://memory/kronos/mcp-server` | active | `uv run -m kronos.mcp_server` |
| `bos://memory/kronos/ingest` | active | `kronos.cli ingest` |
| `bos://memory/minerva/mcp-server` | active | minerva MCP |
| `bos://memory/kos/ingest` | active | kos CLI |
| `bos://capability/media-crawler/crawl` | active · `i0_route: host_cli` | ToolBox `main.py` |
| `bos://capability/last30days-skill/fetch` | active · `i0_route: skill_host` | Skill 宿主 |

`i0_route` 取值:

- `pending` — 仅声明，未标明执行模型  
- `host_cli` — 主机 CLI（cwd 在 ToolBox），非 agora 内嵌 MCP  
- `skill_host` — Agent Skill 加载执行  

---

## 2. Smoke 命令（本机已验证 2026-07-23）

```bash
# Kronos 路由计划 + 真抓取
uv run --directory projects/kairon python -m kronos.cli route https://example.com
uv run --directory projects/kairon python -m kronos.cli fetch https://example.com
# 期望: native_http 成功，标题 Example Domain

# cockpit 入口（修复后应含 kronos）
uv run --directory projects/cockpit python -m cockpit kairon kronos tools
uv run --directory projects/cockpit python -m cockpit import https://example.com

# Iris 连接器清单
uv run --directory projects/kairon python -m iris.cli list
# 本机实证: applenotes/github/wechat/zhihu 可用；WPS Note 401；多数需凭据

# Minerva 健康
uv run --directory projects/kairon python -m minerva.cli check
# 本机: Ollama ✅ · SearXNG ⚠️ · Neo4j ⚠️ · API keys 4/4

# ToolBox media-crawler 入口（需 playwright）
cd "${TOOLBOX_ROOT:-$HOME/ToolBox}/pipelines/media-crawler" && python3 main.py --help
# 未装 playwright 时 ModuleNotFoundError — 属环境债，非注册错误

# last30days skill 存在性
test -f "${TOOLBOX_ROOT:-$HOME/ToolBox}/skills/last30days-skill/skills/last30days/SKILL.md" && echo ok
```

---

## 3. 已知缺口（按优先级）

| ID | 缺口 | 处置建议 |
|----|------|----------|
| G1 | media-crawler 缺 playwright 依赖 | ToolBox venv 已装；须 **在项目根目录** 跑 `main.py`（`libs/*.js` 相对路径） |
| G2 | SearXNG / Neo4j 未常驻 | SearXNG+Neo4j 本机可起；见 [minerva-local.md](./minerva-local.md) |
| G3 | cockpit `bos capability invoke` 仍是占位提示 | 接 agora `resolve_bos_uri` 真 invoke |
| G4 | iris 多连接器未配置 auth | 矩阵见 [iris-credentials-matrix.md](./iris-credentials-matrix.md) |
| G5 | kos ingest parsers 迁移中 | 见 `packages/kos/src/kos/ingest/TODO.md` |
| G6 | last30days 无 stdio MCP 模块 | 保持 skill_host；勿伪造成 `python -m last30days` |
| G7 | media-crawler 真爬需登录态 | headless + 过期 profile 会失败（`float.encode` / 无二维码）；需交互扫码或 cookie — 见 [media-crawler-login.md](./media-crawler-login.md) |

---

## 4. 产品入口速查

| 意图 | 命令 |
|------|------|
| 甩链接入库 | `cockpit import <url>` |
| 只抓不落产品库 | `cockpit kairon kronos fetch <url>` |
| 主题研究 | `cockpit research "主题"` / `cockpit kairon minerva research …` |
| 平台同步 | `cockpit kairon iris sync` |
| 自媒体批量 | ToolBox media-crawler `main.py`（登录态 + 反爬） |
| 热度信息流 | last30days Skill（Agent 宿主） |

---

## 5. 环境落地备注（本机）

| 组件 | 命令 | 状态 |
|------|------|------|
| SearXNG | `cd projects/kairon/packages/minerva/docker && docker compose up -d searxng` | `minerva-searxng` **healthy**（wget spider `/`） |
| Neo4j | `docker compose --profile full up -d neo4j` | `minerva-neo4j` **healthy**；默认密码 `changeme`；`minerva check` 5/5 |
| media-crawler venv | 项目根 `.venv` + playwright | 启动 OK；**真爬**需有效登录（见 G7） |
| iris | `iris list` | local_files/obsidian/applenotes/github 绿；见 [iris-credentials-matrix.md](./iris-credentials-matrix.md) |
| cockpit capability invoke | `cockpit bos capability invoke media-crawler` | 执行 BOS YAML `command`（`--help` smoke） |

media-crawler 最小尝试（需登录；headless 无有效 cookie 会失败）：

```bash
cd "${TOOLBOX_ROOT:-$HOME/ToolBox}/pipelines/media-crawler"
.venv/bin/python main.py --platform xhs --type search --keywords "测试" \
  --crawler_max_notes_count 1 --get_comment false --headless true --save_data_option jsonl
# 交互扫码：去掉 --headless，刷新 browser_data 登录态
```

---

## 6. 变更记录

| 日期 | 变更 |
|------|------|
| 2026-07-23 | 实证 smoke；cockpit 挂 kronos；import 优先 kronos；修正 media-crawler/last30days 伪 `python -m` 命令；本 callchain 文档 |
| 2026-07-23 | 全面落地：SearXNG 起服、media-crawler venv、`bos capability invoke` 真执行、子模块/文档提交 |
| 2026-07-23 | Neo4j healthcheck 修复 + volume 重建；iris 连接器/噪音；凭据矩阵；真爬 G7 |
| 2026-07-23 | kairon #13 子模块指针；media-crawler 交互登录 runbook |
