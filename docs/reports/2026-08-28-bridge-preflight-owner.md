# Bridge preflight owner evidence — 2026-08-28

The live bridge-refresh cron still writes Documents Dashboard projections. This
wave introduces a Workspace-only bridge readiness check; the exact cron cutover
and post-cutover evidence will be recorded after accepted release deployment.

The canonical candidate targets `accepted-20260829` and replaces only the 06:05
bridge-refresh writer. The existing Dashboard content and legacy writer remain
intact until the candidate passes release and post-cutover verification.
