"""
BaseController — 统一控制器基类
所有域控制器继承此类，复用信号扫描、状态聚合、健康检查能力
"""
from pathlib import Path
from datetime import datetime
from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class BaseController(ABC):
    """统一控制器基类"""

    ROOT: Path = Path(".")

    def __init__(self, domain_root: Path, config: Optional[Dict] = None):
        self.domain_root = Path(domain_root)
        self.root = self.domain_root
        self.config = config or {}
        self._signals_cache = None
        self._freshness_cache = None

    def scan_signals(self) -> List[dict]:
        """扫描域信号"""
        if self._signals_cache is not None:
            return self._signals_cache

        signals = []
        signals_file = self.domain_root / "_control" / "signals.md"
        if signals_file.exists():
            content = signals_file.read_text(encoding="utf-8")
            for line in content.split("\n"):
                if line.startswith("- ") or line.startswith("* "):
                    signals.append({
                        "content": line.strip("- *").strip(),
                        "source": str(signals_file.relative_to(self.domain_root)),
                        "timestamp": datetime.fromtimestamp(signals_file.stat().st_mtime).isoformat()
                    })
        self._signals_cache = signals
        return signals

    def check_freshness(self, days: int = 90) -> List[dict]:
        """检查过期文档"""
        if self._freshness_cache is not None:
            return self._freshness_cache

        stale = []
        knowledge_dir = self.domain_root / "_knowledge"
        if knowledge_dir.exists():
            now = datetime.now().timestamp()
            threshold = days * 86400
            for md_file in knowledge_dir.rglob("*.md"):
                if md_file.name == "INDEX.md":
                    continue
                mtime = md_file.stat().st_mtime
                if now - mtime > threshold:
                    stale.append({
                        "file": str(md_file.relative_to(self.domain_root)),
                        "days_old": int((now - mtime) / 86400),
                        "last_modified": datetime.fromtimestamp(mtime).isoformat()
                    })

        stale.sort(key=lambda x: -x["days_old"])
        self._freshness_cache = stale
        return stale

    def health_check(self) -> Dict:
        """健康检查"""
        controllers = ["sensors.md", "control-rules.md", "executor-rules.md", "l4-kernel.md"]
        result = {}
        for name in controllers:
            path = self.domain_root / "_control" / name
            result[name] = {"exists": path.exists()}
        all_present = all(c["exists"] for c in result.values())
        return {"status": "healthy" if all_present else "degraded", "controllers": result}

    def aggregate_state(self) -> Dict:
        """聚合域状态"""
        return {
            "domain": self.domain_root.name,
            "timestamp": datetime.now().isoformat(),
            "controllers": self._check_controllers(),
            "signals": len(self.scan_signals()),
            "health": self.health_check(),
        }

    def _check_controllers(self) -> Dict:
        """检查控制器文件"""
        required = ["sensors.md", "control-rules.md", "executor-rules.md", "l4-kernel.md"]
        result = {}
        for name in required:
            path = self.domain_root / "_control" / name
            result[name] = {"exists": path.exists()}
        return result

    @abstractmethod
    def domain_specific_scan(self) -> Dict:
        """域特有扫描逻辑"""
        pass

    def generate_report(self) -> dict:
        """生成域控制报告"""
        signals = self.scan_signals()
        stale = self.check_freshness()
        return {
            "domain": self.domain_root.name,
            "timestamp": datetime.now().isoformat(),
            "signal_count": len(signals),
            "stale_count": len(stale),
            "stale_top5": stale[:5],
            "health": "healthy" if not stale else "attention",
        }

    def run(self) -> dict:
        """运行完整控制周期"""
        report = self.generate_report()
        report["domain_specific"] = self.domain_specific_scan()
        return report
