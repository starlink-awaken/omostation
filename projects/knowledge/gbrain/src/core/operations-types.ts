/**
 * Contract-first operation definitions. Single source of truth for CLI, MCP, and tools-json.
 * Each operation defines its schema, handler, and optional CLI hints.
 */

import { lstatSync, realpathSync } from 'fs';
import { resolve, relative, sep } from 'path';
import type { BrainEngine } from './engine.ts';
import type { GBrainConfig } from './config.ts';
import { CJK_SLUG_CHARS } from './cjk.ts';

// --- Types ---

/**
 * v0.31 (eD6 / eE7): ErrorCode is now an OPEN union via the
 * `(string & {})` autocomplete-friendly hack. Downstream consumers (e.g.
 * gbrain-evals) get autocomplete on the named codes AND remain TS-forward-
 * compatible when gbrain adds new codes in future releases. This shape is
 * the standard Anthropic-API/OpenAI-API pattern.
 *
 * v0.31 added: 'rate_limited', 'extraction_failed', 'fact_not_found'.
 */
export type ErrorCode =
  | 'page_not_found'
  | 'invalid_params'
  | 'embedding_failed'
  | 'storage_error'
  | 'bucket_not_found'
  | 'database_error'
  | 'permission_denied'
  | 'unknown_transport' // v0.28.1: whoami fail-closed for ambiguous transport
  | 'rate_limited'      // v0.31: gateway rate-limit upstream
  | 'extraction_failed' // v0.31: facts extractor failed (refusal, parse, abort)
  | 'fact_not_found'    // v0.31: forget_fact / recall on unknown id
  // eslint-disable-next-line @typescript-eslint/ban-types
  | (string & {});      // OPEN union for forward-compat (eE7 / D13)

export class OperationError extends Error {
  constructor(
    public code: ErrorCode,
    message: string,
    public suggestion?: string,
    public docs?: string,
  ) {
    super(message);
    this.name = 'OperationError';
  }

  toJSON() {
    return {
      error: this.code,
      message: this.message,
      suggestion: this.suggestion,
      docs: this.docs,
    };
  }
}

// --- Upload validators (Fix 1 / B5 / H5 / M4) ---

/**
 * Validate an upload path. Two modes:
 *   - strict (remote=true): confines the resolved path to `root` and rejects symlinks.
 *     Used when the caller is untrusted (MCP over stdio/HTTP, agent-facing).
 *   - loose (remote=false): only verifies the file exists and is not a symlink whose
 *     target escapes the filesystem (no path traversal protection). Used for local CLI
 *     where the user owns the filesystem.
 *
 * Either way: symlinks in the final component are always rejected (prevents
 * transparent redirection to a different file than the user typed).
 *
 * @param filePath caller-supplied path
 * @param root confinement root (only used when strict=true)
 * @param strict true → enforce cwd confinement (B5 + H1). false → allow any accessible path.
 * @throws OperationError(invalid_params) on symlink escape, traversal, or missing file
 */
export function validateUploadPath(filePath: string, root: string, strict = true): string {
  let real: string;
  try {
    real = realpathSync(resolve(filePath));
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    if (msg.includes('ENOENT')) {
      throw new OperationError('invalid_params', `File not found: ${filePath}`);
    }
    throw new OperationError('invalid_params', `Cannot resolve path: ${filePath}`);
  }
  // Always reject final-component symlinks (basic safety for both modes).
  try {
    if (lstatSync(resolve(filePath)).isSymbolicLink()) {
      throw new OperationError('invalid_params', `Symlinks are not allowed for upload: ${filePath}`);
    }
  } catch (e) {
    if (e instanceof OperationError) throw e;
    // lstat race with unlink — pass if realpath already succeeded.
  }

  if (!strict) return real;

  // Strict mode: confine to root via realpath + path.relative (catches parent-dir symlinks per B5).
  let realRoot: string;
  try {
    realRoot = realpathSync(root);
  } catch {
    throw new OperationError('invalid_params', `Confinement root not accessible: ${root}`);
  }
  const rel = relative(realRoot, real);
  if (rel === '' || rel.startsWith('..') || rel.startsWith(`..${sep}`) || resolve(realRoot, rel) !== real) {
    throw new OperationError('invalid_params', `Upload path must be within the working directory: ${filePath}`);
  }
  return real;
}

/**
 * Allowlist validator for page slugs. Rejects URL-encoded traversal, backslashes,
 * control chars, RTL overrides, Unicode lookalikes — anything outside the allowlist.
 * Format: lowercase alphanumeric + hyphen segments separated by single forward slashes.
 */
