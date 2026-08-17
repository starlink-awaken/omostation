/**
 * Sync helpers — extracted from commands/sync.ts (F7114ABA SRP wave 1).
 *
 * Pure-ish utility functions for the sync orchestration layer:
 *   - cost preview (estimateSyncAllCost, promptYesNo)
 *   - slug resolution for frontmatter-fallback pages (resolveSlugByPathOrSourcePath)
 *   - git CLI wrappers (buildGitInvocation, git, hasOriginRemote, isDetachedHead)
 *   - working-tree manifest builder (buildDetachedWorkingTreeManifest)
 *   - per-source anchor / chunker-version persistence (read/writeSyncAnchor,
 *     read/writeChunkerVersion)
 *
 * performSync / performSyncInner / performFullSync / runSync stay in sync.ts.
 * sync.ts re-exports the test-facing helpers via `export * from './sync-helpers.ts'`
 * so test/sync.test.ts and test/e2e/sync-cjk-git.test.ts keep importing from
 * commands/sync.ts unchanged.
 */

import { readFileSync, statSync } from 'fs';
import { execFileSync } from 'child_process';
import { createInterface } from 'readline';
import type { BrainEngine } from '../core/engine.ts';
import { buildSyncManifest, resolveSlugForPath } from '../core/sync.ts';
import type { SyncManifest } from '../core/sync.ts';
import { collectSyncableFiles } from './import.ts';
import { estimateTokens } from '../core/chunkers/code.ts';

/**
 * v0.20.0 Cathedral II Layer 8 (D1) — walk each source's working tree and
 * sum tokens for every syncable file. This is a conservative overestimate
 * (full file content, not just the incremental diff) because `sync --all`
 * on a source that hasn't been synced yet WILL embed every file in the
 * working tree. For already-synced sources with only incremental changes,
 * the overestimate is the ceiling, not the floor — users never get
 * surprised by MORE cost than the preview claims. The false-high bias is
 * intentional: a lower estimate that undersells the real bill would be
 * worse than one that oversells.
 */
function estimateSyncAllCost(sources: Array<{ local_path: string | null; config: Record<string, unknown> }>): {
  totalTokens: number;
  totalFiles: number;
  activeSources: number;
  perSource: Array<{ path: string; tokens: number; files: number }>;
} {
  let totalTokens = 0;
  let totalFiles = 0;
  let activeSources = 0;
  const perSource: Array<{ path: string; tokens: number; files: number }> = [];

  for (const src of sources) {
    if (!src.local_path) continue;
    const cfg = (src.config || {}) as { syncEnabled?: boolean; strategy?: 'markdown' | 'code' | 'auto' };
    if (cfg.syncEnabled === false) continue;
    activeSources++;
    let sourceTokens = 0;
    let sourceFiles = 0;
    try {
      // v0.31.2: cost preview routed through collectSyncableFiles
      // (single hardened walker; see import.ts). Previously
      // walkSyncableFiles used statSync (followed symlinks). New walker
      // uses lstat + inode-cycle + max-depth so the preview matches
      // what the real sync will actually walk.
      const files = collectSyncableFiles(src.local_path, { strategy: cfg.strategy ?? 'markdown' });
      for (const fullPath of files) {
        try {
          const stat = statSync(fullPath);
          if (stat.size > 5_000_000) continue; // skip large binaries
          const content = readFileSync(fullPath, 'utf-8');
          sourceTokens += estimateTokens(content);
          sourceFiles++;
        } catch {
          // Best-effort per file. Skip unreadable files silently;
          // sync itself tolerates the same.
        }
      }
    } catch {
      // Best-effort: a source whose local_path is gone or unreadable just
      // contributes 0. The sync itself would have failed anyway; no point
      // blocking the preview on a pre-existing fault.
    }
    totalTokens += sourceTokens;
    totalFiles += sourceFiles;
    perSource.push({ path: src.local_path, tokens: sourceTokens, files: sourceFiles });
  }

  return { totalTokens, totalFiles, activeSources, perSource };
}

