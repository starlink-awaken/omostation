#!/usr/bin/env python3
"""model_graph_query.py — 模型图查询（GraphRAG Wave 2）

依据 .omo/_knowledge/patterns/doc-l0-mof-mapping-governance.md Wave 2:
让 agent 通过 consumer_index 反向索引回答治理问题。

查询能力:
- query_constraint(constraint_id, index) — 约束被哪些族/规则引用
- query_family(family, index) — 某抽象族下有哪些约束
- query_rules(rule_prefix, index) — 某治理规则影响哪些约束

用法:
    python3 bin/ssot/model_graph_query.py --constraint X1-C04
    python3 bin/ssot/model_graph_query.py --family 安全
    python3 bin/ssot/model_graph_query.py --rules CR-SEC
"""

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONSUMER_INDEX = ROOT / "projects" / "ecos" / ".omo" / "_derived" / "consumer-index.yaml"


def load_index(path: Path = CONSUMER_INDEX) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def query_constraint(constraint_id: str, index: dict) -> dict:
    consumers = index.get(constraint_id, [])
    return {"constraint_id": constraint_id, "consumers": consumers}


def query_family(family: str, index: dict) -> dict:
    constraints = [cid for cid, c in index.items() if family in c]
    return {"family": family, "constraints": constraints}


def query_rules(rule_prefix: str, index: dict) -> dict:
    constraints = [cid for cid, c in index.items()
                   if any(r.lower().startswith(rule_prefix.lower()) for r in c)]
    return {"rule_prefix": rule_prefix, "constraints": constraints}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--constraint", help="查询约束 id 的消费者")
    ap.add_argument("--family", help="查询抽象族下约束")
    ap.add_argument("--rules", help="查询规则前缀影响的约束")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()
    if not any((args.constraint, args.family, args.rules)):
        print("usage: model_graph_query.py --constraint|--family|--rules", file=sys.stderr)
        return 2
    index = load_index()
    if not index:
        print("[WARN] consumer-index 未生成，先跑: python3 bin/ssot/consumer_index.py", file=sys.stderr)
        return 1
    if args.constraint:
        result = query_constraint(args.constraint, index)
    elif args.family:
        result = query_family(args.family, index)
    else:
        result = query_rules(args.rules, index)
    if args.json:
        import json

        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        for k, v in result.items():
            print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