export function validatePageSlug(slug: string): void {
  if (typeof slug !== 'string' || slug.length === 0) {
    throw new OperationError('invalid_params', 'page_slug must be a non-empty string');
  }
  if (slug.length > 255) {
    throw new OperationError('invalid_params', 'page_slug exceeds 255 characters');
  }
  // v0.32.7: CJK ranges (Han / Hiragana / Katakana / Hangul Syllables) allowed
  // in segments. ASCII shape rules (lead char, hyphen continuation) preserved.
  const PAGE_SLUG_SEG = `[a-z0-9${CJK_SLUG_CHARS}][a-z0-9${CJK_SLUG_CHARS}\\-]*`;
  if (!new RegExp(`^${PAGE_SLUG_SEG}(\\/${PAGE_SLUG_SEG})*$`, 'i').test(slug)) {
    throw new OperationError('invalid_params', `Invalid page_slug: ${slug} (allowed: alphanumeric, CJK, hyphens, forward-slash separated segments)`);
  }
}

/**
 * Match a slug against a list of allow-list prefix globs.
 *
 * Glob form: `<prefix>/*` matches any slug starting with `<prefix>/` and
 * having at least one more segment (single or multi). Bare `<prefix>` (no
 * trailing `/*`) matches that exact slug only. The `*` is intentionally
 * permissive — depth is unbounded, so `wiki/originals/*` matches both
 * `wiki/originals/idea-x` and `wiki/originals/ideas/2026-04-25-idea-y`.
 *
 * Used by the v0.23 dream-cycle trusted-workspace path. Order doesn't
 * matter; the first match wins (returns true on any match).
 */
export function matchesSlugAllowList(slug: string, prefixes: readonly string[]): boolean {
  for (const p of prefixes) {
    if (p.endsWith('/*')) {
      const base = p.slice(0, -2);
      if (slug === base) continue;
      if (slug.startsWith(base + '/')) return true;
    } else if (p === slug) {
      return true;
    }
  }
  return false;
}

/**
 * Allowlist validator for uploaded file basenames. Rejects control chars, backslashes,
 * RTL overrides (\u202E), leading dot (hidden files) and leading dash (CLI flag confusion).
 * Allows extension dots and underscores. Max 255 chars.
 */
export function validateFilename(name: string): void {
  if (typeof name !== 'string' || name.length === 0) {
    throw new OperationError('invalid_params', 'Filename must be a non-empty string');
  }
  if (name.length > 255) {
    throw new OperationError('invalid_params', 'Filename exceeds 255 characters');
  }
  // v0.32.7: CJK ranges (Han / Hiragana / Katakana / Hangul) allowed in filenames.
  // Leading-dot / leading-dash rejection preserved.
  const FILENAME_RE = new RegExp(`^[a-zA-Z0-9${CJK_SLUG_CHARS}][a-zA-Z0-9${CJK_SLUG_CHARS}._\\-]*$`);
  if (!FILENAME_RE.test(name)) {
    throw new OperationError('invalid_params', `Invalid filename: ${name} (allowed: alphanumeric, CJK, dot, underscore, hyphen — no leading dot/dash, no control chars or backslash)`);
  }
}

export interface ParamDef {
  type: 'string' | 'number' | 'boolean' | 'object' | 'array';
  required?: boolean;
  description?: string;
  default?: unknown;
  enum?: string[];
  items?: ParamDef;
}

export interface Logger {
  info(msg: string): void;
  warn(msg: string): void;
  error(msg: string): void;
}

export interface AuthInfo {
  token: string;
  clientId: string;
  /**
   * Human-readable agent name resolved at token-verification time.
   * For OAuth clients this is `oauth_clients.client_name`; for legacy
   * bearer tokens it is `access_tokens.name`. Threading this through
   * AuthInfo eliminates a per-request DB roundtrip in the /mcp handler
   * (was: SELECT client_name FROM oauth_clients WHERE client_id = ?
   * on every request — see PR #586 review note D14=B).
   */
  clientName?: string;
  scopes: string[];
  expiresAt?: number;
  /**
   * v0.34.1 (#861, D2): the source the calling OAuth client is scoped
   * to (write authority). Sourced from `oauth_clients.source_id` at
   * token-verification time. The HTTP transport ALSO threads this
   * value into `OperationContext.sourceId` at the same site so op
   * handlers can consume it via the canonical `ctx.sourceId` (D2
   * dual-write decision — identity surface symmetric with
   * `allowedSources` below).
   *
   * Undefined for legacy bearer tokens that predate v0.34.1 and for
   * clients that haven't been scoped yet. Migration v60 backfills
   * NULL → 'default' for pre-existing rows so this field is populated
   * on the upgrade path; brand-new public-client registrations may
   * still leave it null until an operator explicitly scopes via
   * `gbrain auth scope-client`.
   */
  sourceId?: string;
  /**
   * v0.34.1 (#876): array of source ids this OAuth client may READ
   * from (federation). Sourced from `oauth_clients.federated_read`.
   * Independent of `sourceId` (write authority): a "WeCare L3 dept"
   * client can write to `source_id='dept-x'` while reading the union
   * of `['dept-x', 'wecare-parent', 'shared']`.
   *
   * Empty array `[]` means "no federated reads beyond `sourceId`".
   * Undefined means "the post-v60 backfill hasn't populated this row
   * yet" — engines fall back to scalar `sourceId` filtering in that
   * case (back-compat).
   */
  allowedSources?: string[];
}

