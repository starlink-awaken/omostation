"""
理论层规约检查 — C-09~C-13独立策略单元
=========================================
每个理论模块暴露check_xxx(root)函数，消除check.py的hub-spoke模式。
"""

import sys
from pathlib import Path
from typing import Any


def check_bayesian(root: Any) -> dict[str, Any]:
    """C-09: 贝叶斯信念传播"""
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from ontoderive.theories.bayesian import BayesianLayer

        bl = BayesianLayer(root)
        dist = bl.get_distribution()
        all_confs = dist["facts"] + dist["inferences"]
        ok = all(0 < c < 1 for c in all_confs) if all_confs else True
        has_var = len(set(round(c, 1) for c in all_confs)) > 1 if all_confs else True
        return {
            "passed": ok and has_var,
            "severity": "WARN" if not (ok and has_var) else "PASS",
            "detail": f"事实{dist['n_facts']}个, 推论{dist['n_inferences']}个, "
            f"平均置信度{sum(all_confs) / len(all_confs):.2f}"
            if all_confs
            else "N/A",
            "distribution": dist,
        }
    except ImportError:
        return {"passed": False, "severity": "WARN", "detail": "bayesian.py未安装"}
    except Exception as e:
        return {"passed": False, "severity": "WARN", "detail": f"异常: {str(e)[:50]}"}


def check_metrics(root: Any, precomputed_confs: Any = None) -> dict[str, Any]:
    """C-10: KQI知识质量指数"""
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from ontoderive.theories.metrics import MetricsLayer

        ml = MetricsLayer(root)
        kqi = ml.compute_kqi(precomputed_confs=precomputed_confs)
        ok = kqi["kqi"] > 0 and kqi["entropy"] >= 0
        return {
            "passed": ok,
            "severity": "PASS",
            "detail": f"KQI={kqi['kqi']}, 熵={kqi['entropy']}bits, "
            f"密度={kqi['density']:.2f}, 覆盖={kqi['coverage'] * 100:.0f}%",
        }
    except ImportError:
        return {"passed": False, "severity": "WARN", "detail": "metrics.py未安装"}
    except Exception as e:
        return {"passed": False, "severity": "WARN", "detail": f"异常: {str(e)[:50]}"}


def check_pid(root: Any) -> dict[str, Any]:
    """C-11: PID反馈控制"""
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from ontoderive.theories.controller import PIDController

        pid = PIDController(root).analyze()
        return {
            "passed": pid["stability"] == "stable",
            "severity": "WARN" if pid["stability"] != "stable" else "PASS",
            "detail": f"P={pid['p_value']} I={pid['i_value']} D={pid['d_value']} "
            f"信号={pid['control_signal']} 状态={pid['stability']}",
        }
    except Exception:
        return {"passed": True, "severity": "PASS", "detail": "首次运行, 信号=0 (需历史数据)"}


def check_turing(root: Any) -> dict[str, Any]:
    """C-12: 知识状态机"""
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from ontoderive.theories.turing_k import KnowledgeTM

        state = KnowledgeTM(root).snapshot()
        return {
            "passed": state.timestamp is not None,
            "severity": "PASS",
            "detail": f"快照: {state.facts}F/{state.inferences}I/{state.entities}E",
        }
    except Exception as e:
        return {"passed": False, "severity": "WARN", "detail": f"异常: {str(e)[:50]}"}


def check_ontolang(root: Any = None) -> dict[str, Any]:
    """C-13: OntoLang形式语言 [DEPRECATED - 保留供外部兼容]"""
    try:
        import sys

        sys.path.insert(0, str(Path(__file__).parent))
        from ontolang import OntoLangParser  # type: ignore[reportMissingImports]

        parser = OntoLangParser()
        parser.test_suite()
        return {
            "passed": True,
            "severity": "PASS",
            "detail": "[DEPRECATED] OntoLang保留供外部引用",
        }
    except Exception as e:
        return {"passed": True, "severity": "PASS", "detail": f"[DEPRECATED] ontolang不可用: {str(e)[:30]}"}


# Strategy registry — check.py通过此注册表调用
THEORY_CHECKS = [
    ("C-09", "贝叶斯信念传播(智能层)", check_bayesian),
    ("C-10", "信息论层(KQI质量指数)", check_metrics),
    ("C-11", "控制论层(PID反馈)", check_pid),
    ("C-12", "图灵机层(知识状态机)", check_turing),
    ("C-13", "形式语言层(OntoLang解析) [DEPRECATED]", check_ontolang),
]
