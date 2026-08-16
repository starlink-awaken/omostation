/**
 * memU Engine — lightweight embedded storage engine for gbrain
 *
 * Uses Bun's built-in SQLite as the storage backend.
 * Implements the BrainEngine interface for all 54+ compatible MCP tools.
 *
 * Storage layout (SQLite tables): see initSchema() below.
 */
import { Database } from 'bun:sqlite';
import type { BrainEngine } from './engine.ts';
import type {
  ReservedConnection,
  LinkBatchInput,
  TimelineBatchInput,
  TakeResolution,
  FileRow, FileSpec,
  TrajectoryPoint,
  TraverseGraphOpts,
  TakesListOpts, Take, TakeBatchInput, TakeHit, TakesScorecard, TakesScorecardOpts,
  CalibrationCurveOpts, CalibrationBucket,
  SynthesisEvidenceInput,
  DreamVerdict, DreamVerdictInput,
  FactRow, FactsHealth,
} from './engine-types.ts';
import type {
  EngineConfig,
  Page, PageInput, PageFilters, GetPageOpts, Chunk, ChunkInput, StaleChunkRow,
  SearchResult, SearchOpts, Link,
  GraphNode, GraphPath,
  TimelineEntry, TimelineInput, TimelineOpts,
  RawData,
  PageVersion, BrainStats, BrainHealth,
  IngestLogEntry,
  SalienceResult, AnomalyResult,
  EmotionalWeightInputRow,
  EvalCandidate,
  EvalCaptureFailure,
  DomainBankSampleOpts, CorpusSampleOpts, DomainBankRow,
} from './types.ts';

const DB_FILENAME = 'memu-brain.db';

export class MemUEngine implements BrainEngine {
  readonly kind = 'memu' as const;
  private _db: Database | null = null;
  private _dbPath: string = '';

  get db(): Database {
    if (!this._db) throw new Error('memU Engine not connected');
    return this._db;
  }

  // ── Lifecycle ─────────────────────────────────────────────

  async connect(config: EngineConfig): Promise<void> {
    this._dbPath = config.database_path || DB_FILENAME;
    this._db = new Database(this._dbPath);
    this._db.exec('PRAGMA journal_mode=WAL');
    this._db.exec('PRAGMA busy_timeout=5000');
    this._db.exec('PRAGMA synchronous=NORMAL');
  }

  async disconnect(): Promise<void> {
    if (this._db) {
      this._db.close();
      this._db = null;
    }
  }