export interface OperationContext {
  engine: BrainEngine;
  config: GBrainConfig;
  logger: Logger;
  dryRun: boolean;
  /**
   * OAuth auth info (v0.8+). Present when the caller authenticated via OAuth 2.1
   * through `gbrain serve --http`. Contains clientId and granted scopes for
   * per-operation scope enforcement.
   */
  auth?: AuthInfo;
  /**
   * True when the caller is remote/untrusted (MCP over stdio/HTTP, or any agent-facing entry point).
   * False for local CLI invocations by the owner of the machine.
   *
   * Security-sensitive operations (e.g., file_upload) tighten their filesystem
   * confinement when remote=true and allow unrestricted local-filesystem access
   * when remote=false.
   *
   * REQUIRED as of the F7b hardening — the type system is the first line of defense.
   * Every transport (CLI / stdio MCP / HTTP MCP / subagent dispatcher) sets this
   * explicitly. Consumers still treat anything that isn't strictly `false` as
   * remote/untrusted (defense in depth in case the type is bypassed via cast).
   */
  remote: boolean;
  /**
   * Subagent runtime context (v0.16+). Set by the subagent tool dispatcher when
   * dispatching an op as a tool call from an LLM loop. Used to enforce per-op
   * agent policy (e.g. put_page namespace rule).
   *
   * `viaSubagent` is the FAIL-CLOSED flag: when true, agent-facing policy MUST
   * be enforced even if `subagentId` happens to be undefined (a bug in the
   * dispatcher must not bypass the guard). `subagentId` is the owning subagent
   * job id; `jobId` is the current Minion job id (aggregator or subagent).
   */
  jobId?: number;
  subagentId?: number;
  viaSubagent?: boolean;
  /**
   * Trusted-workspace allow-list (v0.23 dream cycle). When the cycle's
   * synthesize/patterns phases dispatch a subagent, they thread an
   * explicit list of slug-prefix globs (e.g. "wiki/personal/reflections/*")
   * through this field. put_page enforces it BEFORE the legacy
   * `wiki/agents/<id>/...` namespace check.
   *
   * Trust comes from the SUBMITTER (subagent jobs are gated by
   * PROTECTED_JOB_NAMES — MCP cannot submit them), not from `remote`.
   * Every subagent tool call has `remote=true` for auto-link safety,
   * so basing trust on `remote` is incoherent (would always reject).
   *
   * Empty / unset → fall back to the legacy namespace check (existing
   * v0.15 behavior; pure addition, no regression).
   */
  allowedSlugPrefixes?: string[];
  /**
   * Resolved global CLI options (--quiet / --progress-json / --progress-interval).
   * CLI callers populate this from `getCliOptions()`. MCP / library callers
   * may leave it undefined — consumers default to quiet/no-progress for
   * background work.
   */
  cliOpts?: { quiet: boolean; progressJson: boolean; progressInterval: number };
  /**
   * v0.28: per-token allow-list for the holder field on `takes`. Threaded
   * by the MCP HTTP/stdio dispatch layer from `access_tokens.permissions.takes_holders`.
   *
   * When set (i.e., this OperationContext came from an MCP-bound token),
   * `takes_list`, `takes_search`, `takes_scorecard`, `takes_calibration`,
   * and `query` (when it returns takes) MUST apply `WHERE holder = ANY($takesHoldersAllowList)`.
   * This is the server-side filter that backs the v0.28+ visibility model.
   *
   * v0.30.0: aggregate ops (`takes_scorecard`, `takes_calibration`) require
   * the allow-list as a TS-required engine method param (fail-closed by
   * compiler). Hidden-holder rows contribute zero to aggregates. The CLI
   * callers (local + trusted) leave it undefined.
   *
   * Default behavior when unset: local CLI callers see all holders. v0.28
   * MCP dispatch sets it to `['world']` for tokens with no permissions row
   * (default-deny on private hunches).
   */
  takesHoldersAllowList?: string[];
  /**
   * Connected-gbrains brain id (v0.19+ / v0.26 mounts). Identifies which brain
   * this op is targeting. 'host' for the default brain configured in
   * ~/.gbrain/config.json; otherwise a mount id registered in ~/.gbrain/mounts.json.
   *
   * `ctx.engine` is the resolved BrainEngine for this id (populated by
   * BrainRegistry at dispatch time). `brainId` exists alongside for:
   * - audit logging (mount-ops JSONL carries the id)
   * - subagent inheritance (child jobs receive the parent's brainId)
   * - cross-brain citation prefixes in agent output
   *
   * Orthogonal to v0.18.0's source_id, which scopes per-repo WITHIN a brain.
   * See docs/architecture/brains-and-sources.md for the mental model.
   *
   * Omitted = 'host' (pre-v0.19 callers + single-brain deployments keep
   * working without change).
   */
  brainId?: string;
  /**
   * v0.31 (eD4 / eE2): the in-DB tenancy axis for facts hot memory.
   * `sources.id` is TEXT (not INTEGER) — keep this as a string.
   *
   * Resolved once in the dispatcher from CLI flag (--source) / env
   * (GBRAIN_SOURCE) / `.gbrain-source` dotfile / per-token sources scope
   * (HTTP). Defaults to 'default' when nothing else applies.
   *
   * Every facts read/write filter starts with `WHERE source_id = $X`
   * so the trust boundary is part of the index path, not a callback.
   *
   * v0.34 D4 — REQUIRED at the TypeScript level. Mirrors v0.26.9 `remote`
   * REQUIRED pattern that closed the HTTP RCE class. Every transport
   * (CLI / stdio MCP / HTTP MCP / subagent dispatcher) MUST populate
   * this field; `buildOperationContext` auto-fills 'default' for callers
   * who don't pass an explicit sourceId, so the type contract is
   * satisfied even on single-source brains.
   */
  sourceId: string;
}

