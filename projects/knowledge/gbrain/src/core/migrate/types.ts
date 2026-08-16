/**
 * migrate/types.ts — Migration type extracted from migrate.ts (F7114ABA Wave 2, 3/7).
 * Leaf type module so migration segment files can import Migration without
 * pulling migrate.ts (avoid circular).
 */
import type { BrainEngine } from '../engine.ts';
export type { BrainEngine };

export interface Migration {
  version: number;
  name: string;
  /** Engine-agnostic SQL. Used when `sqlFor` is absent. Set to '' for handler-only or sqlFor-only migrations. */
  sql: string;
  sqlFor?: { postgres?: string; pglite?: string; memu?: string };
  transaction?: boolean;
  handler?: (engine: BrainEngine) => Promise<void>;
  idempotent?: boolean;
  verify?: (engine: BrainEngine) => Promise<boolean>;
}
