"""Kronos CLI — 知识摄取管线命令行入口（click）。"""

from __future__ import annotations

import os
import re
import sys
import time
from threading import Thread

import click

from kronos.fetch_router import (  # type: ignore[import-not-found]
    content_type_label,
    execute_fallback_chain,
    execute_fetch,
    list_all_methods,
    plan_for_url,
)


def _show_fetch_plan(url: str) -> None:
    chain = execute_fallback_chain(url)
    ctype = content_type_label(plan_for_url(url).content_type)
    click.echo(f"📌  {url}")
    click.echo(f"📂  类型: {ctype}")
    click.echo("")
    click.echo("📋  6 层 fallback 链:")
    for step in chain:
        label = "★ 优先" if step["priority"] == 1 else f"  ↳ fallback {step['priority'] - 1}"
        click.echo(f"  [{step['layer_name']}] {label}")
        click.echo(f"    {step['description']}")
        if step["params"].get("note"):
            click.echo(f"    📝 {step['params']['note']}")
        click.echo("")


@click.group()
def cli() -> None:
    """Kronos — 全自动知识摄取管线

    L0 原生 HTTP 自动抓取，失败自动降级到 6 层 fallback 链。
    """


@cli.command()
def status() -> None:
    """显示服务状态和集成信息"""
    methods = list_all_methods()
    l1_count = sum(1 for m in methods if m["layer"] == "L1_MCP")
    total = len(methods)
    click.echo("🔧  Kronos v0.4.0 — 自动抓取管线（L0 原生 HTTP）")
    click.echo("")
    click.echo(f"📋  抓取方法: {total}（{l1_count} 个 L1 MCP + {total - l1_count} 个增强层）")
    click.echo("")
    for m in methods:
        click.echo(f"  [{m['layer']}] {m['description']}")
    try:
        from kronos.fetch_router import check_ollama

        ok, info = check_ollama()
    except Exception:
        ok, info = False, "模块导入失败"
    click.echo("")
    click.echo(f"🧠  Ollama: {'✅ ' + info if ok else '❌ ' + info}")
    click.echo("🔗  Gateway: ~/Workspace/gateway/bin/")
    click.echo("🔗  KOS:     ~/Workspace/kos/")
    click.echo("🔗  Vault:   Obsidian (直接文件写入)")
    click.echo("🔗  WPS:     via Gateway MCP")
    click.echo("🔗  Browser: CloakBrowser (pip install cloakbrowser playwright)")