/**
 * v0.34.1 (#861, D9 — P0 leak seal): resolve the source-scope filter for a
 * read-side op handler. Returns an opts fragment ready to spread into the
 * engine call.
 *
 * Precedence:
 *  1. `ctx.auth?.allowedSources` (federated read, #876) → emits
 *     `{sourceIds: [...]}`. Federated semantics subsume the scalar case.
 *  2. `ctx.sourceId` (scalar) → emits `{sourceId: '...'}`.
 *  3. Neither set → emits `{}`. Local CLI callers (and tests that don't
 *     populate ctx) keep the pre-v0.34 unscoped behavior.
 *
 * Both fields default to the engine's "no filter" behavior individually,
 * so unset values are safe — the engine sees the same shape it did
 * pre-v0.34. The leak this guards against is an authenticated MCP client
 * whose ctx.sourceId IS set but whose engine call was constructed without
 * threading it (operations.ts:968/1076/1092/935/1469/1471/2241 pre-fix).
 *
 * Helper rather than inline so every read-side handler routes through the
 * same precedence ladder — drift between sites is the bug class.
 */
export function sourceScopeOpts(ctx: OperationContext): { sourceId?: string; sourceIds?: string[] } {
  const allowed = ctx.auth?.allowedSources;
  // Treat an empty `allowedSources: []` as "no federated read scope" — the
  // op-handler defers to scalar `ctx.sourceId` below. An attacker-controlled
  // value of `[]` MUST NOT widen scope to "all sources" by being interpreted
  // as "no filter."
  if (allowed && allowed.length > 0) return { sourceIds: allowed };
  if (ctx.sourceId) return { sourceId: ctx.sourceId };
  return {};
}

export interface Operation {
  name: string;
  description: string;
  params: Record<string, ParamDef>;
  handler: (ctx: OperationContext, params: Record<string, unknown>) => Promise<unknown>;
  mutating?: boolean;
  /**
   * Capability scope required to invoke this op over an authenticated
   * transport. v0.28 added `sources_admin` (manage federated sources) and
   * `users_admin` (reserved). The hierarchy lives in src/core/scope.ts —
   * `admin` implies all, `write` implies `read`, the two `*_admin` scopes
   * are siblings (different axes; neither implies the other).
   *
   * Local CLI callers (ctx.remote === false) bypass scope enforcement
   * because the trust boundary there is the OS, not OAuth scopes.
   */
  scope?: 'read' | 'write' | 'admin' | 'sources_admin' | 'users_admin';
  localOnly?: boolean;
  cliHints?: {
    name?: string;
    positional?: string[];
    stdin?: string;
    hidden?: boolean;
  };
}

