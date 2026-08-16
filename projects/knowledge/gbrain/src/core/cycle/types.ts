/**
 * cycle/types.ts — Cycle type definitions + util extracted from cycle.ts.
 *
 * Pure types + ALL_PHASES constant + NEEDS_LOCK_PHASES set +
 * makeErrorFromException. No lock primitives, no phase runners, no
 * filesystem/DB imports — safe dependency-free leaf module.
 *
 * Extracted 2026-07-04 (F7114ABA Wave 2 / P3) to bring cycle.ts under
 * the check-god-module 1500L SRP gate. cycle.ts re-exports everything
 * here (`export * from './cycle/types'`) so existing consumers keep
 * importing from './cycle.ts' unchanged.
 */

// ─── Phase enum ────────────────────────────────────────────────────

export type CyclePhase =
  | 'lint' | 'backlinks' | 'sync' | 'synthesize' | 'extract' | 'extract_facts'
  | 'resolve_symbol_edges'
  | 'patterns' | 'recompute_emotional_weight' | 'consolidate'
  // v0.36.1.0 Hindsight calibration wave:
  //  - propose_takes: LLM scans markdown prose, proposes gradeable claims
  //    to a review queue. User accepts/rejects via `gbrain takes propose`.
  //  - grade_takes: walks unresolved takes, retrieves evidence, asks a
  //    judge model to verdict them. Auto-resolve OFF by default (D17).
  //  - calibration_profile: aggregates the resolved subset into 2-4
  //    narrative pattern statements + active bias tags. Voice-gated.
  | 'propose_takes' | 'grade_takes' | 'calibration_profile'
  | 'embed' | 'orphans' | 'purge'
  // v0.39 T12: schema-suggest passive trigger (D3 + D4 plan-eng-review).
  // Wraps runSuggest() — same library the CLI verb + EIIRP call.
  | 'schema-suggest';

export const ALL_PHASES: CyclePhase[] = [
  'lint',
  'backlinks',
  'sync',
  'synthesize',
  'extract',
  // v0.32.2 — reconcile DB facts index from the `## Facts` fence on
  // every affected entity page. Runs AFTER extract (link/timeline
  // materialization) and BEFORE patterns (which reads graph state).
  // The empty-fence guard refuses to run if pre-v51 legacy facts are
  // pending the v0_32_2 backfill (Codex R2-#7).
  'extract_facts',
  // v0.33.3 W0c — within-file two-pass symbol resolution. Runs AFTER
  // extract + extract_facts so any code edges sync emitted (still bare-token)
  // get resolved into {resolved_chunk_id: N} / {ambiguous: true,
  // candidates: [...]} edge_metadata entries before downstream phases read
  // the graph. Quick-cycle compatible: each invocation walks at most
  // BATCH_SIZE*10 chunks where edges_backfilled_at IS NULL or stale.
  'resolve_symbol_edges',
  'patterns',
  // v0.29 — runs AFTER extract + synthesize so it sees the union of
  // sync-touched + synthesize-written pages with fresh tag + take state.
  'recompute_emotional_weight',
  // v0.31: cluster unconsolidated facts per (source_id, entity_slug);
  // Sonnet-synthesize one take per cluster; INSERT into takes(kind='fact');
  // mark facts consolidated_at + consolidated_into. Never DELETE — facts
  // stay as audit trail. Placed AFTER patterns (graph-fresh) and BEFORE
  // embed (so the new takes get embedded same-cycle).
  'consolidate',
  // v0.36.1.0 Hindsight calibration wave. Ordering rationale:
  //   - propose_takes AFTER consolidate so the proposal LLM sees the
  //     freshly-consolidated takes when deciding what's NOT yet captured
  //     (F2 fence-dedup).
  //   - grade_takes AFTER propose so newly-accepted proposals from the
  //     queue are eligible for grading on the next cycle (manual accept
  //     can land between cycle runs; auto-accept is intentionally NOT a
  //     thing — user always reviews).
  //   - calibration_profile AFTER grade so the profile reads fresh
  //     resolutions. Voice-gated narrative; cheap (Haiku judge).
  // Budget caps live in src/core/cycle/budget-meter.ts via BaseCyclePhase.
  'propose_takes',
  'grade_takes',
  'calibration_profile',
  'embed',
  'orphans',
  // v0.39 T12: passive schema-suggest. Runs LATE so post-sync brain state
  // is settled; thin wrapper around runSuggest() library. Cheap (heuristic
  // by default; LLM only when chat provider configured).
  'schema-suggest',
  // v0.26.5: hard-deletes soft-deleted pages and expired archived sources past
  // the 72h recovery window. Runs last so the rest of the cycle sees the
  // recoverable set; the purge then drops what's expired.
  'purge',
];