/** Interactive [y/N] prompt. Resolves false on non-y answers or EOF. */
async function promptYesNo(question: string): Promise<boolean> {
  return new Promise((resolve) => {
    const rl = createInterface({ input: process.stdin, output: process.stdout });
    rl.question(question, (answer) => {
      rl.close();
      resolve(answer.trim().toLowerCase() === 'y' || answer.trim().toLowerCase() === 'yes');
    });
    rl.on('close', () => resolve(false));
  });
}

/**
 * v0.32.7 CJK wave (codex post-merge F4): resolve a slug by `pages.source_path`
 * first, falling back to `resolveSlugForPath(path)`.
 *
 * Frontmatter-fallback pages (emoji-only / Thai / Arabic / exotic-script
 * filenames where `slugifyPath` returns empty and the slug came from the
 * frontmatter) have a slug that ISN'T derivable from the path. Delete and
 * rename operations that only know the path would otherwise orphan these
 * pages by trying to delete the path-derived (wrong) slug.
 *
 * Returns the actual stored slug when source_path matches a row, or the
 * path-derived slug when there's no match (normal-case path-derived pages).
 */
export async function resolveSlugByPathOrSourcePath(
  engine: BrainEngine,
  path: string,
  sourceId?: string,
): Promise<string> {
  try {
    const rows = await engine.executeRaw<{ slug: string }>(
      sourceId
        ? `SELECT slug FROM pages WHERE source_path = $1 AND source_id = $2 LIMIT 1`
        : `SELECT slug FROM pages WHERE source_path = $1 LIMIT 1`,
      sourceId ? [path, sourceId] : [path],
    );
    if (rows.length > 0 && rows[0].slug) return rows[0].slug;
  } catch {
    // Fall through — best-effort. Pre-migration brains or query errors
    // shouldn't break delete/rename for path-derived pages.
  }
  return resolveSlugForPath(path);
}

/**
 * git CLI helper.
 *
 * `configs` flags are emitted as `-c key=val` pairs BEFORE `-C repoPath` and
 * BEFORE the subcommand. `core.quotepath=false` is always emitted first so CJK
 * (and other non-ASCII) paths arrive as UTF-8 in `diff --name-status` and
 * sibling commands. Callers that need additional git config should pass via
 * the `configs` parameter; never inline `-c` into `args`.
 *
 * Exported for `test/sync.test.ts` invariant assertion only.
 */
export function buildGitInvocation(repoPath: string, args: string[], configs: string[] = []): string[] {
  const cfg = ['core.quotepath=false', ...configs].flatMap(c => ['-c', c]);
  return [...cfg, '-C', repoPath, ...args];
}

export function buildAutoEmbedArgs(slugs: string[], sourceId?: string): string[] {
  return sourceId ? ['--source', sourceId, '--slugs', ...slugs] : ['--slugs', ...slugs];
}

/**
 * Shell out to git with a generous maxBuffer.
 *
 * Node's default maxBuffer is 1 MiB.  `git diff --name-status -M` on a
 * 60–100K file repo easily exceeds that, causing an ENOBUFS crash that
 * kills the sync process with no error message in the log.
 *
 * 100 MiB is generous but still bounded — a 100K-file diff with long
 * paths tops out around 10–20 MiB in practice.
 */
function git(repoPath: string, args: string[], configs: string[] = []): string {
  return execFileSync('git', buildGitInvocation(repoPath, args, configs), {
    encoding: 'utf-8',
    timeout: 30000,
    maxBuffer: 100 * 1024 * 1024,
  }).trim();
}

function hasOriginRemote(repoPath: string): boolean {
  try {
    execFileSync('git', buildGitInvocation(repoPath, ['remote', 'get-url', 'origin']), {
      encoding: 'utf-8',
      timeout: 30000,
      stdio: ['ignore', 'ignore', 'ignore'],
    });
    return true;
  } catch {
    return false;
  }
}

function isDetachedHead(repoPath: string): boolean {
  try {
    git(repoPath, ['symbolic-ref', '--quiet', 'HEAD']);
    return false;
  } catch {
    return true;
  }
}

function unique<T>(items: T[]): T[] {
  return [...new Set(items)];
}

