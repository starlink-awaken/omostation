#!/bin/bash
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH
AF=~/Workspace/projects/aetherforge
echo "=== 谁调用了 mesh 的调度(get_best_node / select) ==="
grep -rn "get_best_node\|select_node\|choose_node" $AF/src $AF/packages --include=*.py 2>/dev/null | grep -v test | head -10
echo
echo "=== run_generate 的实际路径(是否经 mesh) ==="
sed -n '39,60p' $AF/src/aetherforge/gateway/rpc.py 2>/dev/null
echo
echo "=== swarm 执行 LLM 步骤时走哪 ==="
grep -rn "llm_generate\|run_generate\|GenerateRequest" $AF/packages/swarm/src --include=*.py 2>/dev/null | grep -v test | head -6
echo
echo "=== ARCHITECTURE-SCHEDULING 摘要(设计意图) ==="
head -30 $AF/ARCHITECTURE-SCHEDULING.md 2>/dev/null | grep -v '^\s*$' | head -18
echo AF2DONE