/**
 * Phases that mutate state (filesystem or DB) and therefore should
 * coordinate via the cycle lock. Only orphans is truly read-only
 * and skips the lock. patterns mutates DB (writes pattern pages) so
 * it acquires the lock; synthesize too. v0.26.5 adds purge (DELETE-cascade
 * across pages and sources). v0.31 adds consolidate (writes takes rows
 * + facts UPDATEs).
 */
export const NEEDS_LOCK_PHASES: ReadonlySet<CyclePhase> = new Set([
  'lint',
  'backlinks',
  'sync',
  'synthesize',
  'extract',
  // v0.32.2 — wipes + re-inserts facts per affected page.
  'extract_facts',
  // v0.33.3 W0c — writes code_edges_symbol.edge_metadata + content_chunks.edges_backfilled_at.
  'resolve_symbol_edges',
  'patterns',
  // v0.29 — writes pages.emotional_weight column.
  'recompute_emotional_weight',
  'consolidate',
  // v0.36.1.0 — propose_takes / grade_takes / calibration_profile all
  // mutate DB state (take_proposals, take_grade_cache, calibration_profiles)
  // so they coordinate via the cycle lock.
  'propose_takes',
  'grade_takes',
  'calibration_profile',
  'embed',
  'purge',
]);

// ─── Result / report shapes ────────────────────────────────────────

export type PhaseStatus = 'ok' | 'warn' | 'fail' | 'skipped';

export interface PhaseError {
  /** Error class for machine branching — e.g., 'DatabaseConnection', 'Timeout', 'LLMError', 'FilesystemError', 'InternalError'. */
  class: string;
  /** System error code or short identifier, e.g., 'ECONNREFUSED', 'ETIMEDOUT', 'UNKNOWN'. */
  code: string;
  /** Human-readable single-line message. */
  message: string;
  /** Optional suggestion of what to try next. */
  hint?: string;
  /** Optional link to a troubleshooting doc. */
  docs_url?: string;
}

export interface PhaseResult {
  phase: CyclePhase;
  status: PhaseStatus;
  duration_ms: number;
  summary: string;
  details: Record<string, unknown>;
  error?: PhaseError;
}

export type CycleStatus = 'ok' | 'clean' | 'partial' | 'skipped' | 'failed';

export interface CycleReport {
  /** Additive schema. Bumped on breaking changes. */
  schema_version: '1';
  timestamp: string;
  duration_ms: number;
  /**
   * Overall status derived from phase results:
   *   - 'clean'   : ran successfully, zero fixes/writes across every phase
   *   - 'ok'      : ran successfully, some work was done
   *   - 'partial' : at least one phase warned or failed, others ran
   *   - 'skipped' : cycle did not run (lock held by another holder)
   *   - 'failed'  : lock acquired but all attempted phases failed
   */
  status: CycleStatus;
  /** Present when status = 'skipped'. E.g., 'cycle_already_running' or 'no_database'. */
  reason?: string;
  brain_dir: string | null;
  phases: PhaseResult[];
  totals: {
    lint_fixes: number;
    backlinks_added: number;
    pages_synced: number;
    pages_extracted: number;
    pages_embedded: number;
    orphans_found: number;
    /** v0.23: number of transcripts the synthesize phase processed (judged + dispatched). */
    transcripts_processed: number;
    /** v0.23: number of new reflection/original/people pages written by synthesize. */
    synth_pages_written: number;
    /** v0.23: number of pattern pages written/updated by patterns phase. */
    patterns_written: number;
    /** v0.29: number of pages whose emotional_weight was (re)computed. */
    pages_emotional_weight_recomputed: number;
    /** v0.34: number of code edges resolved (1 candidate) by the resolve_symbol_edges phase. */
    edges_resolved: number;
    /** v0.34: number of code edges marked ambiguous (2+ candidates) by the resolve_symbol_edges phase. */
    edges_ambiguous: number;
    /** v0.26.5: number of source rows hard-deleted by the purge phase. */
    purged_sources_count: number;
    /** v0.26.5: number of page rows hard-deleted by the purge phase. */
    purged_pages_count: number;
    /** v0.31: number of facts promoted to takes by the consolidate phase. */
    facts_consolidated: number;
    /** v0.31: number of new takes created by the consolidate phase. */
    consolidate_takes_written: number;
    /**
     * v0.35.5: number of phantom unprefixed entity pages (e.g. `alice.md`)
     * redirected to their canonical prefixed slugs (`people/alice-example`)
     * by the phantom-redirect pre-pass inside `extract_facts`. Capped per
     * cycle by `GBRAIN_PHANTOM_REDIRECT_LIMIT` (default 50).
     */
    phantoms_redirected: number;
    /**
     * v0.35.5: number of phantom pages skipped because their canonical
     * resolved to multiple candidates. Operator must triage manually via
     * the `~/.gbrain/audit/phantoms-YYYY-Www.jsonl` audit log.
     */
    phantoms_ambiguous: number;
    /**
     * v0.35.5: number of phantom pages skipped because the disk fence and
     * DB body disagreed on the parsed fact row set, OR because the redirect
     * commit phase failed mid-way and surfaces as drift on retry. Audit log
     * records the specific reason.
     */
    phantoms_skipped_drift: number;
  };
}

