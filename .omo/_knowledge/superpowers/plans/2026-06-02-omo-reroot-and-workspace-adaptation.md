# OMO Reroot and Workspace Adaptation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the external OMO methodology canon from `~/Documents/学习进化/经验积累/OMO` to `~/Documents/学习进化/体系/OMO`, keep a minimal compatibility shell at the legacy path, and adapt Workspace `.omo` to bridge to the new canonical home.

**Architecture:** Use a soft reroot. The new `学习进化/体系/OMO` becomes the only canonical external methodology home; the old `经验积累/OMO` becomes a small redirect shell. Workspace `.omo` remains the live governance kernel and is upgraded only where it references or adopts the external OMO canon.

**Tech Stack:** Markdown, YAML, Python tests under `.omo/tests`, shell filesystem operations, ripgrep verification, git

---

## File map

### External OMO files and directories

- Move tree from: `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/`
- Create canonical home: `/Users/xiamingxing/Documents/学习进化/体系/OMO/`
- Recreate compatibility shell files at legacy path:
  - `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/README.md`
  - `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/INDEX.md`
  - `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/AGENT.md`
  - `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/CLAUDE.md`

### Workspace `.omo` files

- Create: `/Users/xiamingxing/Workspace/.omo/_knowledge/reference/OMO-METHODOLOGY-CANON.md`
- Modify: `/Users/xiamingxing/Workspace/.omo/INDEX.md`
- Modify: `/Users/xiamingxing/Workspace/.omo/_knowledge/reference/INDEX.md`
- Modify: `/Users/xiamingxing/Workspace/.omo/KNOWLEDGE_ARCH.md`
- Modify: `/Users/xiamingxing/Workspace/.omo/tests/test_phase16_execution.py`
- Modify: `/Users/xiamingxing/Workspace/.omo/tasks/done/P16-W1-JOURNEY-BASELINE.yaml`
- Create: `/Users/xiamingxing/Workspace/.omo/tests/test_external_omo_reroot.py`

### Planning / continuity files

- Modify: `/Users/xiamingxing/.copilot/session-state/a0b6fab5-a362-4eb9-90f8-f2e4e85653bc/plan.md`

---

### Task 1: Add failing Workspace reroot coverage

**Files:**
- Create: `/Users/xiamingxing/Workspace/.omo/tests/test_external_omo_reroot.py`
- Modify: `/Users/xiamingxing/Workspace/.omo/tests/test_phase16_execution.py`

- [ ] **Step 1: Write the failing test**

Add `/Users/xiamingxing/Workspace/.omo/tests/test_external_omo_reroot.py` with this content:

```python
from __future__ import annotations

from pathlib import Path


NEW_EXTERNAL_OMO_ROOT = Path("/Users/xiamingxing/Documents/学习进化/体系/OMO")
LEGACY_EXTERNAL_OMO_ROOT = Path("/Users/xiamingxing/Documents/学习进化/经验积累/OMO")


def test_new_external_omo_root_exists_with_core_surfaces() -> None:
    for rel_path in [
        "README.md",
        "INDEX.md",
        "_control/STATE.md",
        "_knowledge/02-OMO增长路线图.md",
        "_delivery/INDEX.md",
    ]:
        assert (NEW_EXTERNAL_OMO_ROOT / rel_path).exists(), rel_path


def test_legacy_external_omo_root_is_redirect_shell() -> None:
    for rel_path in ["README.md", "INDEX.md", "AGENT.md", "CLAUDE.md"]:
        path = LEGACY_EXTERNAL_OMO_ROOT / rel_path
        assert path.exists(), rel_path
        text = path.read_text(encoding="utf-8")
        assert "学习进化/体系/OMO" in text
        assert "canonical" in text or "新 canonical 位置" in text
```

In `/Users/xiamingxing/Workspace/.omo/tests/test_phase16_execution.py`, change:

```python
EXTERNAL_OMO_ROOT = Path("/Users/xiamingxing/Documents/学习进化/经验积累/OMO")
```

to:

```python
EXTERNAL_OMO_ROOT = Path("/Users/xiamingxing/Documents/学习进化/体系/OMO")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_external_omo_reroot.py .omo/tests/test_phase16_execution.py -q
```

Expected: FAIL because the new canonical external OMO root and redirect shell do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Do not patch more repo files yet. Only keep the new test file and the updated test root constant in place so the failing state proves the migration is required.

- [ ] **Step 4: Run test to verify it still fails for the right reason**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_external_omo_reroot.py .omo/tests/test_phase16_execution.py -q
```

Expected: FAIL with missing-path assertions under `学习进化/体系/OMO`.

- [ ] **Step 5: Commit**

```bash
cd /Users/xiamingxing/Workspace && git add .omo/tests/test_external_omo_reroot.py .omo/tests/test_phase16_execution.py && git -c core.hooksPath=/dev/null commit -m $'test(omo): add external reroot coverage\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

### Task 2: Reroot the external OMO canon and recreate the legacy shell

