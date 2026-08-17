// F7114ABA wave 1: cli.ts help 提取 (printOpHelp + printHelp, SRP)
import type { Operation } from './operations.ts';
import { VERSION } from '../version.ts';

export function printOpHelp(op: Operation): void {
  const positional = (op.cliHints?.positional || []).map(p => `<${p}>`).join(' ');
  const name = op.cliHints?.name || op.name;
  console.log(`Usage: gbrain ${name} ${positional} [options]\n`);
  console.log(op.description + '\n');
  const entries = Object.entries(op.params);
  if (entries.length > 0) {
    console.log('Options:');
    for (const [key, def] of entries) {
      const isPos = op.cliHints?.positional?.includes(key);
      const req = def.required ? ' (required)' : '';
      const prefix = isPos ? `  <${key}>` : `  --${key.replace(/_/g, '-')}`;
      console.log(`${prefix.padEnd(28)} ${def.description || ''}${req}`);
    }
  }
}

export function printHelp(cliOps: Map<string, Operation>): void {
  // Gather shared operations grouped by category
  const cliNames = Array.from(cliOps.entries())
    .map(([name, op]) => ({ name, desc: op.description }));

  console.log(`gbrain ${VERSION} -- personal knowledge brain

USAGE
  gbrain <command> [options]

SETUP
  init [--pglite|--supabase|--url]   Create brain (PGLite default, no server)
  migrate --to <supabase|pglite>     Transfer brain between engines
  upgrade                            Self-update
  check-update [--json]              Check for new versions
  doctor [--json] [--fast]            Health check (resolver, skills, pgvector, RLS, embeddings)
  integrations [subcommand]          Manage integration recipes (senses + reflexes)

PAGES
  get <slug>                         Read a page
  put <slug> [< file.md]             Write/update a page
  delete <slug>                      Delete a page
  list [--type T] [--tag T] [-n N]   List pages

SEARCH
  search <query>                     Keyword search (tsvector)
  query <question> [--no-expand]     Hybrid search (RRF + expansion)
  ask <question> [--no-expand]       Alias for query

IMPORT/EXPORT
  import <dir> [--no-embed]          Import markdown directory
  sync [--repo <path>] [flags]       Git-to-brain incremental sync
  sync --watch [--interval N]        Continuous sync (loops until stopped)
  sync --install-cron                Install persistent sync daemon
  export [--dir ./out/]              Export to markdown
  export --restore-only [--repo <p>] Restore missing supabase-only files
        [--type T] [--slug-prefix S] With optional filters

FILES
  files list [slug]                  List stored files
  files upload <file> --page <slug>  Upload file to storage
  files upload-raw <file> --page <s> Smart upload (size routing + .redirect.yaml)
  files signed-url <path>            Generate signed URL (1-hour)
  files sync <dir>                   Bulk upload directory
  files verify                       Verify all uploads

EMBEDDINGS
  embed [<slug>|--all|--stale]       Generate/refresh embeddings

LINKS
  link <from> <to> [--type T]        Create typed link
  unlink <from> <to>                 Remove link
  backlinks <slug>                   Incoming links
  graph <slug> [--depth N]           Traverse link graph (returns nodes)
  graph-query <slug> [--type T]      Edge-based traversal with type/direction filters
        [--depth N] [--direction in|out|both]

TAGS
  tags <slug>                        List tags
  tag <slug> <tag>                   Add tag
  untag <slug> <tag>                 Remove tag

TIMELINE
  timeline [<slug>]                  View timeline
  timeline-add <slug> <date> <text>  Add timeline entry

TOOLS
  extract <links|timeline|all>       Extract links/timeline (idempotent)
        [--source fs|db]             fs (default) walks .md files; db iterates engine pages
        [--dir <brain>]              brain dir for fs source
        [--type T] [--since DATE]    filters (db source)
        [--dry-run] [--json]
  publish <page.md> [--password]     Shareable HTML (strips private data, optional AES-256)
  check-backlinks <check|fix> [dir]  Find/fix missing back-links across brain
  lint <dir|file> [--fix]            Catch LLM artifacts, placeholder dates, bad frontmatter
  orphans [--json] [--count]         Find pages with no inbound wikilinks
  salience [--days N] [--kind P]     v0.29: pages ranked by emotional + activity salience
  anomalies [--since D] [--sigma N]  v0.29: cohort-based statistical anomalies (tag, type)
  transcripts recent [--days N]      v0.29: recent raw .txt transcripts (local-only)
  dream [--dry-run] [--json]         Run the overnight maintenance cycle once (cron-friendly).
                                     See also: autopilot --install (continuous daemon).
  check-resolvable [--json] [--fix]  Validate skill tree (reachability/MECE/DRY)
  report --type <name> --content ... Save timestamped report to brain/reports/

SOURCES (multi-repo / multi-brain)
  sources list                       Show registered sources
  sources add <id> --path <p>        Register a source (id = short name, e.g. 'wiki')
  sources remove <id>                Remove a source + its pages
  sync --all                         Sync all sources with a local_path
  sync --source <id>                 Sync one specific source
  repos ...                          DEPRECATED alias for 'sources' (v0.19.0)

CODE INDEXING (v0.19.0 / v0.20.0 Cathedral II)
  code-def <symbol> [--lang l]       Find the definition of a symbol across code pages
  code-refs <symbol> [--lang l]      Find all references to a symbol (JSON-first)
  code-callers <symbol>              Who calls this symbol? (v0.20.0 A1)
  code-callees <symbol>              What does this symbol call? (v0.20.0 A1)
  query <q> --lang <l>               Filter hybrid search to one language (v0.20.0)
  query <q> --symbol-kind <k>        Filter to symbol type (function|class|method|...) (v0.20.0)
  reconcile-links [--dry-run]        Batch-recompute doc↔impl edges (v0.20.0)
  reindex-code [--source id] [--yes] Explicit code-page reindex (v0.20.0)
  sync --strategy code               Sync code files into the brain

JOBS (Minions)
  jobs submit <name> [--params JSON]  Submit background job [--follow] [--dry-run]
  jobs list [--status S] [--limit N]  List jobs
  jobs get <id>                       Job details + history
  jobs cancel <id>                    Cancel job
  jobs retry <id>                     Re-queue failed/dead job
  jobs prune [--older-than 30d]       Clean old jobs
  jobs stats                          Job health dashboard
  jobs work [--queue Q]               Start worker daemon (Postgres only)

ADMIN
  stats                              Brain statistics
  health                             Brain health dashboard
  history <slug>                     Page version history
  revert <slug> <version-id>         Revert to version
  features [--json] [--auto-fix]     Scan usage + recommend unused features
  autopilot [--repo] [--interval N]  Self-maintaining brain daemon
  config [show|get|set] <key> [val]  Brain config
  storage status [--repo <path>]     Storage tier status and health
        [--json]                     (git-tracked vs supabase-only)
  serve                              MCP server (stdio)
  serve --http [--port N]            HTTP MCP server with OAuth 2.1
    --token-ttl N                    Access token TTL in seconds (default: 3600)
    --enable-dcr                     Enable Dynamic Client Registration
    --public-url URL                 Public issuer URL (required behind proxy/tunnel)
  call <tool> '<json>'               Raw tool invocation
  version                            Version info
  --tools-json                       Tool discovery (JSON)

Run gbrain <command> --help for command-specific help.
`);
}
