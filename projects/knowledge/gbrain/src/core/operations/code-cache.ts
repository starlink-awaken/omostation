// --- v0.34 W3b: code_traversal_cache admin op ---
import type { Operation, OperationContext, ErrorCode } from "../operations-types";
import { clampSearchLimit } from "../engine";
import type { BrainEngine } from "../engine";

export const code_traversal_cache_clear: Operation = {
  name: 'code_traversal_cache_clear',
  description: 'Clear cached code_blast / code_flow traversal results. Source-scoped by default; pass all_sources=true to wipe everything (D8 destructive-guard).',
  params: {
    source_id: { type: 'string', description: 'Source to clear. Required unless all_sources=true.' },
    all_sources: { type: 'boolean', description: 'Wipe cache across every source. Explicit opt-out of source-scoping.' },
  },
  mutating: true,
  scope: 'admin',
  localOnly: true,
  handler: async (ctx, p) => {
    const { clearTraversalCache } = await import('../code-intel/traversal-cache.ts');
    const sourceId = (p.source_id as string | undefined) ?? ctx.sourceId;
    const allSources = (p.all_sources as boolean) ?? false;
    if (ctx.dryRun) {
      return { dry_run: true, action: 'code_traversal_cache_clear', source_id: sourceId, all_sources: allSources };
    }
    const deleted = await clearTraversalCache(ctx.engine, {
      sourceId: allSources ? undefined : sourceId,
      allSources,
    });
    return { deleted, source_id: allSources ? null : sourceId, all_sources: allSources };
  },
  cliHints: { name: 'code_traversal_cache_clear', hidden: true },
};