@cli.command()
@click.argument("url")
@click.option("--plan", "dry_run", is_flag=True, help="只出方案不执行")
def fetch(url: str, dry_run: bool = False) -> None:
    """5 层自动抓取 URL"""
    ctype = content_type_label(plan_for_url(url).content_type)
    click.echo("📥  Kronos v0.4 — 自动抓取管线")
    click.echo("══════════════════════════════════")
    click.echo(f"📌  {url}")
    click.echo(f"📂  类型: {ctype}")
    click.echo("")
    if dry_run:
        chain = execute_fallback_chain(url)
        click.echo("📋  Fallback 链:")
        for step in chain:
            label = "★" if step["priority"] == 1 else f"  ↳#{step['priority'] - 1}"
            click.echo(f"  {label} [{step['layer_name']}] {step['description']}")
        click.echo("")
        click.echo("💡  --plan 模式，不执行。去掉 --plan 自动运行 L0→L0b→方案。")
        return

    click.echo("🔧  尝试 L0 原生 HTTP...")
    _spinning = True

    def _spinner() -> None:
        for c in "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏":
            if not _spinning:
                break
            sys.stdout.write(f"\r  {c} 抓取中...")
            sys.stdout.flush()
            time.sleep(0.1)
        sys.stdout.write("\r" + " " * 30 + "\r")

    t = Thread(target=_spinner, daemon=True)
    t.start()
    result = execute_fetch(url)
    _spinning = False
    if result.get("ok"):
        method = result["method"]  # type: ignore[reportTypedDictNotRequiredAccess]
        title = result.get("title", "")
        content = result["content"]  # type: ignore[reportTypedDictNotRequiredAccess]
        text = result.get("text", content[:50000])
        markdown = result.get("markdown", text)
        content_preview = markdown[:500]
        click.echo(f"  ✅ {method} 成功")
        click.echo(f"  📄 HTML: {len(content)} 字符 → 纯文本: {len(text)} 字符")
        click.echo(f"     Markdown: {len(markdown)} 字符")
        if title:
            click.echo(f"  📌 标题: {title}")
        click.echo("")
        click.echo("🧠  Ollama 提取... (输入: {len(markdown)} 字)")
        ollama_ok = False
        ollama_err = ""
        try:
            from kronos.fetch_router import check_ollama

            ok, info = check_ollama()
            if ok:
                ollama_ok = True
        except Exception as e:
            ollama_err = str(e)
        if ollama_ok:
            click.echo("  ✅ Ollama 已连接 — 提取中...")
            try:
                from kronos.extractor import ExtractedContent, extract  # type: ignore[import-not-found]

                extracted = extract(markdown[:8000], model=None)
                if extracted.get("title") or extracted.get("summary"):
                    ec = ExtractedContent(extracted)
                    click.echo(f"  📌 标题: {ec.title}")
                    click.echo(f"  📝 概括: {ec.summary}")
                    if ec.key_points:
                        click.echo(f"  🔑 要点 ({len(ec.key_points)}):")
                        for p in ec.key_points[:3]:
                            click.echo(f"      • {p}")
                    if ec.entities.get("concepts"):
                        click.echo(f"  🏷️  概念: {', '.join(ec.entities['concepts'][:5])}")
                    if ec.quotes:
                        click.echo(f"  💬 金句: {len(ec.quotes)} 条")
                    if ec.tags:
                        click.echo(f"  🏷️  标签: {', '.join(ec.tags[:5])}")
                else:
                    click.echo(f"  ⚠️  Ollama 返回无有效提取: {str(extracted)[:200]}")
            except Exception as e:
                click.echo(f"  ❌ 提取异常: {e}")
        else:
            click.echo(f"  ❌ Ollama 未连接{' (' + ollama_err + ')' if ollama_err else ''}")
        click.echo("")
        click.echo("📄  Markdown 预览 (前500字):")
        click.echo(f"  {content_preview}")
        click.echo("  ...")
        click.echo("")
        click.echo("💡  要继续处理并分发到 vault/WPS 吗？")
    else:
        chain = result.get("plan", [])
        error = result.get("error", "未知错误")
        click.echo("  ❌ L0 原生 HTTP 失败")
        click.echo("  ❌ L0b Jina Reader 失败")
        click.echo(f"  ⚠️  {error}")
        click.echo("")
        click.echo("📋  剩余方案链:")
        for step in chain:
            if step["priority"] <= 2:
                continue
            label = f"  ↳#{step['priority'] - 2}"
            click.echo(f"  {label} [{step['layer_name']}] {step['description']}")
            if step["params"].get("note"):
                click.echo(f"    📝 {step['params']['note']}")
        click.echo("")
        click.echo("💡  无法自动抓取，需要 MCP 工具或手动操作。")


@cli.command()
@click.argument("url")
def route(url: str) -> None:
    """查看 URL 的完整 fallback 链"""
    _show_fetch_plan(url)


@cli.command()
@click.argument("query", nargs=-1, required=True)
def search(query: tuple[str, ...]) -> None:
    """DuckDuckGo 免费搜索"""
    q = " ".join(query)
    try:
        from kronos.fetch_router import _try_web_search

        results = _try_web_search(q)
        click.echo(f"🔍  DuckDuckGo 搜索结果: {len(results)} 条")
        click.echo("")
        for i, r in enumerate(results[:10], 1):
            click.echo(f"  {i}. {r['title']}")
            click.echo(f"     {r['url']}")
            click.echo("")
    except Exception as e:
        click.echo(f"❌ 搜索失败: {e}")


