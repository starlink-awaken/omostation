import { existsSync, mkdirSync, readFileSync } from 'node:fs';

import { z } from 'zod';
import type { BrainEngine, FactRow } from './engine.ts';
import { gbrainPath } from './config.ts';
import type { SearchResult } from './types.ts';
import { AppendOnlyLog, ZTimestampSchema } from './append-only-log.ts';

const PINS_CONFIG_KEY = 'memory_tree.pins';
const PINS_PATH = gbrainPath('memory-tree-pins.json');

type MemoryTreeNodeType = 'root' | 'entity' | 'page' | 'fact';

export interface MemoryTreeNode {
  id: string;
  type: MemoryTreeNodeType;
  label: string;
  parent_id: string | null;
  summary?: string;
}

function unique<T>(values: T[]): T[] {
  return Array.from(new Set(values));
}

// ── Pin log（AppendOnlyLog）────────────────────────────────────────────────────
// v0.37.x — pin 状态从单一 writeFileSync 迁移到 AppendOnlyLog。
// 历史单一文件 PINS_PATH 保留读取（向后兼容已存在的 pin 数据），
// 新增 pin 写入 pin-log-{YYYY-Www}.jsonl，O_APPEND 原子追加。
//
// R50 P0：原 writePinFile 存在竞争风险——多进程 pin 时最后一个 writeFileSync
// 覆盖前面的，pin 状态会丢失。AppendOnlyLog 用 O_APPEND 原子追加，
// 读端从完整 JSONL 重建（union of all log lines）。

const PinEventSchema = ZTimestampSchema.extend({
  event: z.literal('pin'),
  node_ids: z.array(z.string()),
});
type PinEvent = z.infer<typeof PinEventSchema>;

function pinLog(): AppendOnlyLog {
  return new AppendOnlyLog({
    filePath: gbrainPath('audit/memory-tree-pins-{YYYY-Www}.jsonl'),
    prefix: 'memory-tree-pins',
    schema: PinEventSchema,
  });
}

function readPinFile(): string[] {
  if (!existsSync(PINS_PATH)) return [];
  try {
    const raw = JSON.parse(readFileSync(PINS_PATH, 'utf8'));
    return Array.isArray(raw) ? raw.filter((value): value is string => typeof value === 'string') : [];
  } catch {
    return [];
  }
}

/** 从 PINS_PATH（旧）+ pin-log-{YYYY-Www}.jsonl（新，O_APPEND 原子）合并所有 pin */
function readPinsFromLog(): string[] {
  return pinLog().readAllSync<PinEvent>().flatMap(e => e.node_ids);
}

function entityId(slug: string) {
  return `entity:${slug}`;
}

function pageId(slug: string) {
  return `page:${slug}`;
}

function factId(fact: FactRow, index: number) {
  return `fact:${fact.entity_slug || 'unknown'}:${index}`;
}

function pageNode(result: SearchResult): MemoryTreeNode {
  const parent = result.slug.includes('/') ? entityId(result.slug.split('/')[1] ?? result.slug) : null;
  return {
    id: pageId(result.slug),
    type: 'page',
    label: result.title || result.slug,
    parent_id: parent,
    summary: result.chunk_text || '',
  };
}

function factNode(fact: FactRow, index: number): MemoryTreeNode {
  return {
    id: factId(fact, index),
    type: 'fact',
    label: fact.entity_slug || `fact-${index + 1}`,
    parent_id: fact.entity_slug ? entityId(fact.entity_slug) : null,
    summary: fact.fact,
  };
}

async function fallbackPages(engine: BrainEngine, query: string, limit: number): Promise<SearchResult[]> {
  const escaped = query.toLowerCase().replace(/'/g, "''");
  const rows = await engine.executeRaw(
    `SELECT slug, title, compiled_truth
     FROM pages
     WHERE lower(coalesce(title, '')) LIKE '%${escaped}%'
        OR lower(coalesce(compiled_truth, '')) LIKE '%${escaped}%'
     LIMIT ${Math.max(limit, 1)}`,
  ) as Array<{ slug: string; title: string; compiled_truth: string }>;
  return rows.map(row => ({
    slug: row.slug,
    page_id: 0,
    title: row.title,
    type: 'wiki',
    chunk_text: row.compiled_truth,
    chunk_source: 'compiled_truth' as const,
    chunk_id: 0,
    chunk_index: 0,
    score: 1,
    stale: false,
  })) as unknown as SearchResult[];
}

export async function buildMemoryTree(engine: BrainEngine, query: string, limit = 10) {
  const primaryResults = await engine.searchKeyword(query, { limit });
  const searchResults = primaryResults.length > 0 ? primaryResults : await fallbackPages(engine, query, limit);
  const facts = await engine.listFactsSince('default', new Date(0), { limit, activeOnly: true });
  const nodes: MemoryTreeNode[] = [{ id: 'root', type: 'root', label: query, parent_id: null }];
  const entitySlugs = unique([
    ...searchResults.map(result => result.slug.split('/')[1] ?? result.slug),
    ...facts.map(fact => fact.entity_slug).filter((slug): slug is string => Boolean(slug)),
  ]);

  for (const slug of entitySlugs) {
    nodes.push({ id: entityId(slug), type: 'entity', label: slug, parent_id: 'root' });
  }
  for (const result of searchResults) {
    nodes.push(pageNode(result));
  }
  for (const [index, fact] of facts.entries()) {
    nodes.push(factNode(fact, index));
  }

  return {
    root: nodes[0],
    nodes,
    edges: nodes
      .filter(node => node.parent_id)
      .map(node => ({ from: node.parent_id as string, to: node.id })),
    pinned: await readPinnedNodeIds(engine),
  };
}

export async function readPinnedNodeIds(engine: BrainEngine): Promise<string[]> {
  // v0.37.x — 先读新 log（O_APPEND 原子），再读旧 PINS_PATH（向后兼容）
  const fromLog = readPinsFromLog();
  if (fromLog.length > 0) return unique(fromLog);
  // log 为空：检查 DB config（跨进程持久化）
  const stored = await engine.getConfig(PINS_CONFIG_KEY);
  if (stored) {
    try {
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed)) {
        return parsed.filter((value): value is string => typeof value === 'string');
      }
    } catch {
      /* fall through to file */
    }
  }
  // 兜底：旧 PINS_PATH（pre-AppendOnlyLog 写过的）
  return readPinFile();
}

export async function pinMemoryTreeNodes(engine: BrainEngine, nodeIds: string[]) {
  // 1. DB config（跨进程单一真相）
  const merged = unique([...(await readPinnedNodeIds(engine)), ...nodeIds]);
  await engine.setConfig(PINS_CONFIG_KEY, JSON.stringify(merged));
  // 2. AppendOnlyLog 追加（O_APPEND 原子，R50 P0 修复竞争风险）
  pinLog().append({ ts: new Date().toISOString(), event: 'pin', node_ids: nodeIds });
  return merged;
}

export async function getMemoryTreeStats(engine: BrainEngine) {
  const [pageRows, factRows] = await Promise.all([
    engine.executeRaw('SELECT COUNT(*) AS count FROM pages'),
    engine.executeRaw('SELECT COUNT(*) AS count FROM facts'),
  ]);
  const pinned = await readPinnedNodeIds(engine);
  return {
    pinned_count: pinned.length,
    totals: {
      pages: Number(pageRows[0]?.count ?? 0),
      facts: Number(factRows[0]?.count ?? 0),
    },
  };
}
