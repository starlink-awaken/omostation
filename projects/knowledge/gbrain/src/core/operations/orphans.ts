// --- Orphans ---
import type { Operation, OperationContext, ErrorCode } from "../operations-types";
import { clampSearchLimit } from "../engine";
import type { BrainEngine } from "../engine";

export const find_orphans: Operation = {
  name: 'find_orphans',
  description: 'Find pages with no inbound wikilinks. Essential for content enrichment cycles.',
  params: {
    include_pseudo: {
      type: 'boolean',
      description: 'Include auto-generated and pseudo pages (default: false)',
    },
  },
  scope: 'read',
  handler: async (ctx, p) => {
    const { findOrphans } = await import('../../commands/orphans.ts');
    return findOrphans(ctx.engine, { includePseudo: (p.include_pseudo as boolean) || false });
  },
  cliHints: { name: 'orphans', hidden: true },
};

