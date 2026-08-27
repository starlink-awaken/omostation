"""
规则加载器 — Rule Loader (LP4 自组织)
=====================================
从YAML/JSON声明文件加载推理规则，使规则可插拔而不需改源码。

支持格式:
  id: R22
  name: trend_detection
  type: threshold_alert
  category: analytics
  description: 检测指标的显著变化趋势
  premises: ["has_numeric_value", "change > 20%"]
  conclusion_template: "{desc}从{old}变为{new}, 变化{change}%, 趋势{trend}"
  confidence: 0.75
  method: rule_loader
"""

import json
import re
from pathlib import Path
from typing import Any

_RULES_DIR = Path(__file__).parent / "rules"
_HAS_NUM_RE = re.compile(r"\d+\.?\d*")
_NUM_CMP_RE = re.compile(r"(\w+)\s*(>=|<=|>|<|==|!=)\s*(\d+)")


class RuleLoader:
    """从YAML/JSON声明文件加载推理规则"""

    def __init__(self, rules_dir: str | None = None) -> None:
        self.rules_dir = Path(rules_dir) if rules_dir else _RULES_DIR
        self.rules: list[dict] = []
        self._loaded = False

    def load_all(self) -> list[dict]:
        """自动扫描 rules/ 目录加载所有 YAML 规则文件"""
        if self._loaded:
            return self.rules
        self._loaded = True
        self.rules = []
        if not self.rules_dir.is_dir():
            return []
        for f in sorted(self.rules_dir.glob("*.yaml")):
            try:
                self.load_yaml(str(f))
            except Exception as e:
                print(f"[RuleLoader] 加载 {f.name} 失败: {e}")
        return self.rules

    def load_json(self, path: str) -> list[dict]:
        """从JSON文件加载规则"""
        data = json.loads(Path(path).read_text())
        loaded = data if isinstance(data, list) else [data]
        self.rules.extend(self._validate(loaded))
        return loaded

    def load_yaml(self, path: str) -> list[dict]:
        """从YAML文件加载规则"""
        try:
            import yaml

            data = yaml.safe_load(Path(path).read_text())
        except ImportError:
            data = self._load_yaml_simple(path)
        loaded = data if isinstance(data, list) else [data]
        self.rules.extend(self._validate(loaded))
        return loaded

    def _load_yaml_simple(self, path: str) -> list[dict]:
        """简易YAML解析器 — 零依赖fallback"""
        text = Path(path).read_text()
        rules = []
        current: dict[str, object] = {}
        for line in text.split("\n"):
            line = line.rstrip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("- id:") or (line.startswith("id:") and current):
                if current:
                    rules.append(dict(current))
                current = {}
            if ":" in line and not line.startswith(" "):
                key, _, val = line.partition(":")
                key, val = key.strip(), val.strip()
                if val.startswith('"') and val.endswith('"'):
                    current[key] = val[1:-1]
                elif val.startswith("[") and val.endswith("]"):
                    current[key] = [v.strip().strip('"') for v in val[1:-1].split(",")]
                elif val.replace(".", "").isdigit():
                    current[key] = float(val) if "." in val else int(val)
                elif val in ("true", "false"):
                    current[key] = val == "true"
                else:
                    current[key] = val
        if current:
            rules.append(dict(current))
        self.rules.extend(self._validate(rules))
        return rules

    def _validate(self, rules: list[dict]) -> list[dict]:
        """验证规则基本结构"""
        required = {"id", "name", "type"}
        valid = []
        for r in rules:
            missing = required - set(r.keys())
            if missing:
                print(f"[RuleLoader] 规则{r.get('id', '?')}缺少字段: {missing}")
            else:
                valid.append(r)
        return valid

    def get_by_type(self, rule_type: str) -> list[dict]:
        """按类型获取规则"""
        return [r for r in self.rules if r.get("type") == rule_type]

    def get_by_category(self, category: str) -> list[dict]:
        return [r for r in self.rules if r.get("category") == category]

    # ── 前提匹配 ──

    def match_premises(self, rule: dict, facts: dict, inferences: dict) -> bool:
        """评估规则的前提是否满足当前事实/推论"""
        premises = rule.get("premises", [])
        if not premises:
            return True  # 无前提 → 总是触发

        n_facts = len(facts)
        n_infs = len(inferences)

        for p in premises:
            if not self._eval_premise(p, facts, inferences, n_facts, n_infs):
                return False
        return True

    _HAS_NUM = _HAS_NUM_RE  # 向后兼容引用

    def _eval_premise(self, premise: str, facts: dict, inferences: dict, n_facts: int, n_infs: int) -> bool:
        """评估单条前提"""
        p = premise.strip()

        # 无前提
        if not p:
            return True

        # 硬编码前提
        if p == "has_numeric_value":
            return any(self._HAS_NUM.search(str(v.get("value", ""))) for v in facts.values())
        if p == "same_domain":
            return n_facts >= 2
        if p in ("shared_premises >= 2",):
            return n_infs >= 2
        if p == "referenced_id_not_found":
            return n_infs > 0
        if p in ("premise_count < 3", "premise_count < 2"):
            return n_facts < 3
        if p == "value > threshold":
            return n_facts > 0
        if p == "derivation_chain_incomplete":
            return n_infs > 0
        if p == "all_premises_valid":
            return n_facts > 0 and n_infs > 0
        if p == "depends_on_chain":
            return n_infs >= 2
        if p == "id_prefix_in_hierarchy":
            return bool(facts) or bool(inferences)
        if p == "has_reference_count":
            return n_infs > 0
        if p in ("similar_conclusions >= 2", "shared_premises >= 2"):
            return n_infs >= 2
        if p == "fact_references_count":
            return n_facts > 0 and n_infs > 0
        if p in ("divergent_conclusions",):
            return n_infs >= 2
        if p in ("inference_chain_length >= 2",):
            return n_infs >= 2

        # 数值比较前提: "key > N", "key < N" 等
        m = _NUM_CMP_RE.match(p)
        if m:
            key, op, val_str = m.group(1), m.group(2), m.group(3)
            val = float(val_str)
            actual = {"n_facts": n_facts, "n_infs": n_infs}.get(key)
            if actual is None:
                return True  # unknown key → skip
            if op == ">=":
                return actual >= val
            if op == ">":
                return actual > val
            if op == "<=":
                return actual <= val
            if op == "<":
                return actual < val
            if op == "==":
                return actual == val
            if op == "!=":
                return actual != val

        return True  # unknown premise → pass through

    # ── 规则执行 ──

    def evaluate(self, rule: dict, facts: dict, inferences: dict, **kwargs: Any) -> dict | None:
        """完整规则评估: 前提匹配 → 模板化 → 结论"""
        if not self.match_premises(rule, facts, inferences):
            return None
        return self.to_conclusion(rule, **kwargs)

    def evaluate_all(self, facts: dict, inferences: dict, **kwargs: Any) -> list[dict]:
        """评估所有已加载规则, 返回匹配的结论列表"""
        results = []
        for rule in self.rules:
            try:
                c = self.evaluate(rule, facts, inferences, **kwargs)
                if c:
                    results.append(c)
            except Exception as e:
                import sys

                print(f"[RuleLoader] evaluate {rule.get('id', '?')} 失败: {e}", file=sys.stderr)
                continue
        return results

    @staticmethod
    def to_conclusion(rule: dict, **kwargs: Any) -> dict | None:
        """将规则模板化为结论, 缺kwargs时用规则名作为结论"""
        template = rule.get("conclusion_template", rule.get("name", ""))
        try:
            text = template.format(**kwargs)
        except (KeyError, ValueError):
            # 缺少实际数据 → 不产生结论
            return None
        return {
            "type": rule.get("type", "loaded_rule"),
            "conclusion": text,
            "confidence": rule.get("confidence", 0.70),
            "derived_from": kwargs.get("derives_from", []),
            "method": "rule_loader",
            "derivation_trail": f"{rule.get('id', 'Y?')}: {rule.get('name', '?')}",
        }
