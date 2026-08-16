import type {
  Page, PageInput, PageFilters, GetPageOpts,
  Chunk, ChunkInput, StaleChunkRow,
  SearchResult, SearchOpts,
  Link, GraphNode, GraphPath,
  TimelineEntry, TimelineInput, TimelineOpts,
  RawData,
  PageVersion,
  BrainStats, BrainHealth,
  IngestLogEntry, IngestLogInput,
  EngineConfig,
  CodeEdgeInput, CodeEdgeResult,
  EvalCandidate, EvalCandidateInput,
  EvalCaptureFailure, EvalCaptureFailureReason,
  SalienceOpts, SalienceResult, AnomaliesOpts, AnomalyResult,
  EmotionalWeightInputRow, EmotionalWeightWriteRow,
  DomainBankSampleOpts, CorpusSampleOpts, DomainBankRow,
} from './types.ts';

/**
 * v0.27.1: file row for binary-asset metadata. Mirrors the `files` table
 * shape on both engines (Postgres has had it since v0.18; PGLite gets it
 * via migration v36).
 */
/**
 * Options for `traverseGraph`.
 *
 * `frontierCap`: when set, the BFS recursive term applies a parenthesized
 * `LIMIT N ORDER BY slug,id` so each iteration emits at most N rows. This
 * is the "approximately per-layer" cap discussed in the T8 plan — Postgres'
 * recursive CTE caps per ITERATION, not strictly per BFS LAYER (BFS layer
 * boundaries map to recursive iterations only when fan-out is bounded).
 * For hub-fanout graphs the cap fires early and bounds the work. Default:
 * unset = no cap (back-compat; existing callers see no change).
 *
 * NOTE: a truncation-detection signal (`onTruncation` callback) was
 * designed but the v1 algorithm had both false-positive (organic count ==
 * cap) and false-negative (LIMIT-before-DISTINCT in diamond graphs) cases
 * caught by adversarial review. The signal is deferred until a
 * dedupe-then-cap SQL rewrite + real Postgres parity coverage lands. See
 * (tracked TODO) → "T8 truncation signal" entry. Callers that need to detect
 * truncation can compare `result.length` against expected fanout bounds
 * as a coarse-but-honest signal in the interim.
 */
export interface TraverseGraphOpts {
  sourceId?: string;
  sourceIds?: string[];
  frontierCap?: number;
}

export interface FileRow {
  id: number;
  source_id: string;
  page_slug: string | null;
  page_id: number | null;
  filename: string;
  storage_path: string;
  mime_type: string | null;
  size_bytes: number | null;
  content_hash: string;
  metadata: Record<string, unknown>;
  created_at: Date;
}

/**
 * v0.27.1: spec for upsertFile. Identity is (source_id, storage_path).
 * Re-upserting the same identity with a different content_hash updates the
 * row in place (image was replaced); same content_hash is a no-op.
 */
export interface FileSpec {
  source_id?: string;
  page_slug?: string | null;
  page_id?: number | null;
  filename: string;
  storage_path: string;
  mime_type?: string | null;
  size_bytes?: number | null;
  content_hash: string;
  metadata?: Record<string, unknown>;
}

/** Input row for addLinksBatch. Optional fields default to '' (matches NOT NULL DDL). */
export interface LinkBatchInput {
  from_slug: string;
  to_slug: string;
  link_type?: string;
  context?: string;
  /**
   * Provenance (v0.13+). Pass 'frontmatter' for edges derived from YAML
   * frontmatter, 'markdown' for [Name](path) refs, 'manual' for user-created.
   * NULL means "legacy / unknown" and is only used by pre-v0.13 rows; new
   * writes should always set this. Missing on input defaults to 'markdown'.
   */
  link_source?: string;
  /** For link_source='frontmatter': slug of the page whose frontmatter created this edge. */
  origin_slug?: string;
  /** Frontmatter field name (e.g. 'key_people', 'investors'). */
  origin_field?: string;
  /**
   * v0.18.0: source id for each endpoint. When omitted, the engine JOINs
   * against `source_id='default'`. Pass explicit values when the edge
   * lives in a non-default source OR crosses sources.
   *
   * Without these fields, the batch JOIN `pages.slug = v.from_slug` fans
   * out across every source containing that slug, silently creating wrong
   * edges in a multi-source brain. The source_id filter eliminates the
   * fan-out. Origin pages (frontmatter provenance) get their own
   * source_id so reconciliation can't delete edges from another source's
   * frontmatter.
   */
  from_source_id?: string;
  to_source_id?: string;
  origin_source_id?: string;
}

