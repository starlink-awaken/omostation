#!/usr/bin/env python3
"""
BaseController — 统一控制器基类
消除三域控制器 80% 重复代码。

子类只需定义 ROOT 路径和域特定规则，即可复用：
- 信号扫描 (scan_signals)
- 新鲜度检查 (check_freshness)
- 控制规则匹配 (match_cr)
- 报告生成 (generate_report)
"""

from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import re


class BaseController:
    """统一控制器基类"""

    ROOT: Path = Path(".")  # 子类必须覆盖

    # 控制规则 (子类可扩展)
    CR_RULES: Dict[str, dict] = {
        "stale_warning": {
            "condition": lambda d: d.get("days_old", 0) > 90,
            "severity": "warning",
            "action": "notify",
        },
        "stale_critical": {
            "condition": lambda d: d.get("days_old", 0) > 180,
            "severity": "critical",
            "action": "escalate",
        },
        "signal_backlog": {
            "condition": lambda d: d.get("signal_count", 0) > 10,
            "severity": "warning",
            "action": "triage",
        },
    }

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else self.ROOT
        self._signals_cache = None
        self._freshness_cache = None

    # === 传感器 (子类可覆盖) ===

    def scan_signals(self) -> List[dict]:
        """扫描域信号（通用实现）"""
        if self._signals_cache is not None:
            return self._signals_cache

        signals = []
        signals_file = self.root / "_control" / "signals.md"
        if signals_file.exists():
            content = signals_file.read_text(encoding="utf-8")
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("- ") or line.startswith("* "):
                    signals.append(
                        {
                            "content": line.lstrip("- *").strip(),
                            "source": str(signals_file.relative_to(self.root)),
                            "timestamp": datetime.fromtimestamp(
                                signals_file.stat().st_mtime
                            ).isoformat(),
                        }
                    )
        self._signals_cache = signals
        return signals

    def check_freshness(self, days: int = 90) -> List[dict]:
        """检查过期文档（通用实现）"""
        if self._freshness_cache is not None:
            return self._freshness_cache

        stale = []
        knowledge_dir = self.root / "_knowledge"
        if knowledge_dir.exists():
            now = datetime.now().timestamp()
            threshold = days * 86400

            for md_file in knowledge_dir.rglob("*.md"):
                if md_file.name == "INDEX.md":
                    continue
                mtime = md_file.stat().st_mtime
                if now - mtime > threshold:
                    stale.append(
                        {
                            "file": str(md_file.relative_to(self.root)),
                            "days_old": int((now - mtime) / 86400),
                            "last_modified": datetime.fromtimestamp(
                                mtime
                            ).isoformat(),
                        }
                    )

        stale.sort(key=lambda x: -x["days_old"])
        self._freshness_cache = stale
        return stale

    # === 控制规则匹配 ===

    def match_cr(self, data: dict) -> List[Tuple[str, dict]]:
        """匹配控制规则，返回触发的规则列表"""
        triggered = []
        for rule_name, rule in self.CR_RULES.items():
            try:
                if rule["condition"](data):
                    triggered.append((rule_name, rule))
            except Exception:
                pass
        return triggered

    # === 执行器 ===

    def generate_report(self) -> dict:
        """生成域控制报告"""
        signals = self.scan_signals()
        stale = self.check_freshness()

        # 匹配规则
        triggered = self.match_cr(
            {
                "signal_count": len(signals),
                "stale_count": len(stale),
                "days_old": stale[0]["days_old"] if stale else 0,
            }
        )

        return {
            "domain": self.root.name,
            "timestamp": datetime.now().isoformat(),
            "signal_count": len(signals),
            "stale_count": len(stale),
            "stale_top5": stale[:5],
            "triggered_rules": [r[0] for r in triggered],
            "health": "healthy" if not triggered else "attention",
        }

    # === 域特有逻辑（子类覆盖） ===

    def domain_specific_scan(self) -> dict:
        """域特有扫描逻辑（子类必须覆盖）"""
        return {}

    def run(self) -> dict:
        """运行完整控制周期"""
        report = self.generate_report()
        report["domain_specific"] = self.domain_specific_scan()
        return report


if __name__ == "__main__":
    import json

    # 默认运行当前域
    controller = BaseController(Path.cwd())
    print(json.dumps(controller.run(), ensure_ascii=False, indent=2))
