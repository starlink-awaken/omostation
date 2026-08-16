// --- v0.29: Salience + Anomaly Detection ---
import type { Operation, OperationContext, ErrorCode } from "../operations-types";
import { OperationError } from "../operations-types";
import { sourceScopeOpts } from "../operations-types";
import { clampSearchLimit } from "../engine";
import type { BrainEngine } from "../engine";
import { hybridSearch, hybridSearchCached } from "../search/hybrid";
import { VERSION } from "../../version";
import {
  GET_RECENT_SALIENCE_DESCRIPTION,
  FIND_ANOMALIES_DESCRIPTION,
  FIND_EXPERTS_DESCRIPTION,
  GET_RECENT_TRANSCRIPTS_DESCRIPTION,
  FIND_CONTRADICTIONS_DESCRIPTION,
  FIND_TRAJECTORY_DESCRIPTION,
} from "../operations-descriptions";

export const get_recent_salience: Operation = {
  name: 'get_recent_salience',
  description: GET_RECENT_SALIENCE_DESCRIPTION,
  scope: 'read',
  params: {
    days: { type: 'number', description: 'Window in days. Default 14.' },
    limit: { type: 'number', description: 'Max results (default 20, capped at 100).' },
    slugPrefix: {
      type: 'string',
      description: "Optional slug-prefix filter, e.g. 'personal' or 'wiki/people'.",
    },
    recency_bias: {
      type: 'string',
      enum: ['flat', 'on'],
      description:
        "v0.29.1: how to weight recency in the salience score.\n" +
        "  'flat' (DEFAULT) — v0.29.0 behavior. Every page gets 1/(1+days_old).\n" +
        "                     Stable, predictable; what most callers want.\n" +
        "  'on'             — Per-prefix decay map. concepts/originals/writing/\n" +
        "                     become evergreen (recency component = 0); daily/,\n" +
        "                     media/x/, chat/ decay aggressively. Use when the\n" +
        "                     user explicitly biases for recency-aware salience\n" +
        "                     ('what's been salient lately' vs 'what matters\n" +
        "                     in this brain regardless of when').",
    },
  },
  handler: async (ctx, p) => {
    const recencyBias = p.recency_bias === 'on' ? 'on' : 'flat';
    return ctx.engine.getRecentSalience({
      days: typeof p.days === 'number' ? p.days : undefined,
      limit: typeof p.limit === 'number' ? p.limit : undefined,
      slugPrefix: typeof p.slugPrefix === 'string' ? p.slugPrefix : undefined,
      recency_bias: recencyBias,
    });
  },
  cliHints: { name: 'salience' },
};

export const find_anomalies: Operation = {
  name: 'find_anomalies',
  description: FIND_ANOMALIES_DESCRIPTION,
  scope: 'read',
  params: {
    since: {
      type: 'string',
      description: 'ISO date YYYY-MM-DD. Default = today (UTC).',
    },
    lookback_days: {
      type: 'number',
      description: 'Days of history for the baseline. Default 30.',
    },
    sigma: {
      type: 'number',
      description: 'Sigma threshold. Default 3.0.',
    },
  },
  handler: async (ctx, p) => {
    return ctx.engine.findAnomalies({
      since: typeof p.since === 'string' ? p.since : undefined,
      lookback_days: typeof p.lookback_days === 'number' ? p.lookback_days : undefined,
      sigma: typeof p.sigma === 'number' ? p.sigma : undefined,
    });
  },
  cliHints: { name: 'anomalies' },
};

