// --- Exports ---

import type { Operation } from "../operations-types";

import { get_page, put_page, delete_page, list_pages, restore_page, purge_deleted_pages } from "./pages.ts";
import { search, query } from "./search.ts";
import { search_by_image } from "./search-image.ts";
import { add_tag, remove_tag, get_tags } from "./tags.ts";
import { add_link, remove_link, get_links, get_backlinks, traverse_graph } from "./links.ts";
import { add_timeline_entry, get_timeline } from "./timeline.ts";
import { get_stats, get_health, run_doctor, get_versions, revert_version, get_brain_identity } from "./admin.ts";
import { sync_brain } from "./sync.ts";
import { put_raw_data, get_raw_data } from "./raw.ts";
import { resolve_slugs, get_chunks } from "./resolution.ts";
import { log_ingest, get_ingest_log } from "./ingest.ts";
import { file_list, file_upload, file_url } from "./files.ts";
import { submit_job, get_job, list_jobs, cancel_job, retry_job, get_job_progress, pause_job, resume_job, replay_job, send_job_message, submit_agent } from "./jobs.ts";
import { find_orphans } from "./orphans.ts";
import { get_calibration_profile } from "./calibration.ts";
import { takes_list, takes_search, think, takes_scorecard, takes_calibration } from "./takes.ts";
import { whoami, sources_add, sources_list, sources_remove, sources_status } from "./sources.ts";
import { get_recent_salience, find_anomalies, get_recent_transcripts } from "./salience.ts";
import { extract_facts, recall, forget_fact, memory_tree } from "./sources.ts";
import { find_contradictions, find_experts, find_trajectory } from "./salience.ts";
import { code_callers, code_callees, code_def, code_refs } from "./sources.ts";
import { code_blast, code_flow } from "./code-blast.ts";
import { code_traversal_cache_clear } from "./code-cache.ts";

export const operations: Operation[] = [
  // Page CRUD
  get_page, put_page, delete_page, list_pages,
  // v0.26.5 destructive-guard ops (page-level soft-delete + recovery + admin purge)
  restore_page, purge_deleted_pages,
  // Search
  search, query,
  // v0.36 Phase 2: image-as-query
  search_by_image,
  // Tags
  add_tag, remove_tag, get_tags,
  // Links
  add_link, remove_link, get_links, get_backlinks, traverse_graph,
  // Timeline
  add_timeline_entry, get_timeline,
  // Admin
  get_stats, get_health, run_doctor, get_versions, revert_version,
  // v0.31.1 (Issue #734): thin-client banner identity packet (read-scope, banner-only)
  get_brain_identity,
  // Sync
  sync_brain,
  // Raw data
  put_raw_data, get_raw_data,
  // Resolution & chunks
  resolve_slugs, get_chunks,
  // Ingest log
  log_ingest, get_ingest_log,
  // Files
  file_list, file_upload, file_url,
  // Jobs (Minions)
  submit_job, get_job, list_jobs, cancel_job, retry_job, get_job_progress,
  pause_job, resume_job, replay_job, send_job_message,
  // v0.38 Slice 3: remote-callable agent dispatch with OAuth-bound trust boundary
  submit_agent,
  // Orphans
  find_orphans,
  // v0.36.1.0 (T7) — Hindsight calibration wave: read profile via MCP
  get_calibration_profile,
  // v0.28: Takes + think
  takes_list, takes_search, think,
  // v0.30: calibration aggregates over takes
  takes_scorecard, takes_calibration,
  // v0.28: whoami + scoped sources management
  whoami, sources_add, sources_list, sources_remove, sources_status,
  // v0.29: Salience + anomalies + recent transcripts
  get_recent_salience, find_anomalies, get_recent_transcripts,
  // v0.31: hot memory (facts table)
  extract_facts, recall, forget_fact, memory_tree,
  // v0.32.6: contradiction probe MCP surface (M3)
  find_contradictions,
  // v0.33: expertise + relationship-proximity routing
  find_experts,
  // v0.35.4: temporal trajectory (typed claims over time + regression detection)
  find_trajectory,
  // v0.33.3: Cathedral III code-intelligence (MCP-exposed; were CLI_ONLY pre-v0.33.3)
  code_callers, code_callees, code_def, code_refs,
  // v0.34 W3: recursive code_blast + code_flow
  code_blast, code_flow,
  // v0.34 W3b: code_traversal_cache admin clear op
  code_traversal_cache_clear,
];

export const operationsByName = Object.fromEntries(
  operations.map(op => [op.name, op]),
) as Record<string, Operation>;
