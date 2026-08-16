// AUTO-GENERATED — do not edit by hand.
// Source: admin/dist/ at 2026-05-22.
//
// NOTE (2026-06-24): admin/ directory was removed as part of gbrain UI
// deprecation. This module now exports empty placeholders so that
// src/commands/serve-http.ts falls back to 404 for /admin routes without
// breaking the build. If admin is reintroduced, regenerate via
// `bun run scripts/build-admin-embedded.ts`.

export interface AdminAsset {
  path: string;
  mime: string;
}

export const ADMIN_ASSETS: Record<string, AdminAsset> = {};

/** Index entry point for SPA fallback. */
export const ADMIN_INDEX_HTML: AdminAsset | undefined = undefined;

export const ADMIN_ASSET_COUNT = 0;
