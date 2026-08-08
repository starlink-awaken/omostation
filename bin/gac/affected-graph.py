#!/usr/bin/env python3
"""bin/gac/affected-graph.py — Topological Affected Graph calculation.

Given a list of changed projects, calculate all downstream projects that depend on them
according to docs/layer-contract.yaml. This forms the basis of Cascading CI (Topological Defense).

Usage:
  python3 bin/gac/affected-graph.py --changed-projects ecos gbrain --json
"""
import argparse
import json
import yaml
from pathlib import Path

def load_yaml(path: Path):
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}

def get_project_layers(layer_contract):
    project_layer = {}
    for layer, info in layer_contract.get("layers", {}).items():
        for proj in info.get("projects", []):
            project_layer[proj] = layer
    return project_layer

def build_dependency_graph(layer_contract, project_layer):
    # returns upstream -> set(downstreams)
    graph = {}
    for proj in project_layer:
        graph[proj] = set()

    # directions: upstream <- downstream (who depends on whom)
    # layer-contract defines 'from' -> 'to' (downstream depends on upstream)
    # e.g., L3 depends on L2. L2 is upstream.
    # so upstream=L2, downstream=L3. If L2 changes, L3 is affected.

    rules = layer_contract.get("dependency_rules", {}).get("allowed_directions", [])
    
    # layer -> list of downstream layers
    layer_downstreams = {}
    for layer in layer_contract.get("layers", {}):
        layer_downstreams[layer] = set()
        
    for rule in rules:
        from_layers = rule.get("from", [])
        to_layers = rule.get("to", [])
        for f in from_layers:
            for t in to_layers:
                layer_downstreams[t].add(f)
                
    for upstream_proj, up_layer in project_layer.items():
        downstreams = layer_downstreams.get(up_layer, set())
        for downstream_layer in downstreams:
            for down_proj, d_layer in project_layer.items():
                if d_layer == downstream_layer:
                    graph[upstream_proj].add(down_proj)

    return graph

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--changed-projects", nargs="+", default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    layer_contract = load_yaml(Path("docs/layer-contract.yaml"))
    project_layer = get_project_layers(layer_contract)
    
    graph = build_dependency_graph(layer_contract, project_layer)
    
    affected = set()
    queue = []
    
    # only start from valid projects
    for cp in args.changed_projects:
        if cp in project_layer:
            affected.add(cp)
            queue.append(cp)
            
    while queue:
        curr = queue.pop(0)
        for down in graph.get(curr, []):
            if down not in affected:
                affected.add(down)
                queue.append(down)
                
    result = sorted(list(affected))
    
    if args.json:
        print(json.dumps(result))
    else:
        for p in result:
            print(p)

if __name__ == "__main__":
    main()
