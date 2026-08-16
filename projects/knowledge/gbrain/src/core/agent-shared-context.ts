/**
 * G-DEL.4 / BET-b7da — cross-agent shared context (identity-scoped store).
 *
 * Pure in-memory store + optional KOS SQLite retrieve adapter.
 * Does NOT implement multi-machine registry/scheduling (G-DEL.1) or
 * multi-node sync (G-DEL.3). Safe to land pre-M1 in the gbrain submodule.
 */

export type AgentId = string;

export interface SharedContextEntry {
  key: string;
  value: string;
  writer: AgentId;
  writtenAt: string;
  tags?: string[];
}

export interface SharedContextRecord extends SharedContextEntry {
  readers: AgentId[];
}

/** C3 collaboration product (Batch3, ADR-0237): 角色协作产物写入公共黑板. */
export interface CollabProductEntry {
  taskRef: string;
  fromRole: string;
  toRole: string | null;
  messageType: string; // research_result | delivery_registered | handshake trail
  correlationId?: string;
  payload: string; // JSON-serialized
  writer: AgentId;
}

/** In-process store keyed by scope (e.g. task-id or brain-id). */
export class AgentSharedContextStore {
  private readonly byScope = new Map<string, Map<string, SharedContextRecord>>();

  constructor(private readonly defaultScope = "default") {}

  write(
    writer: AgentId,
    key: string,
    value: string,
    opts?: { scope?: string; tags?: string[]; readers?: AgentId[] },
  ): SharedContextRecord {
    if (!writer || !writer.trim()) {
      throw new Error("writer agent id is required");
    }
    if (!key || !key.trim()) {
      throw new Error("key is required");
    }
    const scope = opts?.scope ?? this.defaultScope;
    let bucket = this.byScope.get(scope);
    if (!bucket) {
      bucket = new Map();
      this.byScope.set(scope, bucket);
    }
    const rec: SharedContextRecord = {
      key,
      value,
      writer,
      writtenAt: new Date().toISOString(),
      tags: opts?.tags ? [...opts.tags] : undefined,
      readers: opts?.readers ? [...opts.readers] : [],
    };
    bucket.set(key, rec);
    return { ...rec, tags: rec.tags ? [...rec.tags] : undefined, readers: [...rec.readers] };
  }

  /**
   * Read a key. Visible if:
   * - reader === writer, or
   * - readers list empty (shared to all agents in scope), or
   * - reader is listed in readers.
   */
  read(reader: AgentId, key: string, opts?: { scope?: string }): SharedContextRecord | null {
    if (!reader || !reader.trim()) {
      throw new Error("reader agent id is required");
    }
    const scope = opts?.scope ?? this.defaultScope;
    const bucket = this.byScope.get(scope);
    if (!bucket) return null;
    const rec = bucket.get(key);
    if (!rec) return null;
    if (rec.writer === reader) return cloneRec(rec);
    if (rec.readers.length === 0) return cloneRec(rec);
    if (rec.readers.includes(reader)) return cloneRec(rec);
    return null;
  }

  listVisible(reader: AgentId, opts?: { scope?: string }): SharedContextRecord[] {
    const scope = opts?.scope ?? this.defaultScope;
    const bucket = this.byScope.get(scope);
    if (!bucket) return [];
    const out: SharedContextRecord[] = [];
    for (const rec of bucket.values()) {
      const visible = this.read(reader, rec.key, { scope });
      if (visible) out.push(visible);
    }
    return out;
  }

  /** Export all records for a scope (for KOS seed / index adapters). */
  exportScope(scope?: string): SharedContextRecord[] {
    const s = scope ?? this.defaultScope;
    const bucket = this.byScope.get(s);
    if (!bucket) return [];
    return [...bucket.values()].map(cloneRec);
  }

  // ─── C3: collaboration blackboard (Batch3, ADR-0237) ───

  /**
   * Write a collaboration product to the public blackboard.
   * scope = taskRef; tags = [fromRole, messageType, toRole?]; readers empty
   * → visible to all agents in scope (public blackboard, downstream reuse).
   */
  writeCollabProduct(entry: CollabProductEntry): SharedContextRecord {
    if (!entry.taskRef?.trim()) throw new Error("taskRef is required");
    if (!entry.fromRole?.trim()) throw new Error("fromRole is required");
    if (!entry.messageType?.trim()) throw new Error("messageType is required");
    const key = `${entry.messageType}:${entry.correlationId ?? entry.writer}:${Date.now()}`;
    const tags = [entry.fromRole, entry.messageType];
    if (entry.toRole) tags.push(entry.toRole);
    return this.write(entry.writer, key, entry.payload, {
      scope: entry.taskRef,
      tags,
    });
  }