**Files:**
- Move: `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/**`
- Create: `/Users/xiamingxing/Documents/学习进化/体系/OMO/**`
- Create: `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/README.md`
- Create: `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/INDEX.md`
- Create: `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/AGENT.md`
- Create: `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/CLAUDE.md`

- [ ] **Step 1: Move the canonical tree**

Run:

```bash
mkdir -p '/Users/xiamingxing/Documents/学习进化/体系' && \
mv '/Users/xiamingxing/Documents/学习进化/经验积累/OMO' '/Users/xiamingxing/Documents/学习进化/体系/OMO'
```

Expected: the full external OMO tree now lives at `/Users/xiamingxing/Documents/学习进化/体系/OMO`.

- [ ] **Step 2: Recreate the legacy shell directory**

Run:

```bash
mkdir -p '/Users/xiamingxing/Documents/学习进化/经验积累/OMO'
```

Expected: the old path exists again, but is empty and ready for redirect entry files.

- [ ] **Step 3: Write the legacy redirect shell**

Create these four files with equivalent concise redirect wording.

`/Users/xiamingxing/Documents/学习进化/经验积累/OMO/README.md`

```markdown
# OMO（旧路径兼容壳）

> 此处不再是 OMO 的 canonical home。
>
> 新 canonical 位置：`/Users/xiamingxing/Documents/学习进化/体系/OMO`

请从新位置继续阅读与维护。旧路径仅保留最小兼容入口，避免旧引用和书签立即失效。
```

`/Users/xiamingxing/Documents/学习进化/经验积累/OMO/INDEX.md`

```markdown
# OMO（旧路径索引兼容页）

当前 OMO 方法系统已迁移到：

- `/Users/xiamingxing/Documents/学习进化/体系/OMO`

此页仅作为旧路径兼容索引，不再承载完整方法系统正文。
```

`/Users/xiamingxing/Documents/学习进化/经验积累/OMO/AGENT.md`

```markdown
# OMO Agent note（旧路径兼容壳）

如果从旧路径进入，请切换到新 canonical 位置：

- `/Users/xiamingxing/Documents/学习进化/体系/OMO`

旧路径不再作为主要维护面。
```

`/Users/xiamingxing/Documents/学习进化/经验积累/OMO/CLAUDE.md`

```markdown
# OMO CLAUDE note（旧路径兼容壳）

OMO 方法系统正文已经迁移到新 canonical 位置：

- `/Users/xiamingxing/Documents/学习进化/体系/OMO`

旧路径只保留兼容入口。
```

- [ ] **Step 4: Verify the reroot**

Run:

```bash
test -f '/Users/xiamingxing/Documents/学习进化/体系/OMO/README.md' && \
test -f '/Users/xiamingxing/Documents/学习进化/体系/OMO/INDEX.md' && \
test -f '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/README.md' && \
test -f '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/INDEX.md'
```

Expected: PASS with exit code 0.

- [ ] **Step 5: Commit**

No git commit is required for files outside `/Users/xiamingxing/Workspace`, but capture the reroot in the later Workspace doc/test commit.

### Task 3: Upgrade Workspace `.omo` to bridge to the rerooted canon

**Files:**
- Create: `/Users/xiamingxing/Workspace/.omo/_knowledge/reference/OMO-METHODOLOGY-CANON.md`
- Modify: `/Users/xiamingxing/Workspace/.omo/INDEX.md`
- Modify: `/Users/xiamingxing/Workspace/.omo/_knowledge/reference/INDEX.md`
- Modify: `/Users/xiamingxing/Workspace/.omo/KNOWLEDGE_ARCH.md`
- Modify: `/Users/xiamingxing/Workspace/.omo/tasks/done/P16-W1-JOURNEY-BASELINE.yaml`

- [ ] **Step 1: Add the bridge document**

Create `/Users/xiamingxing/Workspace/.omo/_knowledge/reference/OMO-METHODOLOGY-CANON.md` with this content:

```markdown
# External OMO methodology canon

> Freshness: 2026-06-02

## Purpose

This document fixes the relationship between the external OMO methodology system and the Workspace `.omo` governance kernel.

## Canonical split

1. External OMO canon lives at `/Users/xiamingxing/Documents/学习进化/体系/OMO`
2. Workspace `.omo` lives at `/Users/xiamingxing/Workspace/.omo`
3. External OMO stores method, case, pattern, and playbook
4. Workspace `.omo` stores live governance state, tasks, standards, evidence, and delivery truth

## Rules

1. `.omo` may reference external OMO as methodology canon
2. `.omo` must not shadow-copy external OMO as a second canon
3. External OMO must not replace `.omo` as live SSOT
4. Legacy external path `/Users/xiamingxing/Documents/学习进化/经验积累/OMO` is compatibility-only
```

- [ ] **Step 2: Add the new bridge to `.omo` navigation**

Append one row under “本体论与方法论” in `/Users/xiamingxing/Workspace/.omo/_knowledge/reference/INDEX.md`:

