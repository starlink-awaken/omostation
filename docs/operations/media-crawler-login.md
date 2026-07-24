# MediaCrawler 登录与最小真爬

> 路径：`$TOOLBOX_ROOT/pipelines/media-crawler`（默认 `~/ToolBox/pipelines/media-crawler`）  
> 全景： [external-ingest-callchain.md](./external-ingest-callchain.md) G7

## 为什么 headless 会失败

2026-07-23 实证：

1. 必须在**项目根目录**运行（`libs/*.js` 相对路径）
2. 已有 `browser_data/xhs_user_data_dir` 仍可能登录失效
3. 失效时 `pong` 报 `'float' object has no attribute 'encode'`（签名链路/cookie 异常）
4. headless 下 `login_by_qrcode` 找不到二维码 → 无法非交互恢复

## 人工刷新登录态（推荐）

在本机终端（**非 headless**，能看到浏览器窗口）：

```bash
cd "${TOOLBOX_ROOT:-$HOME/ToolBox}/pipelines/media-crawler"
source .venv/bin/activate   # 或直接用 .venv/bin/python

# 有界面扫码 — 成功后会写入 browser_data
python main.py \
  --platform xhs \
  --type search \
  --keywords "测试" \
  --crawler_max_notes_count 1 \
  --get_comment false \
  --headless false \
  --save_data_option jsonl \
  --lt qrcode
```

扫码成功后，再跑 headless 复用状态：

```bash
python main.py \
  --platform xhs \
  --type search \
  --keywords "人工智能" \
  --crawler_max_notes_count 1 \
  --get_comment false \
  --headless true \
  --save_data_option jsonl
```

## Cookie 登录（可选）

从已登录浏览器复制 Cookie 字符串：

```bash
python main.py --platform xhs --lt cookie --cookies '<name=value; ...>' \
  --type search --keywords "测试" --crawler_max_notes_count 1 \
  --get_comment false --headless true --save_data_option jsonl
```

勿把 cookie 写入 git 或 PR。

## 产物位置

- `data/xhs/jsonl/` — 历史样例：`search_contents_2026-07-20.jsonl`（曾成功过）
- `browser_data/xhs_user_data_dir/` — Playwright 持久化配置（本地，gitignore）

## Agent 边界

Agent 无法完成需扫码/人机验证的真爬；可做 venv、`--help`、BOS invoke smoke。真业务验收保留给人机步骤。
