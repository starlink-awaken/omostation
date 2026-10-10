from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "bin/panorama/assets/host/template.html"


def test_republished_lease_does_not_make_old_dashboard_snapshot_look_live() -> None:
    script = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(process.argv[1], 'utf8');
const start = source.indexOf('function refreshHealth(){');
const end = source.indexOf('\nrefreshHealth();setInterval', start);
if (start < 0 || end < 0) throw new Error('refreshHealth function not found');
const refreshHealth = source.slice(start, end);
function render(snapshot, now) {
  const elements = {
    'refresh-health': { textContent: '' },
    'health-pulse-dot': { style: {} },
    'health-status-headline': { textContent: '' },
    'health-last-attempt-chip': { textContent: '' },
    'health-diagnostic-content': { innerHTML: '' },
  };
  const context = {
    D: snapshot,
    failures: [],
    Date: { now: () => now, parse: Date.parse },
    Number,
    Object,
    $: (id) => elements[id],
    dt: (value) => value || '未知',
    esc: (value) => String(value),
  };
  vm.runInNewContext(`${refreshHealth}\nrefreshHealth();`, context);
  return { headline: elements['health-status-headline'].textContent, dot: elements['health-pulse-dot'].style.background };
}
const now = Date.parse('2026-10-07T03:00:00Z');
const stale = render({ observed_at: '2026-10-06T18:13:06Z', generated_at: '2026-10-07T02:59:00Z' }, now);
if (!stale.headline.includes('数据快照已过期') || stale.dot !== '#f59e0b') {
  throw new Error(`old observation was not marked stale: ${JSON.stringify(stale)}`);
}
const fresh = render({ observed_at: '2026-10-07T02:59:00Z', generated_at: '2026-10-07T02:59:00Z' }, now);
if (!fresh.headline.includes('100% 实时对齐') || fresh.dot !== '#10b981') {
  throw new Error(`fresh observation lost healthy status: ${JSON.stringify(fresh)}`);
}
"""

    subprocess.run(["node", "-e", script, str(TEMPLATE)], cwd=ROOT, check=True)