```markdown
| [OMO-METHODOLOGY-CANON.md](../../_knowledge/reference/OMO-METHODOLOGY-CANON.md) | 外部 OMO 方法系统 canonical home 与 Workspace `.omo` 的边界说明 |
```

Add one line to `/Users/xiamingxing/Workspace/.omo/INDEX.md` under “当前状态快照” or “阅读路径”:

```markdown
- **外部 OMO 方法系统 canonical home**: [_knowledge/reference/OMO-METHODOLOGY-CANON.md](_knowledge/reference/OMO-METHODOLOGY-CANON.md)
```

Add one short paragraph to `/Users/xiamingxing/Workspace/.omo/KNOWLEDGE_ARCH.md` stating that the external OMO methodology canon now lives under `学习进化/体系/OMO`, while `.omo` remains the live governance kernel.

- [ ] **Step 3: Update live `.omo` references**

In `/Users/xiamingxing/Workspace/.omo/tasks/done/P16-W1-JOURNEY-BASELINE.yaml`, change:

```yaml
- /Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/cases/2026-06-01-phase16-knowledge-capture-search-retrospective.md
```

to:

```yaml
- /Users/xiamingxing/Documents/学习进化/体系/OMO/_delivery/cases/2026-06-01-phase16-knowledge-capture-search-retrospective.md
```

- [ ] **Step 4: Run targeted grep verification**

Run:

```bash
cd /Users/xiamingxing/Workspace && \
rg -n '学习进化/经验积累/OMO' .omo/INDEX.md .omo/KNOWLEDGE_ARCH.md .omo/_knowledge/reference/INDEX.md .omo/_knowledge/reference/OMO-METHODOLOGY-CANON.md .omo/tasks/done/P16-W1-JOURNEY-BASELINE.yaml .omo/tests/test_phase16_execution.py .omo/tests/test_external_omo_reroot.py
```

Expected: only the legacy-path wording inside the bridge doc or redirect-oriented assertions should remain; live canonical references should now use `学习进化/体系/OMO`.

- [ ] **Step 5: Commit**

```bash
cd /Users/xiamingxing/Workspace && git add .omo/INDEX.md .omo/KNOWLEDGE_ARCH.md .omo/_knowledge/reference/INDEX.md .omo/_knowledge/reference/OMO-METHODOLOGY-CANON.md .omo/tasks/done/P16-W1-JOURNEY-BASELINE.yaml .omo/tests/test_phase16_execution.py .omo/tests/test_external_omo_reroot.py && git -c core.hooksPath=/dev/null commit -m $'docs(omo): reroot external canon and bridge workspace\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```

### Task 4: Verify the migration and update continuity

**Files:**
- Modify: `/Users/xiamingxing/.copilot/session-state/a0b6fab5-a362-4eb9-90f8-f2e4e85653bc/plan.md`
- Test: `/Users/xiamingxing/Workspace/.omo/tests/test_external_omo_reroot.py`
- Test: `/Users/xiamingxing/Workspace/.omo/tests/test_phase16_execution.py`

- [ ] **Step 1: Run the focused regression**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests/test_external_omo_reroot.py .omo/tests/test_phase16_execution.py -q
```

Expected: PASS.

- [ ] **Step 2: Run the standard `.omo` regression**

Run:

```bash
cd /Users/xiamingxing/Workspace && python3 -m pytest .omo/tests -q
```

Expected: PASS with no migration-related regressions.

- [ ] **Step 3: Update the session continuity note**

Append a short section to `/Users/xiamingxing/.copilot/session-state/a0b6fab5-a362-4eb9-90f8-f2e4e85653bc/plan.md` stating:

```markdown
## 2026-06-02 OMO reroot and Workspace adaptation

- External OMO canonical home moved from `学习进化/经验积累/OMO` to `学习进化/体系/OMO`
- Legacy path is now a compatibility shell only
- Workspace `.omo` now treats the rerooted external OMO as methodology canon and retains `.omo` as live governance kernel
```

- [ ] **Step 4: Run final filesystem and grep checks**

Run:

```bash
test -f '/Users/xiamingxing/Documents/学习进化/体系/OMO/README.md' && \
test -f '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/README.md' && \
cd /Users/xiamingxing/Workspace && \
rg -n '学习进化/体系/OMO' .omo/tests/test_phase16_execution.py .omo/tests/test_external_omo_reroot.py .omo/tasks/done/P16-W1-JOURNEY-BASELINE.yaml .omo/_knowledge/reference/OMO-METHODOLOGY-CANON.md
```

Expected: PASS; all live bridge files point to the new canonical home.

- [ ] **Step 5: Commit**

```bash
cd /Users/xiamingxing/Workspace && git add /Users/xiamingxing/.copilot/session-state/a0b6fab5-a362-4eb9-90f8-f2e4e85653bc/plan.md && git -c core.hooksPath=/dev/null commit -m $'docs(omo): record reroot continuity\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>'
```