function buildDetachedWorkingTreeManifest(repoPath: string): SyncManifest {
  const manifest = buildSyncManifest(git(repoPath, ['diff', '--name-status', '-M', 'HEAD']));
  const untracked = git(repoPath, ['ls-files', '--others', '--exclude-standard'])
    .split('\n')
    .filter(line => line.length > 0);

  return {
    added: unique([...manifest.added, ...untracked]),
    modified: unique(manifest.modified),
    deleted: unique(manifest.deleted),
    renamed: manifest.renamed,
  };
}

// v0.18.0 Step 5: source-scoped sync state helpers. When opts.sourceId
// is set, read/write the per-source row instead of the global config
// keys. These wrappers centralize the branch so every read/write site
// picks the right storage — future Step 5 work (failure-tracking per
// source) hooks here too.
async function readSyncAnchor(
  engine: BrainEngine,
  sourceId: string | undefined,
  which: 'repo_path' | 'last_commit',
): Promise<string | null> {
  if (sourceId) {
    const col = which === 'repo_path' ? 'local_path' : 'last_commit';
    const rows = await engine.executeRaw<Record<string, string | null>>(
      `SELECT ${col} AS value FROM sources WHERE id = $1`,
      [sourceId],
    );
    return rows[0]?.value ?? null;
  }
  return await engine.getConfig(`sync.${which}`);
}

async function writeSyncAnchor(
  engine: BrainEngine,
  sourceId: string | undefined,
  which: 'repo_path' | 'last_commit',
  value: string,
): Promise<void> {
  if (sourceId) {
    const col = which === 'repo_path' ? 'local_path' : 'last_commit';
    // last_sync_at bookmarked on every last_commit advance.
    if (which === 'last_commit') {
      await engine.executeRaw(
        `UPDATE sources SET last_commit = $1, last_sync_at = now() WHERE id = $2`,
        [value, sourceId],
      );
    } else {
      await engine.executeRaw(
        `UPDATE sources SET ${col} = $1 WHERE id = $2`,
        [value, sourceId],
      );
    }
    return;
  }
  await engine.setConfig(`sync.${which}`, value);
}

/**
 * v0.20.0 Cathedral II Layer 12 (SP-1 fix) — read/write the chunker version
 * last used to sync a given source. When it mismatches CURRENT_CHUNKER_VERSION,
 * `performSync` forces a full walk regardless of git HEAD equality. Without
 * this gate, bumping CHUNKER_VERSION does NOTHING on an unchanged repo
 * because sync short-circuits at `up_to_date` before reaching
 * `importCodeFile`'s content_hash check.
 *
 * Per-source storage matches writeSyncAnchor's shape — sources.chunker_version
 * TEXT column from the v27 migration. No global fallback: non-source syncs
 * (pre-v0.17 brains with no sources table) never had CHUNKER_VERSION
 * version-gating, so they keep the v0.19.0 behavior.
 */
async function readChunkerVersion(
  engine: BrainEngine,
  sourceId: string | undefined,
): Promise<string | null> {
  if (!sourceId) return null;
  const rows = await engine.executeRaw<{ chunker_version: string | null }>(
    `SELECT chunker_version FROM sources WHERE id = $1`,
    [sourceId],
  );
  return rows[0]?.chunker_version ?? null;
}

async function writeChunkerVersion(
  engine: BrainEngine,
  sourceId: string | undefined,
  version: string,
): Promise<void> {
  if (!sourceId) return;
  await engine.executeRaw(
    `UPDATE sources SET chunker_version = $1 WHERE id = $2`,
    [version, sourceId],
  );
}

// Internal re-export: sync.ts imports these to drive the orchestration layer.
// Kept as a single named bucket so the import site in sync.ts reads as one line.
export {
  git,
  unique,
  estimateSyncAllCost,
  promptYesNo,
  hasOriginRemote,
  isDetachedHead,
  buildDetachedWorkingTreeManifest,
  readSyncAnchor,
  writeSyncAnchor,
  readChunkerVersion,
  writeChunkerVersion,
};
