#!/usr/bin/env python3
"""proposal-triage — 提案池质量分层 + 归档工具 (第 0 段清淤, ADR-0431 D2/D3).

背景 (2026-08-28 实测): evolution-proposals/ 3951 个文件, 唯一提案文本仅 67 个
(98.3% 重复), 其中 99% 是 "Only 9 scene cards" (×3913, 场景卡实际已 20+ 张,
建议本身已过时) 和 hacker_news 快讯重复转发。真实体系提案 <10 个。

分层:
  keep    — 真提案 (体系改进/战略决策/真实待办), 按文本去重保留最新一份
  archive — 机器流水账 (重复/过时), 移至 _archive/ 子目录 (不删, 可恢复)

用法:
  python3 proposal-triage.py --analyze          # 只读分析报告
  python3 proposal-triage.py --dry-run          # 模拟归档 (显示将移动什么)
  python3 proposal-triage.py --execute          # 真实归档 (需明确授权)
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
POOL = WORKSPACE / ".omo" / "_knowledge" / "evolution-proposals"
ARCHIVE = POOL / "_archive"

# 机器噪音特征 (实测 Top 重复): 过时场景卡建议 + 外部快讯转发
NOISE_TEXT_MARKERS = (
    "Only 9 scene cards",          # ×3913, 场景卡已 20+ 张, 建议过时
    "[hacker_news]",               # ×1920, 外部信号直接进池属路由配置错误
)
# 真实信号特征: 体系评估/战略决策/健康域
REAL_TEXT_MARKERS = (
    "Evaluate",                    # A2A protocol / Apple Health API 评估
    "Address:",                    # unhealthy_service 待办
    "Domain policy evaluation",    # L3 战略决策审批 (医工交叉/三甲医院)
    "AUTHORIZE",                   # 授权动作
)


def _load_all() -> list[dict]:
    items = []
    for f in sorted(POOL.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            items.append({"file": f, "data": data})
        except (OSError, json.JSONDecodeError):
            continue
    return items


def _classify(items: list[dict]) -> dict[str, list[dict]]:
    """keep=真提案(文本去重取最新) archive=机器流水账 invalid=空/损坏."""
    seen_real: dict[str, dict] = {}
    archive: list[dict] = []
    invalid: list[dict] = []
    for it in items:
        props = (it["data"].get("proposals") or [])
        texts = [str(p.get("proposal", "")) for p in props if p.get("proposal")]
        if not texts:
            invalid.append(it)
            continue
        real_texts = [
            t for t in texts
            if any(m in t for m in REAL_TEXT_MARKERS)
            and not any(m in t for m in NOISE_TEXT_MARKERS)
        ]
        if real_texts:
            key = "|".join(sorted(real_texts))
            prev = seen_real.get(key)
            if prev is None or str(it["data"].get("generated_at", "")) > str(prev["data"].get("generated_at", "")):
                if prev is not None:
                    archive.append(prev)  # 旧的归档, 保最新
                seen_real[key] = it
            else:
                archive.append(it)
        else:
            archive.append(it)
    return {"keep": list(seen_real.values()), "archive": archive, "invalid": invalid}


def analyze() -> int:
    items = _load_all()
    layers = _classify(items)
    print(f"提案池文件总数: {len(items)}")
    print(f"  keep (真提案, 去重后): {len(layers['keep'])}")
    print(f"  archive (机器流水账): {len(layers['archive'])}")
    print(f"  invalid (空/损坏):   {len(layers['invalid'])}")
    print("\nkeep 明细:")
    for it in layers["keep"]:
        texts = [str(p.get("proposal", ""))[:70] for p in (it["data"].get("proposals") or [])]
        for t in texts[:2]:
            print(f"  - {t}")
    return 0


def run(mode: str) -> int:
    items = _load_all()
    layers = _classify(items)
    n_move = len(layers["archive"]) + len(layers["invalid"])
    print(f"{'[DRY-RUN] ' if mode == 'dry-run' else ''}将归档 {n_move} 个文件 → {ARCHIVE}/")
    if mode == "execute":
        ARCHIVE.mkdir(parents=True, exist_ok=True)
        for it in layers["archive"] + layers["invalid"]:
            shutil.move(str(it["file"]), str(ARCHIVE / it["file"].name))
        print(f"已归档 {n_move} 个; 池内保留 {len(layers['keep'])} 个真提案")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--analyze", action="store_true", help="只读分析报告")
    g.add_argument("--dry-run", action="store_true", help="模拟归档")
    g.add_argument("--execute", action="store_true", help="真实归档 (需授权)")
    args = parser.parse_args(argv)
    if args.analyze:
        return analyze()
    return run("dry-run" if args.dry_run else "execute")


if __name__ == "__main__":
    sys.exit(main())