/** Input row for addTimelineEntriesBatch. Optional fields default to '' (matches NOT NULL DDL). */
export interface TimelineBatchInput {
  slug: string;
  date: string;
  source?: string;
  summary: string;
  detail?: string;
  /**
   * v0.18.0: source id for the owning page. When omitted, the engine JOINs
   * against `source_id='default'`. Without this, two pages sharing the
   * same slug across sources would fan out timeline rows to both.
   */
  source_id?: string;
}

/**
 * A single dedicated database connection, isolated from the engine's pool.
 *
 * Used by migration paths that need session-level GUCs (e.g.
 * `SET statement_timeout = '600000'` before a `CREATE INDEX CONCURRENTLY`)
 * without leaking into the shared pool, and by write-quiesce designs
 * that need a session-lifetime Postgres advisory lock that survives
 * across transaction boundaries.
 *
 * On Postgres: backed by postgres-js `sql.reserve()`; the same backend
 * process serves every `executeRaw` call within the callback. Released
 * automatically when the callback returns or throws.
 *
 * On PGLite: a thin pass-through. PGLite has no pool, so every call is
 * already on the single backing connection. The interface is still
 * exposed so cross-engine callers don't need to branch.
 *
 * Not safe to call from inside `transaction()`. The transaction holds a
 * different backend; reserving a second one can deadlock on a row the
 * transaction itself is waiting to write.
 */
export interface ReservedConnection {
  executeRaw<T = Record<string, unknown>>(sql: string, params?: unknown[]): Promise<T[]>;
}

/**
 * v0.28: Takes — typed/weighted/attributed claims, indexed in Postgres.
 * Markdown is source of truth (fenced table on the page); this row is the
 * derived index. Page-scoped via page_id (NOT slug — slug is unique only
 * within a source). `(page_id, row_num)` is the natural unique key.
 */
// v0.38: TakeKind opens from closed 4-element union to string (T3/T10).
// Pre-v0.38, kinds {fact|take|bet|hunch} were enforced by DB CHECK
// (migrations v41/v48) AND by this TS closed union. Codex outside-voice
// review caught that dropping the CHECK without also widening the TS
// type "moves inconsistency around" — raw SQL and old clients could
// poison rows that runtime-validate cleanly. v0.38 migration v76 drops
// the CHECK; this widens the type. Runtime validation moves to the
// active schema pack's `takes_kinds:` declaration. The annotation
// primitive's seed list in gbrain-base reproduces {fact|take|bet|hunch}
// so existing behavior is unchanged; packs can extend to {finding|
// hypothesis|observation|...} per domain.
export interface TakeKindLiteral { kind: string }
export type TakeKind = string;

/** Input row for addTakesBatch. */
export interface TakeBatchInput {
  page_id: number;
  row_num: number;
  claim: string;
  kind: TakeKind;
  holder: string;
  weight?: number;          // 0..1, default 0.5; clamped server-side
  since_date?: string;      // ISO date 'YYYY-MM-DD'
  until_date?: string;
  source?: string;
  superseded_by?: number | null;
  active?: boolean;         // default true
}