// v0.33: expertise + relationship-proximity routing. CLI: gbrain whoknows.
export const find_experts: Operation = {
  name: 'find_experts',
  description: FIND_EXPERTS_DESCRIPTION,
  scope: 'read',
  params: {
    topic: {
      type: 'string',
      description: 'The topic to route. Free-form natural language.',
    },
    limit: {
      type: 'number',
      description: 'Max results (default 5).',
    },
    explain: {
      type: 'boolean',
      description: 'Include factor breakdown per result (expertise, recency, salience).',
    },
  },
  handler: async (ctx, p) => {
    const { findExperts } = await import('../../commands/whoknows.ts');
    const topic = typeof p.topic === 'string' ? p.topic : '';
    if (!topic.trim()) {
      throw new OperationError('invalid_params', '`topic` is required and must be a non-empty string.');
    }
    // v0.34.1 (#861, D3 — 5th leak surface): find_experts (whoknows) was
    // authored against v0.33 after PR #861 was drafted, so the source-scope
    // thread was missing entirely. The op calls findExperts → hybridSearch
    // internally; without the thread an auth'd src-A whoknows query would
    // surface src-B people in the rankings.
    return findExperts(ctx.engine, {
      topic,
      limit: typeof p.limit === 'number' ? p.limit : undefined,
      explain: p.explain === true,
      ...sourceScopeOpts(ctx),
    });
  },
  cliHints: { name: 'whoknows', positional: ['topic'] },
};

// v0.32.6: contradiction probe MCP surface (M3)
export const find_contradictions: Operation = {
  name: 'find_contradictions',
  description: FIND_CONTRADICTIONS_DESCRIPTION,
  scope: 'read',
  // Reads eval_contradictions_runs.report_json for the latest run, then
  // filters in-memory by slug and severity. No new probe is triggered;
  // the agent surfaces what's already on disk.
  params: {
    slug: {
      type: 'string',
      description: 'Optional slug filter; matches either side of a pair (substring match on slug).',
    },
    severity: {
      type: 'string',
      enum: ['low', 'medium', 'high'],
      description: 'Optional severity filter.',
    },
    limit: {
      type: 'number',
      description: 'Max findings to return. Default 20.',
    },
  },
  handler: async (ctx, p) => {
    const limit = typeof p.limit === 'number' && p.limit > 0 ? Math.min(p.limit, 100) : 20;
    const slugFilter = typeof p.slug === 'string' ? p.slug.toLowerCase() : null;
    const sevFilter = (p.severity === 'low' || p.severity === 'medium' || p.severity === 'high')
      ? p.severity
      : null;
    const rows = await ctx.engine.loadContradictionsTrend(30);
    if (rows.length === 0) {
      return { contradictions: [], note: 'No probe runs in the last 30 days; run `gbrain eval suspected-contradictions` first.' };
    }
    const latest = rows[0];
    const report = latest.report_json as Record<string, unknown> | null;
    const perQuery = (report?.per_query as Array<{
      contradictions: Array<{
        kind: string;
        severity: 'low' | 'medium' | 'high';
        axis: string;
        confidence: number;
        a: { slug: string; chunk_id: number | null; take_id: number | null };
        b: { slug: string; chunk_id: number | null; take_id: number | null };
        resolution_kind: string;
        resolution_command: string;
      }>;
    }> | undefined) ?? [];
    const findings = perQuery.flatMap((q) => q.contradictions);
    const filtered = findings.filter((f) => {
      if (sevFilter && f.severity !== sevFilter) return false;
      if (slugFilter) {
        const sA = f.a.slug.toLowerCase();
        const sB = f.b.slug.toLowerCase();
        if (!sA.includes(slugFilter) && !sB.includes(slugFilter)) return false;
      }
      return true;
    });
    return {
      run_id: latest.run_id,
      ran_at: latest.ran_at,
      contradictions: filtered.slice(0, limit),
      total_in_run: findings.length,
    };
  },
  cliHints: { name: 'find-contradictions' },
};

