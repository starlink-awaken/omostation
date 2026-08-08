#!/bin/bash
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH
AF=~/Workspace/projects/aetherforge
echo "=== aetherforge 结构 ==="
ls $AF 2>/dev/null | head -12
echo "--- packages ---"; ls $AF/packages 2>/dev/null
echo
echo "=== 最近提交(看它在往哪走) ==="
git -C $AF log --oneline -8 2>/dev/null
echo
echo "=== SSOT: compute_engine 有哪些 ==="
ls ~/Workspace/projects/ecos/src/ecos/ssot/mof/m1/compute_engine/ 2>/dev/null
echo
echo "=== ENG-OMLX-LOCAL 现状 ==="
grep -E 'base_url|status|network_zone|description' ~/Workspace/projects/ecos/src/ecos/ssot/mof/m1/compute_engine/ENG-OMLX-LOCAL.yaml 2>/dev/null | head -5
echo
echo "=== mesh 实时看到的节点 ==="
cd $AF && uv run python -c "
from aetherforge.mesh.rpc import run_mesh_status
r=run_mesh_status()
print(' online', r.get('online'),'/',r.get('total'))
for n in (r.get('nodes') or []):
    print('   ', n.get('id'), 'ON' if n.get('online') else 'off')
" 2>&1 | grep -v 'Failed to publish' | head -20
echo AFDONE