/** Take row as returned by listTakes / searchTakes. */
export interface Take {
  id: number;
  page_id: number;
  page_slug: string;        // joined from pages
  row_num: number;
  claim: string;
  kind: TakeKind;
  holder: string;
  weight: number;
  since_date: string | null;
  until_date: string | null;
  source: string | null;
  superseded_by: number | null;
  active: boolean;
  resolved_at: string | null;
  resolved_outcome: boolean | null;
  /**
   * v0.30.0: 3-state outcome label. v0.36.1.1 added 'unresolvable' as a 4th
   * state for verdicts where evidence was insufficient to grade. Sits
   * alongside `resolved_outcome` for back-compat. New writes populate both;
   * legacy v0.28-resolved rows have `resolved_quality` backfilled by
   * migration v40 from the boolean. Null on unresolved rows. Schema CHECK
   * (widened in v74) enforces (quality, outcome) consistency:
   * `correct` ↔ `outcome=true`, `incorrect` ↔ `outcome=false`,
   * `partial` ↔ `outcome=NULL`, `unresolvable` ↔ `outcome=NULL`.
   */
  resolved_quality: 'correct' | 'incorrect' | 'partial' | 'unresolvable' | null;
  resolved_value: number | null;
  resolved_unit: string | null;
  resolved_source: string | null;
  resolved_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface TakesListOpts {
  page_id?: number;
  page_slug?: string;       // resolved via JOIN
  holder?: string;
  kind?: TakeKind;
  active?: boolean;         // default true (only active rows)
  resolved?: boolean;       // true = only resolved; false = only unresolved; undefined = both
  /** Per-token MCP allow-list. Server applies AND holder = ANY($takesHoldersAllowList) when set. */
  takesHoldersAllowList?: string[];
  sortBy?: 'weight' | 'since_date' | 'created_at';
  limit?: number;
  offset?: number;
}

/** Search result row from searchTakes / searchTakesVector. */
export interface TakeHit {
  take_id: number;
  page_id: number;
  page_slug: string;
  row_num: number;
  claim: string;
  kind: TakeKind;
  holder: string;
  weight: number;
  score: number;            // search rank score (ts_rank for keyword, 1-cos_dist for vector)
}

/** v0.28 stale-takes row (mirrors StaleChunkRow shape). Embedding column intentionally omitted. */
export interface StaleTakeRow {
  take_id: number;
  page_slug: string;
  row_num: number;
  claim: string;
}

/** Resolution metadata for resolveTake. */
export interface TakeResolution {
  /**
   * v0.30.0: primary 3-state input; v0.36.1.1 widened to 4-state with
   * 'unresolvable'. When set, takes precedence over `outcome` and the engine
   * writes both columns (quality directly; outcome derived:
   * `correct→true`, `incorrect→false`, `partial→null`, `unresolvable→null`).
   * `unresolvable` marks rows where the judge ran but evidence was
   * insufficient to grade; surfaces in `TakesScorecard.unresolvable_count`.
   */
  quality?: 'correct' | 'incorrect' | 'partial' | 'unresolvable';
  /**
   * v0.28 back-compat input. Keep submitting for v0.28 callers; the engine
   * derives quality (`true→correct`, `false→incorrect`). When `quality` is
   * also set, `quality` wins. When neither is set, the engine throws.
   * Mutually-exclusive with `quality === 'partial'` because partial isn't
   * binary.
   */
  outcome?: boolean;
  value?: number;
  unit?: string;       // 'usd' | 'pct' | 'count' | other
  source?: string;
  resolvedBy: string;  // slug or 'garry'
}

/** v0.30.0: scorecard aggregate. */
export interface TakesScorecard {
  total_bets: number;
  /**
   * Count of resolved rows where `resolved_quality IN
   * ('correct','incorrect','partial')`. v0.36.1.1 deliberately keeps this
   * 3-state semantic to preserve historical comparisons. Unresolvable rows
   * land in the sibling `unresolvable_count` field instead.
   */
  resolved: number;
  correct: number;
  incorrect: number;
  partial: number;
  /** Accuracy = correct / (correct + incorrect). NULL when n=0. */
  accuracy: number | null;
  /**
   * Brier score over rows where `resolved_quality IN ('correct','incorrect')`.
   * Maps `correct→1`, `incorrect→0`, computes `mean((weight − outcome)²)`.
   * Lower is better; 0 = perfect; 0.25 = always-50% baseline.
   * Excludes partial AND unresolvable — both hide signal; the dedicated
   * `partial_rate` and `unresolvable_rate` fields surface them separately.
   * NULL when no correct+incorrect rows.
   */
  brier: number | null;
  /** partial / resolved. NULL when n=0. */
  partial_rate: number | null;
  /**
   * v0.36.1.1: count of rows where `resolved_quality = 'unresolvable'`.
   * Sibling field to `resolved` so historical comparisons against pre-v80
   * scorecards stay valid; `resolved` retains its 3-state meaning, and
   * unresolvable rows count here separately. Optional for SDK back-compat —
   * downstream consumers constructing TakesScorecard fixtures shouldn't have
   * to update on a hotfix. `finalizeScorecard` always populates it.
   */
  unresolvable_count?: number;
  /**
   * v0.37.2.0: `unresolvable_count / (resolved + unresolvable_count)`. NULL
   * when both are 0. Surfaces the spec's headline calibration signal:
   * "what fraction of grade-attempted takes couldn't be graded?" — high
   * values signal weak evidence retrieval rather than wrong predictions.
   * Optional for SDK back-compat; see `unresolvable_count` note above.
   */
  unresolvable_rate?: number | null;
}

export interface TakesScorecardOpts {
  holder?: string;
  domainPrefix?: string; // e.g. 'companies/' to scope the scorecard
  since?: string;        // ISO date 'YYYY-MM-DD'
  until?: string;        // ISO date 'YYYY-MM-DD'
}

/** v0.30.0: calibration curve bucket. */
export interface CalibrationBucket {
  /** Lower bound of the weight bucket, inclusive. */
  bucket_lo: number;
  /** Upper bound, exclusive (except for the final bucket which is inclusive of 1.0). */
  bucket_hi: number;
  /** Count of resolved correct+incorrect bets falling in this weight range. */
  n: number;
  /** correct / n. NULL when n=0. */
  observed: number | null;
  /** mean(weight) within the bucket — what was predicted on average. NULL when n=0. */
  predicted: number | null;
}

export interface CalibrationCurveOpts {
  holder?: string;
  bucketSize?: number; // default 0.1
}

/** Synthesis evidence row input (provenance from think synthesis pages). */
export interface SynthesisEvidenceInput {
  synthesis_page_id: number;
  take_page_id: number;
  take_row_num: number;
  citation_index: number;
}

/** Dream-cycle Haiku verdict on whether a transcript is worth processing. */
export interface DreamVerdict {
  worth_processing: boolean;
  reasons: string[];
  judged_at: string;
}

/** Input shape for putDreamVerdict — judged_at defaults to now() server-side. */
export interface DreamVerdictInput {
  worth_processing: boolean;
  reasons: string[];
}

// ============================================================
// v0.31 Hot Memory: facts table + recall surface
// ============================================================

/** Allowed `facts.kind` values. Different decay halflives apply per kind. */
export type FactKind = 'event' | 'preference' | 'commitment' | 'belief' | 'fact';

export const ALL_FACT_KINDS: readonly FactKind[] = [
  'event', 'preference', 'commitment', 'belief', 'fact',
] as const;

/** Visibility tier on a fact row. Mirrors takes' world-default ACL contract (D21). */
export type FactVisibility = 'private' | 'world';

/** Status returned by insertFact. */
export type FactInsertStatus = 'inserted' | 'duplicate' | 'superseded';

/** A fact row read from the facts table. */
export interface FactRow {
  id: number;
  source_id: string;
  entity_slug: string | null;
  fact: string;
  kind: FactKind;
  visibility: FactVisibility;
  /**
   * v0.31.2: salience tier the LLM assigned at extraction time. Surfaces
   * to consumers (recall response, daily-page writer, admin dashboard,
   * agents reading via MCP `_meta.brain_hot_memory`). Pre-v45 brains had
   * no notability column; migration v46 backfills with default 'medium'.
   */
  notability: 'high' | 'medium' | 'low';
  context: string | null;
  valid_from: Date;
  valid_until: Date | null;
  expired_at: Date | null;
  superseded_by: number | null;
  consolidated_at: Date | null;
  consolidated_into: number | null;
  source: string;
  source_session: string | null;
  confidence: number;
  embedding: Float32Array | null;
  embedded_at: Date | null;
  created_at: Date;
}

/** Input for insertFact. source_id supplied via the ctx arg. */
export interface NewFact {
  fact: string;
  kind?: FactKind;                     // default 'fact'
  entity_slug?: string | null;
  visibility?: FactVisibility;          // default 'private'
  context?: string | null;
  valid_from?: Date;                   // default now()
  valid_until?: Date | null;
  source: string;                       // 'mcp:put_page' | 'mcp:extract_facts' | 'cli:think' | etc
  source_session?: string | null;
  confidence?: number;                  // [0,1], default 1.0
  notability?: 'high' | 'medium' | 'low'; // salience filter for extraction gate
  embedding?: Float32Array | null;     // pre-computed; if null, insertFact computes via gateway
  /**
   * v0.35.4 (D-CDX-5) — typed-claim fields. Optional. When populated,
   * `gbrain eval trajectory` + `find_trajectory` MCP op consume them for
   * chronological regression detection and drift_score. `claim_metric` is
   * normalized to lowercase snake_case by the extraction layer before
   * this method sees it; the engine stores verbatim.
   */
  claim_metric?: string | null;
  claim_value?: number | null;
  claim_unit?: string | null;
  claim_period?: string | null;
}

/** Options shared by list-facts methods. */
export interface FactListOpts {
  /** Hide expired_at IS NOT NULL rows. Default true. */
  activeOnly?: boolean;
  limit?: number;
  offset?: number;
  /** Restrict to specific kinds. Default: all kinds. */
  kinds?: FactKind[];
  /**
   * Visibility filter. When undefined, returns all. When set, only matches
   * are returned. Remote (untrusted) callers must supply ['world'].
   */
  visibility?: FactVisibility[];
}

/** Per-source operational health snapshot consumed by `gbrain doctor`. */
export interface FactsHealth {
  source_id: string;
  total_active: number;          // facts where expired_at IS NULL
  total_today: number;           // created in last 24h
  total_week: number;            // created in last 7d
  total_expired: number;         // expired_at IS NOT NULL
  total_consolidated: number;    // consolidated_at IS NOT NULL
  top_entities: Array<{ entity_slug: string; count: number }>;
  /** Optional counters fed by the queue / classifier — populated when those modules report. */
  drop_counter?: number;
  classifier_fail_counter?: number;
  p50_latency_ms?: number;
  p99_latency_ms?: number;
}

/**
 * v0.35.4 (D-CDX-6) — Options for `BrainEngine.findTrajectory`.
 *
 * `sourceId` (scalar fast path) and `sourceIds` (federated array) follow
 * the v0.34.1.0 search* pattern: when `sourceIds` is set the engine
 * applies `WHERE source_id = ANY($N::text[])`; otherwise scalar predicate
 * with `sourceId ?? 'default'`.
 *
 * `remote` (D-CDX-1) gates the visibility filter: when true the engine
 * adds `AND visibility = 'world'`, mirroring `recall`'s posture for
 * untrusted callers. Local CLI keeps `remote: false` and sees both
 * private + world facts.
 */
export interface TrajectoryOpts {
  entitySlug: string;
  /** Single-source scope; default 'default' when both this and sourceIds are unset. */
  sourceId?: string;
  /** Federated array scope (mutually exclusive with sourceId; the array wins when set). */
  sourceIds?: string[];
  /** When true, filters to visibility='world' only. Set by MCP layer from ctx.remote. */
  remote?: boolean;
  /** Metric filter. When set, only facts with this canonical metric label participate. */
  metric?: string;
  /** Lower bound on valid_from (inclusive). YYYY-MM-DD or full ISO. */
  since?: string | Date;
  /** Upper bound on valid_from (inclusive). YYYY-MM-DD or full ISO. */
  until?: string | Date;
  /** Cap on points returned. Default 100, max 500. */
  limit?: number;
}

/**
 * A single point in an entity's claim trajectory. Carries the typed-claim
 * fields when populated (drives regression detection), the underlying
 * fact text (for display), provenance (source_session, source_markdown_slug),
 * and the raw embedding so the caller can compute drift_score without a
 * second SQL round-trip.
 */
export interface TrajectoryPoint {
  fact_id: number;
  valid_from: Date;
  metric: string | null;
  value: number | null;
  unit: string | null;
  period: string | null;
  text: string;
  source_session: string | null;
  source_markdown_slug: string | null;
  /** Raw embedding for drift computation; null when the fact was inserted without one. */
  embedding: Float32Array | null;
}
