// --- v0.36 Phase 2: search_by_image (image-as-query) ---
import type { Operation, OperationContext, ErrorCode } from "../operations-types";
import { sourceScopeOpts } from "../operations-types";
import { clampSearchLimit } from "../engine";
import type { BrainEngine } from "../engine";

export const search_by_image: Operation = {
  name: 'search_by_image',
  description:
    'v0.36 cross-modal Phase 2: image-as-query retrieval. Accepts a local path (CLI), data: URI, or http(s):// URL ' +
    '(SSRF-defended). Returns visually-similar image chunks plus any OCR text they carry. Optional `query` text ' +
    'refinement merges via weighted RRF (D13 hybrid intersect). True image→full-text-knowledge requires Phase 3 ' +
    '(`gbrain reindex --multimodal` + `search.unified_multimodal: true`).',
  params: {
    image_path: { type: 'string', description: 'Absolute path to image (local CLI callers only — rejected for remote MCP per D18).' },
    image_url: { type: 'string', description: 'http(s):// URL to image. SSRF-defended; max 3 redirect hops; 10MB cap.' },
    image_data: { type: 'string', description: 'Base64-encoded image bytes (preferred for remote MCP callers). PNG/JPEG/WebP only.' },
    image_mime: { type: 'string', description: 'Optional MIME hint when ambiguous. Magic-byte sniff is authoritative.' },
    query: { type: 'string', description: 'Optional text refinement; runs hybrid intersect via D13 weighted RRF.' },
    limit: { type: 'number', description: 'Max results (default 20)' },
    offset: { type: 'number', description: 'Skip first N results (for pagination)' },
    source_id: { type: 'string', description: "Scope to a single source. Defaults to ctx.sourceId. '__all__' opts out." },
  },
  scope: 'read',
  // NOT localOnly: remote MCP callers can pass image_url or image_data
  // (subject to D18 image_path ban + D12 size cap + D23-#6 spend cap).
  handler: async (ctx, p) => {
    const imagePath = p.image_path as string | undefined;
    const imageUrl = p.image_url as string | undefined;
    const imageData = p.image_data as string | undefined;
    const imageMime = (p.image_mime as string) || undefined;
    const queryRefinement = p.query as string | undefined;
    const sourceIdParam = typeof p.source_id === 'string' ? p.source_id : undefined;

    // D18 P0 — remote callers cannot pass image_path. Rejecting at handler
    // entry, before any file I/O fires. validateParams catches it too at the
    // dispatch layer; this is defense-in-depth.
    if (ctx.remote === true && imagePath) {
      throw new Error(
        'permission_denied: image_path is not permitted for remote callers (D18). ' +
        'Use image_url or image_data instead.',
      );
    }

    if (!imagePath && !imageUrl && !imageData) {
      throw new Error('search_by_image requires one of: image_path, image_url, image_data');
    }
    if ([imagePath, imageUrl, imageData].filter(Boolean).length > 1) {
      throw new Error('search_by_image accepts only one of: image_path, image_url, image_data');
    }

    // D23-#6 — pre-flight daily-budget check for remote OAuth clients.
    // Local CLI callers (ctx.remote=false) bypass the cap (clientId="").
    const clientId = (ctx.remote === true ? (ctx.auth?.clientId ?? '') : '');
    if (clientId) {
      const budgetUsd = await getDailyImageBudgetUsd(ctx.engine);
      const { checkBudget } = await import('../spend-log.ts');
      await checkBudget(ctx.engine, clientId, Math.round(budgetUsd * 100));
    }

    // Resolve image bytes via the SSRF-defended loader. For remote callers,
    // tighter byte cap.
    const remoteCap = await getRemoteMaxBytes(ctx.engine);
    const localCap = await getLocalMaxBytes(ctx.engine);
    const cap = ctx.remote === true ? remoteCap : localCap;
    const { loadImageInput } = await import('../search/image-loader.ts');
    const loaded = await loadImageInput(
      (imagePath ?? imageUrl ?? `data:${imageMime ?? 'image/png'};base64,${imageData}`)!,
      { maxBytes: cap },
    );

    // Resolve source-scope (D5 canonical thread).
    const resolvedSourceId =
      sourceIdParam !== undefined
        ? sourceIdParam === '__all__'
          ? undefined
          : sourceIdParam
        : ctx.sourceId;

    const { searchByImage } = await import('../search/by-image.ts');
    const results = await searchByImage(
      ctx.engine,
      { base64: loaded.base64, mime: loaded.contentType },
      {
        limit: (p.limit as number) || 20,
        offset: (p.offset as number) || 0,
        query: queryRefinement,
        sourceId: resolvedSourceId,
        ...sourceScopeOpts(ctx),
      },
    );

    // D23-#6 — record successful Voyage call. Best-effort; failures don't
    // block the response.
    if (clientId) {
      const { recordSpend, VOYAGE_MULTIMODAL_3_PER_IMAGE_CENTS } = await import('../spend-log.ts');
      // Approximate: 1 image embed + (query ? 1 text embed : 0). Both are
      // billed at the same per-call rate by Voyage.
      const calls = 1 + (queryRefinement ? 1 : 0);
      void recordSpend(ctx.engine, {
        clientId,
        tokenName: ctx.auth?.clientName ?? null,
        operation: 'search_by_image',
        spendCents: VOYAGE_MULTIMODAL_3_PER_IMAGE_CENTS * calls,
        provider: 'voyage',
        model: 'voyage-multimodal-3',
      });
    }

    return results;
  },
  cliHints: { name: 'search-by-image' },
};

async function getDailyImageBudgetUsd(engine: BrainEngine): Promise<number> {
  try {
    const v = await engine.getConfig('search.image_query.daily_budget_usd_per_client');
    if (v == null) return 5; // default $5
    const n = parseFloat(v);
    return Number.isFinite(n) && n > 0 ? n : 5;
  } catch {
    return 5;
  }
}

async function getLocalMaxBytes(engine: BrainEngine): Promise<number> {
  try {
    const v = await engine.getConfig('search.image_query.max_bytes');
    if (v == null) return 10 * 1024 * 1024;
    const n = parseInt(v, 10);
    return Number.isFinite(n) && n > 0 ? n : 10 * 1024 * 1024;
  } catch {
    return 10 * 1024 * 1024;
  }
}

async function getRemoteMaxBytes(engine: BrainEngine): Promise<number> {
  try {
    const v = await engine.getConfig('search.image_query.remote_max_bytes');
    if (v == null) return 2 * 1024 * 1024;
    const n = parseInt(v, 10);
    return Number.isFinite(n) && n > 0 ? n : 2 * 1024 * 1024;
  } catch {
    return 2 * 1024 * 1024;
  }
}