  /**
   * Retrieve collaboration products (cross-task when taskRef omitted).
   * C3 跨任务上下文复用: 后续任务可检索前序协作产物 (by role / messageType).
   */
  retrieveCollab(
    reader: AgentId,
    opts: {
      taskRef?: string;
      fromRole?: string;
      messageType?: string;
      scope?: string;
    } = {},
  ): SharedContextRecord[] {
    const scopes = opts.scope ?? opts.taskRef
      ? [opts.scope ?? opts.taskRef!]
      : [...this.byScope.keys()];
    const out: SharedContextRecord[] = [];
    for (const scope of scopes) {
      const visible = this.listVisible(reader, { scope });
      for (const rec of visible) {
        const tags = rec.tags ?? [];
        if (opts.fromRole && !tags.includes(opts.fromRole)) continue;
        if (opts.messageType && !tags.includes(opts.messageType)) continue;
        out.push(rec);
      }
    }
    return out;
  }
}

function cloneRec(rec: SharedContextRecord): SharedContextRecord {
  return {
    ...rec,
    tags: rec.tags ? [...rec.tags] : undefined,
    readers: [...rec.readers],
  };
}

/** Build a KOS-searchable document body from a shared context record. */
export function formatSharedContextForKos(rec: SharedContextRecord, scope: string): string {
  const tags = rec.tags?.length ? rec.tags.join(", ") : "";
  return [
    `# shared-context/${scope}/${rec.key}`,
    `writer: ${rec.writer}`,
    `writtenAt: ${rec.writtenAt}`,
    tags ? `tags: ${tags}` : "",
    "",
    rec.value,
  ]
    .filter((line) => line !== undefined)
    .join("\n");
}

export interface KosDocumentRow {
  doc_id: string;
  title: string;
  canonical_path: string;
  body_preview: string;
  indexed_at: string;
}

export interface KosQueryResult {
  path: string;
  title: string;
  preview: string;
  score: number;
}

/**
 * Minimal KOS adapter: query documents table by LIKE on title/path/body_preview.
 * Uses better-sqlite3-compatible shape OR a simple query function injection
 * so unit tests can drive with an in-memory stub without native bindings.
 */
export type KosSqlRunner = (sql: string, params: unknown[]) => KosDocumentRow[];

export function createKosRetrieve(run: KosSqlRunner) {
  return function retrieveSharedViaKos(query: string, limit = 10): KosQueryResult[] {
    const q = (query || "").trim();
    if (!q) return [];
    const like = `%${q.replace(/%/g, "")}%`;
    const rows = run(
      `SELECT doc_id, title, canonical_path, body_preview, indexed_at
       FROM documents
       WHERE title LIKE ? OR canonical_path LIKE ? OR body_preview LIKE ?
       LIMIT ?`,
      [like, like, like, limit],
    );
    return rows.map((r, i) => ({
      path: r.canonical_path,
      title: r.title,
      preview: r.body_preview,
      score: Math.max(0, 1 - i * 0.05),
    }));
  };
}

/**
 * Seed KOS documents table from shared-context export (adapter for seed pipeline).
 * `upsert` is injected so tests don't need real sqlite.
 */
export function seedSharedContextIntoKos(
  records: SharedContextRecord[],
  scope: string,
  upsert: (row: {
    doc_id: string;
    title: string;
    canonical_path: string;
    body_preview: string;
    indexed_at: string;
  }) => void,
): number {
  let n = 0;
  for (const rec of records) {
    const body = formatSharedContextForKos(rec, scope);
    const path = `gbrain://shared-context/${scope}/${rec.key}`;
    const title = `shared-context ${scope}/${rec.key}`;
    upsert({
      doc_id: simpleHash(path),
      title,
      canonical_path: path,
      body_preview: body.slice(0, 500),
      indexed_at: new Date().toISOString(),
    });
    n += 1;
  }
  return n;
}

function simpleHash(s: string): string {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
  }
  return `sc${(h >>> 0).toString(16).padStart(8, "0")}`;
}