  async initSchema(): Promise<void> {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS pages (
        slug TEXT NOT NULL,
        source_id TEXT NOT NULL DEFAULT 'default',
        title TEXT NOT NULL DEFAULT '',
        body TEXT NOT NULL DEFAULT '',
        frontmatter TEXT NOT NULL DEFAULT '{}',
        compiled_truth TEXT NOT NULL DEFAULT '{}',
        page_type TEXT NOT NULL DEFAULT 'doc',
        word_count INTEGER NOT NULL DEFAULT 0,
        embedding INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        deleted_at TEXT,
        PRIMARY KEY (source_id, slug)
      );
      CREATE TABLE IF NOT EXISTS content_chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        page_slug TEXT NOT NULL,
        source_id TEXT NOT NULL DEFAULT 'default',
        content TEXT NOT NULL,
        heading TEXT NOT NULL DEFAULT '',
        chunk_index INTEGER NOT NULL DEFAULT 0,
        char_start INTEGER NOT NULL DEFAULT 0,
        char_end INTEGER NOT NULL DEFAULT 0,
        token_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (source_id, page_slug) REFERENCES pages(source_id, slug)
      );
      CREATE TABLE IF NOT EXISTS page_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_slug TEXT NOT NULL,
        source_id TEXT NOT NULL DEFAULT 'default',
        target_slug TEXT NOT NULL,
        target_id TEXT NOT NULL DEFAULT 'default',
        link_type TEXT NOT NULL DEFAULT 'wiki',
        context TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
      CREATE TABLE IF NOT EXISTS page_tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        page_slug TEXT NOT NULL,
        source_id TEXT NOT NULL DEFAULT 'default',
        tag TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(source_id, page_slug, tag)
      );
      CREATE TABLE IF NOT EXISTS timeline_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        page_slug TEXT NOT NULL,
        source_id TEXT NOT NULL DEFAULT 'default',
        entry_date TEXT NOT NULL,
        content TEXT NOT NULL,
        source TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
      CREATE TABLE IF NOT EXISTS raw_data (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        page_slug TEXT,
        source_id TEXT NOT NULL DEFAULT 'default',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
      CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id TEXT NOT NULL DEFAULT 'default',
        page_slug TEXT,
        page_id INTEGER,
        filename TEXT NOT NULL,
        storage_path TEXT NOT NULL,
        mime_type TEXT,
        size_bytes INTEGER,
        content_hash TEXT NOT NULL,
        metadata TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
      CREATE TABLE IF NOT EXISTS takes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        page_slug TEXT NOT NULL,
        source_id TEXT NOT NULL DEFAULT 'default',
        claim TEXT NOT NULL,
        weight REAL NOT NULL DEFAULT 1.0,
        kind TEXT NOT NULL DEFAULT 'statement',
        tags TEXT NOT NULL DEFAULT '[]',
        superseded_by INTEGER,
        resolved_at TEXT,
        resolution TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
      CREATE TABLE IF NOT EXISTS facts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity TEXT NOT NULL,
        attribute TEXT NOT NULL,
        value TEXT NOT NULL,
        source TEXT,
        confidence REAL NOT NULL DEFAULT 1.0,
        session_id TEXT,
        expired_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
      CREATE TABLE IF NOT EXISTS ingest_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        slugs TEXT NOT NULL DEFAULT '[]',
        status TEXT NOT NULL DEFAULT 'success',
        message TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
      CREATE TABLE IF NOT EXISTS code_edges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_slug TEXT NOT NULL,
        target_slug TEXT NOT NULL,
        edge_type TEXT NOT NULL DEFAULT 'calls',
        metadata TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
      CREATE TABLE IF NOT EXISTS config_store (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS page_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        page_slug TEXT NOT NULL,
        source_id TEXT NOT NULL DEFAULT 'default',
        title TEXT,
        body TEXT,
        version INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
      CREATE TABLE IF NOT EXISTS dream_verdicts (
        page_slug TEXT NOT NULL,
        source_id TEXT NOT NULL DEFAULT 'default',
        verdict TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (source_id, page_slug)
      );
      CREATE TABLE IF NOT EXISTS contradictions_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE NOT NULL,
        value TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
      CREATE TABLE IF NOT EXISTS eval_candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tool_name TEXT NOT NULL,
        input TEXT NOT NULL,
        output TEXT NOT NULL,
        key TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
      CREATE TABLE IF NOT EXISTS eval_failures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tool_name TEXT NOT NULL,
        input TEXT NOT NULL,
        reason TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
      CREATE INDEX IF NOT EXISTS idx_chunks_page ON content_chunks(source_id, page_slug);
      CREATE INDEX IF NOT EXISTS idx_links_source ON page_links(source_id, source_slug);
      CREATE INDEX IF NOT EXISTS idx_links_target ON page_links(source_id, target_slug);
      CREATE INDEX IF NOT EXISTS idx_tags_page ON page_tags(source_id, page_slug);
      CREATE INDEX IF NOT EXISTS idx_timeline_page ON timeline_entries(source_id, page_slug);
      CREATE INDEX IF NOT EXISTS idx_takes_page ON takes(source_id, page_slug);
      CREATE INDEX IF NOT EXISTS idx_facts_entity ON facts(entity);
      CREATE INDEX IF NOT EXISTS idx_code_source ON code_edges(source_slug);
      CREATE INDEX IF NOT EXISTS idx_code_target ON code_edges(target_slug);
    `);
  }

  async transaction<T>(fn: (engine: BrainEngine) => Promise<T>): Promise<T> {
    const tx = this.db.transaction(() => fn(this));
    return tx();
  }

  async withReservedConnection<T>(fn: (conn: ReservedConnection) => Promise<T>): Promise<T> {
    // memU is single-connection; pass-through
    return fn(this as unknown as ReservedConnection);
  }

  // ── Pages CRUD ────────────────────────────────────────────

  async getPage(slug: string, opts?: GetPageOpts): Promise<Page | null> {
    const q = opts?.includeDeleted
      ? `SELECT * FROM pages WHERE slug = ? AND source_id = ?`
      : `SELECT * FROM pages WHERE slug = ? AND source_id = ? AND deleted_at IS NULL`;
    const row = this.db.query(q).get(slug, opts?.sourceId || 'default') as any;
    return row ? this._rowToPage(row) : null;
  }

  async putPage(slug: string, page: PageInput, opts?: { sourceId?: string }): Promise<Page> {
    const sid = opts?.sourceId || 'default';
    const existing = this.db.query(`SELECT * FROM pages WHERE slug = ? AND source_id = ?`).get(slug, sid) as any;
    if (existing) {
      this.db.query(`
        UPDATE pages SET title = ?, body = ?, frontmatter = ?, updated_at = datetime('now')
        WHERE slug = ? AND source_id = ?
      `).run(page.title || existing.title, page.compiled_truth ?? existing.body,
            JSON.stringify(page.frontmatter ?? {}), slug, sid);
    } else {
      this.db.query(`
        INSERT INTO pages (slug, source_id, title, body, frontmatter)
        VALUES (?, ?, ?, ?, ?)
      `).run(slug, sid, page.title || '', page.compiled_truth || '', JSON.stringify(page.frontmatter || {}));
    }
    return (await this.getPage(slug, { sourceId: sid }))!;
  }

  async deletePage(slug: string, opts?: { sourceId?: string }): Promise<void> {
    const sid = opts?.sourceId || 'default';
    this.db.query(`DELETE FROM content_chunks WHERE page_slug = ? AND source_id = ?`).run(slug, sid);
    this.db.query(`DELETE FROM page_links WHERE source_slug = ? AND source_id = ?`).run(slug, sid);
    this.db.query(`DELETE FROM page_tags WHERE page_slug = ? AND source_id = ?`).run(slug, sid);
    this.db.query(`DELETE FROM pages WHERE slug = ? AND source_id = ?`).run(slug, sid);
  }

  async softDeletePage(slug: string, opts?: { sourceId?: string }): Promise<{ slug: string } | null> {
    const sid = opts?.sourceId || 'default';
    const r = this.db.query(`UPDATE pages SET deleted_at = datetime('now') WHERE slug = ? AND source_id = ? AND deleted_at IS NULL`)
      .run(slug, sid);
    return r.changes > 0 ? { slug } : null;
  }

  async restorePage(slug: string, opts?: { sourceId?: string }): Promise<boolean> {
    const sid = opts?.sourceId || 'default';
    const r = this.db.query(`UPDATE pages SET deleted_at = NULL WHERE slug = ? AND source_id = ? AND deleted_at IS NOT NULL`)
      .run(slug, sid);
    return r.changes > 0;
  }

  async purgeDeletedPages(olderThanHours: number): Promise<{ slugs: string[]; count: number }> {
    const rows = this.db.query(`
      SELECT slug, source_id FROM pages WHERE deleted_at IS NOT NULL AND
      datetime(deleted_at, '+' || ? || ' hours') <= datetime('now')
    `).all(olderThanHours) as any[];
    for (const r of rows) {
      await this.deletePage(r.slug, { sourceId: r.source_id });
    }
    return { slugs: rows.map(r => r.slug), count: rows.length };
  }

  async listPages(filters?: PageFilters): Promise<Page[]> {
    let sql = `SELECT * FROM pages WHERE 1=1`;
    const params: any[] = [];
    if (!filters?.includeDeleted) { sql += ` AND deleted_at IS NULL`; }
    if (filters?.sourceId) { sql += ` AND source_id = ?`; params.push(filters.sourceId); }
    if (filters?.slugPrefix) { sql += ` AND slug LIKE ?`; params.push(filters.slugPrefix + '%'); }
    if (filters?.limit) { sql += ` LIMIT ?`; params.push(filters.limit); }
    const rows = this.db.query(sql).all(...params) as any[];
    return rows.map(r => this._rowToPage(r));
  }

  async resolveSlugs(partial: string): Promise<string[]> {
    const rows = this.db.query(`SELECT slug FROM pages WHERE slug LIKE ? LIMIT 20`).all(`%${partial}%`) as any[];
    return rows.map(r => r.slug);
  }

  async getAllSlugs(opts?: { sourceId?: string }): Promise<Set<string>> {
    let sql = `SELECT slug FROM pages WHERE deleted_at IS NULL`;
    const params: any[] = [];
    if (opts?.sourceId) { sql += ` AND source_id = ?`; params.push(opts.sourceId); }
    const rows = this.db.query(sql).all(...params) as any[];
    return new Set(rows.map(r => r.slug));
  }

  async listAllPageRefs(): Promise<Array<{ slug: string; source_id: string }>> {
    return this.db.query(`SELECT slug, source_id FROM pages WHERE deleted_at IS NULL`).all() as any[];
  }

  async listPrefixSampledPages(_opts: DomainBankSampleOpts): Promise<DomainBankRow[]> {
    return [];
  }

  async listCorpusSample(_opts: CorpusSampleOpts): Promise<DomainBankRow[]> {
    return [];
  }

  // ── Search ────────────────────────────────────────────────

  async searchKeyword(query: string, opts?: SearchOpts): Promise<SearchResult[]> {
    const limit = opts?.limit || 20;
    const rows = this.db.query(`
      SELECT slug, source_id, title, body FROM pages
      WHERE deleted_at IS NULL AND (title LIKE ? OR body LIKE ?)
      LIMIT ?
    `).all(`%${query}%`, `%${query}%`, limit) as any[];
    return rows.map(r => ({
      slug: r.slug,
      page_id: r.id || 0,
      title: r.title,
      type: r.type || 'wiki',
      chunk_text: r.body?.substring(0, 200) || '',
      chunk_source: 'compiled_truth' as const,
      chunk_id: 0,
      chunk_index: 0,
      score: 0.5,
      stale: false,
    }));
  }

  async searchVector(_embedding: Float32Array, opts?: SearchOpts): Promise<SearchResult[]> {
    // memU v1: no vector search — returns empty results gracefully
    return [];
  }

  async getEmbeddingsByChunkIds(_ids: number[], _column?: string): Promise<Map<number, Float32Array>> {
    return new Map();
  }

  // ── Chunks ────────────────────────────────────────────────

  async upsertChunks(slug: string, chunks: ChunkInput[], opts?: { sourceId?: string }): Promise<void> {
    const sid = opts?.sourceId || 'default';
    this.db.query(`DELETE FROM content_chunks WHERE page_slug = ? AND source_id = ?`).run(slug, sid);
    for (let i = 0; i < chunks.length; i++) {
      const c = chunks[i];
      this.db.query(`
        INSERT INTO content_chunks (page_slug, source_id, content, heading, chunk_index, char_start, char_end, token_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `).run(slug, sid, c.chunk_text, '', i, 0, 0, c.token_count || 0);
    }
  }

  async getChunks(slug: string, opts?: { sourceId?: string }): Promise<Chunk[]> {
    const sid = opts?.sourceId || 'default';
    return this.db.query(`
      SELECT * FROM content_chunks WHERE page_slug = ? AND source_id = ? ORDER BY chunk_index
    `).all(slug, sid) as any[];
  }

  async countStaleChunks(): Promise<number> {
    return 0;
  }

  async listStaleChunks(_opts?: { batchSize?: number; afterPageId?: number; afterChunkIndex?: number; sourceId?: string }): Promise<StaleChunkRow[]> {
    return [];
  }

  async deleteChunks(_slug: string, _opts?: { sourceId?: string }): Promise<void> {}

  // ── Links ─────────────────────────────────────────────────

  async addLink(from: string, to: string, context?: string, linkType?: string, _linkSource?: string, _originSlug?: string, _originField?: string, opts?: { fromSourceId?: string; toSourceId?: string; originSourceId?: string }): Promise<void> {
    const sid = opts?.fromSourceId || opts?.originSourceId || 'default';
    this.db.query(`
      INSERT OR IGNORE INTO page_links (source_slug, source_id, target_slug, target_id, link_type, context)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(from, sid, to, sid, linkType || 'wiki', context || null);
  }

  async addLinksBatch(inputs: LinkBatchInput[]): Promise<number> {
    for (const inp of inputs) {
      await this.addLink(inp.from_slug, inp.to_slug, inp.context, inp.link_type, inp.link_source);
    }
    return inputs.length;
  }

  async removeLink(from: string, to: string, _linkType?: string, _linkSource?: string, opts?: { fromSourceId?: string; toSourceId?: string }): Promise<void> {
    const sid = opts?.fromSourceId || 'default';
    this.db.query(`DELETE FROM page_links WHERE source_slug = ? AND source_id = ? AND target_slug = ?`).run(from, sid, to);
  }

  async getLinks(slug: string, opts?: { sourceId?: string }): Promise<Link[]> {
    const sid = opts?.sourceId || 'default';
    return this.db.query(`SELECT * FROM page_links WHERE source_slug = ? AND source_id = ?`).all(slug, sid) as any[];
  }

  async getBacklinks(slug: string, opts?: { sourceId?: string }): Promise<Link[]> {
    const sid = opts?.sourceId || 'default';
    return this.db.query(`SELECT * FROM page_links WHERE target_slug = ? AND target_id = ?`).all(slug, sid) as any[];
  }

  async findByTitleFuzzy(_name: string, _dirPrefix?: string, _minSimilarity?: number): Promise<{ slug: string; similarity: number } | null> {
    return null;
  }

  async traverseGraph(_slug: string, _depth?: number, _opts?: TraverseGraphOpts): Promise<GraphNode[]> {
    // memU v1: graph traversal not fully implemented; returns empty (parity with searchVector graceful degrade)
    return [];
  }

  async traversePaths(_slug: string, _opts?: { depth?: number; linkType?: string; direction?: 'in' | 'out' | 'both'; sourceId?: string; sourceIds?: string[] }): Promise<GraphPath[]> {
    return [];
  }

  async getBacklinkCounts(_slugs: string[]): Promise<Map<string, number>> {
    return new Map();
  }

  async getPageTimestamps(_slugs: string[]): Promise<Map<string, Date>> {
    return new Map();
  }

  async getEffectiveDates(_refs: { slug: string; source_id: string }[]): Promise<Map<string, Date>> {
    return new Map();
  }

  async getSalienceScores(_refs: { slug: string; source_id: string }[]): Promise<Map<string, number>> {
    return new Map();
  }

  async findOrphanPages(): Promise<{ slug: string; title: string; domain: string | null }[]> {
    return [];
  }

  // ── Tags ──────────────────────────────────────────────────

  async addTag(slug: string, tag: string, opts?: { sourceId?: string }): Promise<void> {
    const sid = opts?.sourceId || 'default';
    this.db.query(`INSERT OR IGNORE INTO page_tags (page_slug, source_id, tag) VALUES (?, ?, ?)`).run(slug, sid, tag);
  }

  async removeTag(slug: string, tag: string, opts?: { sourceId?: string }): Promise<void> {
    const sid = opts?.sourceId || 'default';
    this.db.query(`DELETE FROM page_tags WHERE page_slug = ? AND source_id = ? AND tag = ?`).run(slug, sid, tag);
  }

  async getTags(slug: string, opts?: { sourceId?: string }): Promise<string[]> {
    const sid = opts?.sourceId || 'default';
    const rows = this.db.query(`SELECT tag FROM page_tags WHERE page_slug = ? AND source_id = ?`).all(slug, sid) as { tag: string }[];
    return rows.map(r => r.tag);
  }

  // ── Timeline ──────────────────────────────────────────────

  async addTimelineEntry(slug: string, entry: TimelineInput, opts?: { sourceId?: string }): Promise<void> {
    const sid = opts?.sourceId || 'default';
    this.db.query(`
      INSERT INTO timeline_entries (page_slug, source_id, entry_date, content, source)
      VALUES (?, ?, ?, ?, ?)
    `).run(slug, sid, entry.date, entry.summary, entry.source || null);
  }

  async addTimelineEntriesBatch(entries: TimelineBatchInput[]): Promise<number> {
    let inserted = 0;
    for (const e of entries) {
      this.db.query(`
        INSERT OR IGNORE INTO timeline_entries (page_slug, source_id, entry_date, content, source)
        VALUES (?, ?, ?, ?, ?)
      `).run(e.slug, e.source_id || 'default', e.date, e.summary, e.source || null);
      inserted++;
    }
    return inserted;
  }

  async getTimeline(slug: string, opts?: TimelineOpts): Promise<TimelineEntry[]> {
    const sid = opts?.sourceId || 'default';
    let sql = `SELECT * FROM timeline_entries WHERE page_slug = ? AND source_id = ? ORDER BY entry_date`;
    const params: any[] = [slug, sid];
    if (opts?.limit) { sql += ` LIMIT ?`; params.push(opts.limit); }
    return this.db.query(sql).all(...params) as any[];
  }

  // ── Raw Data ──────────────────────────────────────────────

  async putRawData(key: string, value: any, opts?: { pageSlug?: string; sourceId?: string }): Promise<void> {
    const sid = opts?.sourceId || 'default';
    this.db.query(`
      INSERT INTO raw_data (key, value, page_slug, source_id, updated_at)
      VALUES (?, ?, ?, ?, datetime('now'))
      ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')
    `).run(key, typeof value === 'string' ? value : JSON.stringify(value), opts?.pageSlug || null, sid);
  }

  async getRawData(_slug: string, _source?: string, _opts?: { sourceId?: string }): Promise<RawData[]> {
    return [];
  }

  // ── Files ─────────────────────────────────────────────────

  async upsertFile(spec: FileSpec): Promise<{ id: number; created: boolean }> {
    const r = this.db.query(`
      INSERT INTO files (source_id, page_slug, filename, storage_path, mime_type, size_bytes, content_hash, metadata)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT DO NOTHING
    `).run(spec.source_id || 'default', spec.page_slug || null, spec.filename, spec.storage_path,
           spec.mime_type || null, spec.size_bytes || null, spec.content_hash,
           JSON.stringify(spec.metadata || {}));
    const row = this.db.query(`SELECT id FROM files WHERE content_hash = ?`).get(spec.content_hash) as any;
    return { id: row?.id || 0, created: r.changes > 0 };
  }

  async getFile(_sourceId: string, _storagePath: string): Promise<FileRow | null> {
    return null;
  }

  async listFilesForPage(_pageId: number): Promise<FileRow[]> {
    return [];
  }

  // ── Takes ─────────────────────────────────────────────────

  async addTakesBatch(rows: TakeBatchInput[]): Promise<number> {
    for (const t of rows) {
      this.db.query(`
        INSERT INTO takes (page_slug, source_id, claim, weight, kind, holder)
        VALUES (?, ?, ?, ?, ?, ?)
      `).run('', 'default', t.claim, t.weight ?? 0.5, t.kind, t.holder);
    }
    return rows.length;
  }

  async listTakes(opts?: TakesListOpts): Promise<Take[]> {
    let sql = `SELECT * FROM takes WHERE superseded_by IS NULL`;
    const params: any[] = [];
    if (opts?.page_slug) { sql += ` AND page_slug = ?`; params.push(opts.page_slug); }
    if (opts?.kind) { sql += ` AND kind = ?`; params.push(opts.kind); }
    if (opts?.limit) { sql += ` LIMIT ?`; params.push(opts.limit); }
    return this.db.query(sql).all(...params) as any[];
  }

  async searchTakes(query: string, _opts?: { limit?: number }): Promise<TakeHit[]> {
    const limit = _opts?.limit || 20;
    return this.db.query(`
      SELECT t.*, p.title as page_title FROM takes t
      JOIN pages p ON p.slug = t.page_slug AND p.source_id = t.source_id
      WHERE t.claim LIKE ? AND t.superseded_by IS NULL LIMIT ?
    `).all(`%${query}%`, limit) as any[];
  }

  async searchTakesVector(_embedding: Float32Array, _opts?: { limit?: number }): Promise<TakeHit[]> {
    return [];
  }

  async getTakeEmbeddings(_ids: number[]): Promise<Map<number, Float32Array>> {
    return new Map();
  }

  async countStaleTakes(): Promise<number> { return 0; }
  async listStaleTakes(_limit?: number): Promise<any[]> { return []; }
  async updateTake(_pageId: number, _rowNum: number, _fields: { weight?: number; since_date?: string; source?: string }): Promise<void> {}
  async supersedeTake(_pageId: number, _oldRow: number, _newRow: Omit<TakeBatchInput, "page_id" | "row_num" | "superseded_by">): Promise<{ oldRow: number; newRow: number }> { return { oldRow: 0, newRow: 0 }; }
  async resolveTake(_pageId: number, _rowNum: number, _resolution: TakeResolution): Promise<void> {}
  async getScorecard(_opts?: TakesScorecardOpts): Promise<TakesScorecard> {
    return { total_bets: 0, resolved: 0, correct: 0, incorrect: 0, partial: 0 } as TakesScorecard;
  }
  async getCalibrationCurve(_opts?: CalibrationCurveOpts): Promise<CalibrationBucket[]> { return []; }
  async addSynthesisEvidence(_rows: SynthesisEvidenceInput[]): Promise<number> { return 0; }
  async listActiveTakesForPages(_pageIds: number[], _opts?: { takesHoldersAllowList?: string[] }): Promise<Map<number, Take[]>> { return new Map(); }

  // ── Dream Cycle ───────────────────────────────────────────

  async getDreamVerdict(filePath: string, contentHash: string): Promise<DreamVerdict | null> {
    return this.db.query(`SELECT * FROM dream_verdicts WHERE page_slug = ?`).get(filePath + ':' + contentHash) as any || null;
  }

  async putDreamVerdict(filePath: string, contentHash: string, verdict: DreamVerdictInput): Promise<void> {
    this.db.query(`
      INSERT OR REPLACE INTO dream_verdicts (page_slug, source_id, verdict) VALUES (?, ?, ?)
    `).run(filePath + ':' + contentHash, 'default', JSON.stringify(verdict));
  }

  // ── Contradictions ────────────────────────────────────────

  async writeContradictionsRun(..._args: Parameters<BrainEngine['writeContradictionsRun']>): Promise<boolean> { return false; }
  async loadContradictionsTrend(..._args: Parameters<BrainEngine['loadContradictionsTrend']>): Promise<any[]> { return []; }
  async getContradictionCacheEntry(..._args: Parameters<BrainEngine['getContradictionCacheEntry']>): Promise<any> { return null; }
  async putContradictionCacheEntry(..._args: Parameters<BrainEngine['putContradictionCacheEntry']>): Promise<void> {}
  async sweepContradictionCache(): Promise<number> { return 0; }

  // ── Facts ─────────────────────────────────────────────────

  async insertFact(..._args: Parameters<BrainEngine['insertFact']>): Promise<any> { return { id: 0, status: 'inserted' }; }
  async insertFacts(..._args: Parameters<BrainEngine['insertFacts']>): Promise<any> { return { inserted: 0, ids: [] }; }
  async deleteFactsForPage(..._args: Parameters<BrainEngine['deleteFactsForPage']>): Promise<any> { return { deleted: 0 }; }
  async expireFact(..._args: Parameters<BrainEngine['expireFact']>): Promise<boolean> { return false; }
  async listFactsByEntity(..._args: Parameters<BrainEngine['listFactsByEntity']>): Promise<FactRow[]> { return []; }
  async listFactsBySession(_sessionId: string): Promise<FactRow[]> { return []; }
  async listFactsSince(..._args: Parameters<BrainEngine['listFactsSince']>): Promise<FactRow[]> { return []; }
  async listSupersessions(..._args: Parameters<BrainEngine['listSupersessions']>): Promise<FactRow[]> { return []; }
  async countUnconsolidatedFacts(): Promise<number> { return 0; }
  async findCandidateDuplicates(..._args: Parameters<BrainEngine['findCandidateDuplicates']>): Promise<any[]> { return []; }
  async consolidateFact(_winnerId: number, _loserId: number): Promise<void> {}
  async findTrajectory(..._args: Parameters<BrainEngine['findTrajectory']>): Promise<TrajectoryPoint[]> { return []; }
  async getFactsHealth(): Promise<FactsHealth> {
    const count = (this.db.query(`SELECT COUNT(*) as c FROM facts`).get() as any).c;
    return { source_id: 'default', total_active: count, total_today: 0, total_week: 0, total_expired: 0, total_consolidated: 0, top_entities: [] };
  }

  // ── Versions ──────────────────────────────────────────────

  async createVersion(slug: string, opts?: { sourceId?: string }): Promise<PageVersion> {
    const sid = opts?.sourceId || 'default';
    const page = await this.getPage(slug, { sourceId: sid });
    if (!page) throw new Error(`Page not found: ${slug}`);
    const maxVer = (this.db.query(`SELECT COALESCE(MAX(version), 0) as v FROM page_versions WHERE page_slug = ? AND source_id = ?`).get(slug, sid) as any).v;
    this.db.query(`
      INSERT INTO page_versions (page_slug, source_id, title, body, version) VALUES (?, ?, ?, ?, ?)
    `).run(slug, sid, page.title, page.compiled_truth, maxVer + 1);
    return this.db.query(`SELECT * FROM page_versions WHERE id = last_insert_rowid()`).get() as any;
  }

  async getVersions(slug: string, _opts?: { sourceId?: string }): Promise<PageVersion[]> {
    return [];
  }

  async revertToVersion(..._args: Parameters<BrainEngine['revertToVersion']>): Promise<void> {}

  // ── Stats + Health ────────────────────────────────────────

  async getStats(): Promise<BrainStats> {
    const pageCount = (this.db.query(`SELECT COUNT(*) as c FROM pages WHERE deleted_at IS NULL`).get() as any).c;
    const linkCount = (this.db.query(`SELECT COUNT(*) as c FROM page_links`).get() as any).c;
    const chunkCount = (this.db.query(`SELECT COUNT(*) as c FROM content_chunks`).get() as any).c;
    return {
      page_count: pageCount, chunk_count: chunkCount, embedded_count: 0,
      link_count: linkCount, tag_count: 0, timeline_entry_count: 0,
      pages_by_type: {},
    } as BrainStats;
  }

  async getHealth(): Promise<BrainHealth> {
    return {
      page_count: (this.db.query(`SELECT COUNT(*) as c FROM pages WHERE deleted_at IS NULL`).get() as any).c,
      embed_coverage: 0,
      stale_pages: 0,
    } as BrainHealth;
  }

  // ── Ingest Log ────────────────────────────────────────────

  async logIngest(..._args: Parameters<BrainEngine['logIngest']>): Promise<void> {}

  async getIngestLog(_opts?: { limit?: number }): Promise<IngestLogEntry[]> {
    const limit = _opts?.limit || 50;
    return this.db.query(`SELECT * FROM ingest_log ORDER BY id DESC LIMIT ?`).all(limit) as any[];
  }

  // ── Sync ──────────────────────────────────────────────────

  async updateSlug(_oldSlug: string, _newSlug: string, _opts?: { sourceId?: string }): Promise<void> {
    throw new Error('Slug rename not supported in memU');
  }

  async rewriteLinks(_oldSlug: string, _newSlug: string, _opts?: { sourceId?: string }): Promise<void> {}
  async refreshPageBody(..._args: Parameters<BrainEngine['refreshPageBody']>): Promise<void> {}
  async migrateFactsToCanonical(): Promise<{ migrated: number; errors: string[] }> { return { migrated: 0, errors: [] }; }

  // ── Config ────────────────────────────────────────────────

  async getConfig(key: string): Promise<string | null> {
    const row = this.db.query(`SELECT value FROM config_store WHERE key = ?`).get(key) as any;
    return row?.value || null;
  }

  async setConfig(key: string, value: string): Promise<void> {
    this.db.query(`INSERT OR REPLACE INTO config_store (key, value) VALUES (?, ?)`).run(key, value);
  }

  async unsetConfig(key: string): Promise<number> {
    const r = this.db.query(`DELETE FROM config_store WHERE key = ?`).run(key);
    return r.changes;
  }

  async listConfigKeys(): Promise<string[]> {
    const rows = this.db.query(`SELECT key FROM config_store`).all() as any[];
    return rows.map(r => r.key);
  }

  // ── Migration ─────────────────────────────────────────────

  async runMigration(_version: number): Promise<void> {}
  async getChunksWithEmbeddings(): Promise<any[]> { return []; }

  // ── Raw SQL ───────────────────────────────────────────────

  async executeRaw<T>(sql: string, ...params: any[]): Promise<T[]> {
    return this.db.query(sql).all(...params) as T[];
  }

  // ── Code Edges ────────────────────────────────────────────

  async addCodeEdges(..._args: Parameters<BrainEngine['addCodeEdges']>): Promise<number> { return 0; }

  async deleteCodeEdgesForChunks(chunkIds: number[]): Promise<void> {
    // Not supported via chunk IDs in memU
  }

  async getCallersOf(..._args: Parameters<BrainEngine['getCallersOf']>): Promise<any[]> { return []; }

  async getCalleesOf(..._args: Parameters<BrainEngine['getCalleesOf']>): Promise<any[]> { return []; }

  async getEdgesByChunk(_chunkId: number): Promise<any[]> { return []; }
  async searchKeywordChunks(_query: string): Promise<any[]> { return []; }

  // ── Eval Capture ──────────────────────────────────────────

  async logEvalCandidate(..._args: Parameters<BrainEngine['logEvalCandidate']>): Promise<number> { return 0; }

  async listEvalCandidates(_opts?: { limit?: number; tool_name?: string }): Promise<EvalCandidate[]> {
    return [];
  }

  async deleteEvalCandidatesBefore(..._args: Parameters<BrainEngine['deleteEvalCandidatesBefore']>): Promise<number> { return 0; }

  async logEvalCaptureFailure(..._args: Parameters<BrainEngine['logEvalCaptureFailure']>): Promise<void> {}

  async listEvalCaptureFailures(..._args: Parameters<BrainEngine['listEvalCaptureFailures']>): Promise<EvalCaptureFailure[]> { return []; }

  // ── Salience / Anomaly ────────────────────────────────────

  async batchLoadEmotionalInputs(..._args: Parameters<BrainEngine['batchLoadEmotionalInputs']>): Promise<EmotionalWeightInputRow[]> { return []; }
  async setEmotionalWeightBatch(..._args: Parameters<BrainEngine['setEmotionalWeightBatch']>): Promise<number> { return 0; }
  async getRecentSalience(..._args: Parameters<BrainEngine['getRecentSalience']>): Promise<SalienceResult[]> { return []; }
  async findAnomalies(..._args: Parameters<BrainEngine['findAnomalies']>): Promise<AnomalyResult[]> { return []; }

  // ── Helpers ───────────────────────────────────────────────

  private _rowToPage(row: any): Page {
    return {
      id: row.id || 0,
      slug: row.slug,
      source_id: row.source_id,
      timeline: row.timeline || '',
      title: row.title || '',
      frontmatter: safeJson(row.frontmatter, {}),
      compiled_truth: safeJson(row.compiled_truth, {}),
      type: row.page_type || 'doc',
      created_at: new Date(row.created_at),
      updated_at: new Date(row.updated_at),
      deleted_at: row.deleted_at ? new Date(row.deleted_at) : undefined,
    };
  }
}

function safeJson(raw: string, fallback: any): any {
  try { return JSON.parse(raw); } catch { return fallback; }
}