export interface CycleOpts {
  /** If true, no writes to filesystem or DB. All phases honor this. */
  dryRun?: boolean;
  /** Defaults to ALL_PHASES. Pass a subset for --phase lint etc. */
  phases?: CyclePhase[];
  /** Brain directory (git repo). Required for filesystem phases. */
  brainDir: string;
  /** Whether sync should run `git pull`. Default false (cron-safe). */
  pull?: boolean;
  /**
   * Called between phases AND before runCycle returns. Awaited even
   * after phase failure. Hook exceptions are logged, never fatal.
   * Minions handlers pass a function that yields + renews the job lock
   * + refreshes the cycle-lock-table TTL.
   */
  yieldBetweenPhases?: () => Promise<void>;
  /**
   * Generic in-phase keepalive (v0.23). Long-running phases (synthesize
   * waiting on a fan-out aggregator, patterns rolling up reflections)
   * call this periodically while idle to renew the cycle-lock TTL and
   * the Minions worker job lock. Mirrors `yieldBetweenPhases` shape;
   * passing the same function for both is the common case.
   */
  yieldDuringPhase?: () => Promise<void>;
  /**
   * Synthesize phase scope overrides (v0.23). Forwarded to runPhaseSynthesize.
   * - `synthInputFile`: ad-hoc transcript path (`gbrain dream --input <file>`).
   * - `synthDate` / `synthFrom` / `synthTo`: date filters for corpus scan.
   * Mutually exclusive with each other in CLI parsing; runner trusts the
   * caller (CLI wrapper validates).
   */
  synthInputFile?: string;
  synthDate?: string;
  synthFrom?: string;
  synthTo?: string;
  /**
   * v0.23.2: explicit opt-in to disable the synthesize self-consumption guard.
   * Wired from `gbrain dream --unsafe-bypass-dream-guard`. Never auto-applied
   * for `--input` because that would let any caller silently re-trigger the
   * loop bug (codex finding #3).
   */
  synthBypassDreamGuard?: boolean;
  /**
   * AbortSignal from the Minions worker (v0.22.1, #403). When aborted
   * (timeout, cancel, lock-loss), runCycle bails between phases and
   * returns a 'failed' report instead of running the next phase. Without
   * this, a timed-out autopilot-cycle handler ignores the abort and runs
   * until the worker wedges (the 98-waiting-0-active incident on 2026-04-24).
   */
  signal?: AbortSignal;
}

// ─── Error mapping util ────────────────────────────────────────────

/**
 * Map an arbitrary thrown value to a structured PhaseError for the cycle
 * report. Keeps the 200-char message cap + node errno classification
 * (ECONNREFUSED → DatabaseConnection, ETIMEDOUT → Timeout, ENOENT/EACCES
 * → FilesystemError, OpenAI/embed in message → LLMError).
 */
export function makeErrorFromException(e: unknown, fallbackClass = 'InternalError'): PhaseError {
  const err = e instanceof Error ? e : new Error(String(e));
  // Node errors often have .code (e.g., 'ECONNREFUSED').
  const code = (err as NodeJS.ErrnoException).code || 'UNKNOWN';
  let className = fallbackClass;
  if (code === 'ECONNREFUSED' || code === 'ENOTFOUND') className = 'DatabaseConnection';
  if (code === 'ETIMEDOUT') className = 'Timeout';
  if (/OpenAI|embed/i.test(err.message)) className = 'LLMError';
  if (/ENOENT|EACCES|EISDIR|ENOTDIR/.test(code)) className = 'FilesystemError';
  return {
    class: className,
    code,
    message: err.message.slice(0, 200),
  };
}