@cli.command()
@click.option("--save", is_flag=True, help="保存内容到桌面")
def batch(save: bool) -> None:
    """批量处理 pending 列表"""
    from kronos.config import get_config  # type: ignore[import-not-found]

    pending_file = get_config().pending_links_path
    if not os.path.exists(pending_file):
        click.echo(f"❌ 找不到 pending 列表: {pending_file}")
        return
    save_dir = None
    if save:
        save_dir = os.path.expanduser("~/Desktop/kronos_batch")
        os.makedirs(save_dir, exist_ok=True)
        click.echo(f"💾 内容将保存到: {save_dir}/")
    with open(pending_file) as f:
        text = f.read()
    lines = text.split("\n")
    pending = []
    for line in lines:
        if "https://" in line and "✅" not in line and "⏭️" not in line:
            for u in re.findall(r"https?://[^\s\)\|]+", line):
                if u not in pending:
                    pending.append(u)
    total = len(pending)
    success = 0
    failed = 0
    click.echo(f"📋  pending 列表: {total} 条待处理")
    click.echo("══════════════════════════════════")
    click.echo("")
    for i, url in enumerate(pending, 1):
        click.echo(f"[{i}/{total}] 📥 {url}")
        result = execute_fetch(url)
        if result.get("ok"):
            success += 1
            method = result["method"]  # type: ignore[reportTypedDictNotRequiredAccess]
            title = result.get("title", "")[:60]
            markdown = result.get("markdown", "")
            click.echo(f"  ✅ {method} → {title}")
            if save_dir and markdown:
                safe = re.sub(r"[^\w\- ]", "", title)[:40].strip()
                fpath = os.path.join(save_dir, f"{i:02d}-{safe or 'article'}.md")
                with open(fpath, "w") as sf:
                    sf.write(f"# {title}\n\n{markdown}\n")
                click.echo(f"     💾 → {fpath}")
        else:
            failed += 1
            click.echo("  ❌ 所有方法失败")
        click.echo("")
    click.echo("══════════════════════════════════")
    click.echo(f"📊 完成: {success} ✅ / {failed} ❌ / {total} 总计")


@cli.command()
@click.argument("title")
@click.argument("content", nargs=-1, required=False)
def insight(title: str, content: tuple[str, ...] | None = None) -> None:
    """生成洞察报告"""
    body = " ".join(content) if content else ""
    if not body and not sys.stdin.isatty():
        body = sys.stdin.read().strip()
    from kronos.insight_engine import format_insight_report, generate_insight  # type: ignore[import-not-found]

    report = generate_insight(title, body)
    click.echo(format_insight_report(report))


@cli.command()
def tools() -> None:
    """列出所有抓取方法"""
    for m in list_all_methods():
        click.echo(f"  [{m['layer']}] {m['name']}")
        click.echo(f"    {m['description']}")


@cli.command()
def layers() -> None:
    """架构说明"""
    click.echo("""
Kronos 抓取引擎 — 全自动顺序尝试
══════════════════════════════════

HTTP 层 (无需外部依赖):
  L0  native_http      httpx GET，基础抓取
  L0.5 scrapling       StealthyFetcher TLS 指纹伪装
  L0b jina_reader      r.jina.ai/<URL> 代理
  L0c duckduckgo       免费搜索 API

浏览器层 (需安装):
  L4  cloakbrowser     CloakBrowser (58 处反爬补丁)
  L4b playwright       降级方案

MCP 层 (对话环境):
  L1  metaso/GitHub/CSDN/掘金/LinuxDo 等 MCP 工具

全部尝试失败 → 输出可执行方案链
""")


def main() -> None:
    print("⚠️ Kronos 独立 CLI 已弃用，请使用 cockpit 替代", file=sys.stderr)
    cli()


if __name__ == "__main__":
    main()
