---
name: moltbook
description: Knowledge molting — brain page lifecycle.
triggers:
  - "moltbook"
  - "knowledge molt"
  - "molt my knowledge"
---

# Moltbook

## Contract
- On knowledge molt, identify pages whose content has been superseded or rewritten.
- Archive the old page, link it to the replacement, and update the brain index.
- Preserve provenance: record why the molt happened and when.
- Confirm the replacement page is discoverable before closing the molt.

## Anti-Patterns
- Do not delete superseded pages without archiving them first.
- Do not break inbound links; always leave a redirect or link to the replacement.
- Do not molt pages that are still actively referenced.

## Output Format
- A molt report: `molt | old_page -> new_page | reason | timestamp`.
- A discovery confirmation: the replacement page id and its linked inbound references.
