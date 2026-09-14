"""
OntoDerive 上下文提取器 — 从本地文件/网页提取事实
====================================================
支持: md/txt/html文件的内容提取和事实识别

用法:
    python3 engine/extractor.py --input ./docs/ --output facts/data.md
    python3 engine/extractor.py --url https://example.com --output facts/
"""

import re
from pathlib import Path
from typing import Any


class ContextExtractor:
    def __init__(self) -> None:
        self.facts: list[Any] = []
        self.fact_counter = 1

    def extract_from_text(self, text: Any, source: Any = "auto") -> Any:
        """从文本中提取数值事实"""
        # 提取形如 "470项成果" "220亿基金" "133名" 的数字陈述
        patterns = [
            (r"(\d+(?:\.\d+)?)\s*(项|个|所|家|名|亿|万|%|次|天|周|月|年)", "auto"),
            (r"([一二三四五六七八九十百千万亿]+)\s*(项|个|所|家|名|亿|万)", "auto"),
        ]
        found = []
        for pattern, tag in patterns:
            for m in re.finditer(pattern, text):
                num = m.group(1)
                unit = m.group(2) if len(m.groups()) > 1 else ""
                # 获取上下文
                start = max(0, m.start() - 40)
                end = min(len(text), m.end() + 40)
                context = text[start:end].replace("\n", " ").strip()
                if len(context) > 10 and context not in found:
                    found.append(context)
                    self.facts.append(
                        {
                            "id": f"D-F{self.fact_counter}",
                            "value": f"{num}{unit}",
                            "context": context[:80],
                            "source": source,
                        }
                    )
                    self.fact_counter += 1
        return found

    def extract_from_file(self, filepath: Any) -> Any:
        """从文件提取事实"""
        text = Path(filepath).read_text("utf-8", errors="ignore")
        return self.extract_from_text(text, source=filepath)

    def extract_from_dir(self, directory: Any, extensions: Any = (".md", ".txt", ".html")) -> None:
        """从目录递归提取"""
        dp = Path(directory)
        for f in sorted(dp.rglob("*")):
            if f.suffix in extensions and f.is_file():
                self.extract_from_file(str(f))

    def to_markdown(self) -> Any:
        """输出为OntoDerive facts/data.md格式"""
        lines = ["| 编号 | 数据 | 数值 | 来源 |"]
        lines.append("|------|------|------|------|")
        for f in self.facts:
            lines.append(f"| {f['id']} | {f['context'][:30]} | {f['value']} | {f['source']} |")
        return "\n".join(lines)

    def save(self, output_path: Any) -> Any:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(self.to_markdown(), encoding="utf-8")
        print(f"[extract] ✅ {len(self.facts)} facts → {output_path}")
        return len(self.facts)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OntoDerive 上下文提取器")
    parser.add_argument("--input", help="输入目录")
    parser.add_argument("--url", help="输入URL(需配合web_fetch)")
    parser.add_argument("--output", default="facts/data.md", help="输出文件")
    args = parser.parse_args()

    extractor = ContextExtractor()
    if args.input:
        extractor.extract_from_dir(args.input)
    if args.url:
        try:
            from urllib.request import urlopen

            text = urlopen(args.url).read().decode("utf-8", errors="ignore")
            extractor.extract_from_text(text, source=args.url)
        except Exception as e:
            print(f"[extract] ⚠️ URL提取失败: {e}")

    extractor.save(args.output)
