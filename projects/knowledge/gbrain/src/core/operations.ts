/**
 * Contract-first operation definitions — barrel file.
 *
 * Re-exports shared types from operations-types.ts and the operation registry
 * (operations array + operationsByName) from operations/exports.ts.
 *
 * Every import below is a split domain module under operations/. The original
 * single-file god module (3841 lines) was decomposed on 2026-06-20 as debt
 * remediation: DEBT-GBRAIN-OPERATIONS-TS.
 *
 * Before adding a new operation:
 *   1. Create or extend the appropriate domain file in operations/.
 *   2. Export the const (export const my_op: Operation = { ... }).
 *   3. Add it to the operations array in operations/exports.ts.
 *   4. Run `bun test` to verify no breakage.
 */

// Re-export all shared types and utilities from the types module
// (backward compatible — existing importers don't need to change paths).
export * from './operations-types.ts';

// Re-export the operation registry.
export { operations, operationsByName } from './operations/exports.ts';