export const find_trajectory: Operation = {
  name: 'find_trajectory',
  description: FIND_TRAJECTORY_DESCRIPTION,
  scope: 'read',
  // localOnly intentionally NOT set — federated OAuth clients should be
  // able to query trajectories for entities in their scope. Visibility
  // filtering (D-CDX-1) inside the engine restricts remote callers to
  // visibility='world' facts.
  params: {
    entity_slug: {
      type: 'string',
      description: 'Required. Entity slug to chart (e.g. "companies/acme-example", "people/alice-example").',
    },
    metric: {
      type: 'string',
      description: 'Optional. Filter to a single canonical metric (e.g. "mrr", "arr", "team_size"). When omitted, all metrics return.',
    },
    since: {
      type: 'string',
      description: 'Optional lower bound on valid_from (YYYY-MM-DD or ISO).',
    },
    until: {
      type: 'string',
      description: 'Optional upper bound on valid_from (YYYY-MM-DD or ISO).',
    },
    limit: {
      type: 'number',
      description: 'Max points returned. Default 100, max 500.',
    },
  },
  handler: async (ctx, p) => {
    if (typeof p.entity_slug !== 'string' || !p.entity_slug.trim()) {
      throw new Error('find_trajectory requires entity_slug (string)');
    }
    const metric = typeof p.metric === 'string' ? p.metric : undefined;
    const since  = typeof p.since  === 'string' ? p.since  : undefined;
    const until  = typeof p.until  === 'string' ? p.until  : undefined;
    const limit  = typeof p.limit  === 'number' ? p.limit  : undefined;
    const scope = sourceScopeOpts(ctx);

    // D-CDX-1: thread ctx.remote into the engine so visibility filtering
    // happens at SQL level. Mirrors recall's posture for untrusted callers.
    const points = await ctx.engine.findTrajectory({
      entitySlug: p.entity_slug,
      ...scope,
      remote: ctx.remote === true,
      metric,
      since,
      until,
      limit,
    });

    const { computeTrajectoryStats, TRAJECTORY_SCHEMA_VERSION } = await import('../trajectory.ts');
    const { regressions, drift_score } = computeTrajectoryStats(points);

    // Engine result includes raw embeddings (Float32Array); strip those
    // before sending over MCP — they're bulky binary noise that consumers
    // never need at this layer.
    const wirePoints = points.map(pt => ({
      fact_id: pt.fact_id,
      valid_from: pt.valid_from.toISOString().slice(0, 10),
      metric: pt.metric,
      value: pt.value,
      unit: pt.unit,
      period: pt.period,
      text: pt.text,
      source_session: pt.source_session,
      source_markdown_slug: pt.source_markdown_slug,
    }));

    return {
      points: wirePoints,
      regressions,
      drift_score,
      schema_version: TRAJECTORY_SCHEMA_VERSION,
    };
  },
  cliHints: { name: 'find-trajectory' },
};

export const get_recent_transcripts: Operation = {
  name: 'get_recent_transcripts',
  description: GET_RECENT_TRANSCRIPTS_DESCRIPTION,
  scope: 'read',
  // Local-only: rejects HTTP-borne MCP traffic at tool-list time
  // (serve-http.ts filters on `localOnly`) AND at runtime via the in-handler
  // ctx.remote check. Defense in depth: hidden + rejected.
  localOnly: true,
  params: {
    days: { type: 'number', description: 'Window in days. Default 7.' },
    summary: {
      type: 'boolean',
      description: 'When true (default), return first ~300 chars per transcript. When false, full content (capped at 100 KB per file).',
    },
    limit: { type: 'number', description: 'Max transcripts (default 50).' },
  },
  handler: async (ctx, p) => {
    // Trust gate (eng review D2 + codex C3): MCP / HTTP callers (`remote=true`)
    // are blocked. Local CLI callers (`remote=false`) and the trusted-workspace
    // dream cycle pass through. This op is intentionally NOT in the subagent
    // allow-list (subagents always run with remote=true; they would always be
    // rejected, which is a footgun if the op is visible).
    if (ctx.remote === true) {
      throw new OperationError(
        'permission_denied',
        'get_recent_transcripts is local-only — call via the gbrain CLI.',
      );
    }
    const { listRecentTranscripts } = await import('../transcripts.ts');
    return listRecentTranscripts(ctx.engine, {
      days: typeof p.days === 'number' ? p.days : undefined,
      summary: typeof p.summary === 'boolean' ? p.summary : undefined,
      limit: typeof p.limit === 'number' ? p.limit : undefined,
    });
  },
  cliHints: { name: 'transcripts', hidden: true },
};

