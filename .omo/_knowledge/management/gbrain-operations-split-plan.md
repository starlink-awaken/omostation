---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# gbrain operations.ts Split Plan

> Created: 2026-06-19 | Status: DEFERRED

## Current State

- 3841 LOC, 75 operations, 31 importers
- Single file exports `operations` array + `operationsByName` map

## Proposed Split

```
src/core/operations/
├── index.ts          # re-export operations array + operationsByName
├── pages.ts          # get_page, put_page, delete_page, restore_page, purge_deleted_pages, list_pages
├── search.ts         # search, query
├── takes.ts          # takes_*, think
├── tags.ts           # add_tag, remove_tag, get_tags
├── links.ts          # add_link, remove_link, get_links, get_backlinks, traverse_graph
├── timeline.ts       # add_timeline_entry, get_timeline
├── stats.ts          # get_stats, get_health, get_brain_identity, run_doctor
├── versions.ts       # get_versions, revert_version, sync_brain
├── raw-data.ts       # put_raw_data, get_raw_data, resolve_slugs, get_chunks
├── ingest.ts         # log_ingest, get_ingest_log
├── files.ts          # file_list, file_upload, file_url
├── jobs.ts           # submit_job, submit_agent, get_job, list_jobs, cancel_job, retry_job, get_job_progress, pause_job, resume_job, replay_job, send_job_message
├── analysis.ts       # find_orphans, get_calibration_profile, get_recent_salience, find_*
├── identity.ts       # whoami
├── sources.ts        # sources_*
├── memory.ts         # extract_facts, recall, forget_fact, memory_tree
├── code.ts           # code_*
└── image.ts          # search_by_image
```

## Migration Steps

1. Create operations/ directory
2. Move operations to domain files
3. Create index.ts re-export
4. Update 31 import sites
5. Run bun test
6. Delete old operations.ts

## Risk

- Medium: 31 import sites need updating
- Low: operations are self-contained (schema + handler)
