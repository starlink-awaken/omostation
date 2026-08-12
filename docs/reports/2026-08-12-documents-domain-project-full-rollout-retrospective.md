# Documents Domain Projects — Phase 7 Full Rollout Retrospective

Date: 2026-08-12

## Outcome

All 12 manifests in the authoritative Documents L4 registry now expose the same
standalone-project contract:

| Domain ID | Documents project root |
|---|---|
| `shared` | `@公共` |
| `personal` | `@个人` |
| `vault` | `@学习进化` |
| `family` | `@家庭生活` |
| `creative` | `@创意创作` |
| `opc` | `@OPC` |
| `work-docs` | `@工作文档` |
| `work-weijian` | `@工作文档/卫健委` |
| `work-guozhuan` | `@工作文档/国转中心` |
| `work-liyongke` | `@工作文档/规自委` |
| `work-contracts` | `@工作文档/合同法规` |
| `cockpit` | `@驾驶舱` |

Each root has a thin `CLAUDE.md` projection and a thin `AGENTS.md` projection.
The projection restores the manifest ID, calls `domain_context(domain_id=...)`,
uses only capabilities returned by the accepted Cockpit Workspace MCP, and
reports `degraded` when that control plane is unavailable. Documents remains
read-only by default and no gateway instructs local execution from `_runtime`,
`_control`, `.kems/_scripts`, or an application root.

The nine legacy Claude entries and all pre-existing gateway files were backed
up before the batch update. The first three MVP domains (`vault`,
`work-weijian`, and `creative`) were already conformant and were not rewritten.

## SSOT Boundary

- Domain identity and content boundary: Documents `DOMAIN.yaml`, loaded through
  the L4 manifest registry.
- Client capability binding: Workspace
  `documents-domain-projects.yaml`.
- Skills and multi-step workflows: Workspace routes returned by Cockpit; their
  implementations are not copied into Documents.
- Execution and receipts: Runtime and the registered owner; no Runtime state is
  written back into Documents.
- Client projection: `CLAUDE.md` or `AGENTS.md`; it contains no copied identity,
  command matrix, skill inventory, workflow implementation, or checkout path.

This keeps each domain independently openable without creating 12 competing
runtime or capability authorities.

## Client Deployment

The accepted root is pinned at merge `aa43a79dfe6551d71081ee4a485943f5b0bb3519`
under `/Users/xiamingxing/.local/share/omostation/accepted`. The same accepted
`cockpit-mcp` command is registered for Codex, Claude Desktop, Zed, and ZCode.
The running Claude Desktop instance uses `deploymentMode=3p` and the separate
`~/Library/Application Support/Claude-3p` user-data directory, so the Cockpit
entry is present in both the standard and active third-party Desktop MCP config.
Claude's third-party model gateway remains separately owned by
`~/.claude/settings.json`; that file was byte-identical before and after both
MCP configuration changes. The active third-party Desktop config was also
backed up before modification and differs only by the new Cockpit server.

ChatGPT Web and Cowork do not consume the local Claude Desktop/Codex MCP
registration. They remain explicitly degraded until a reviewed remote
connector exists; this phase does not claim otherwise.

## Verification Evidence

- TDD RED: two new default-coverage cases failed because the checker silently
  skipped every gateway unless `--gateway-domain` was repeated manually.
- GREEN: no selector now means all project-registry domains; explicit selectors
  remain available for focused diagnosis.
- Reproducible focused root command:
  `uv run --with pytest --with pyyaml python -m pytest tests/test_documents_domain_project_check.py tests/test_documents_domain_owner_job.py -q`;
  24 gateway tests plus 3 owner-job tests passed before the selector regression
  was added. The final suite contains 25 gateway tests plus 3 owner-job tests.
- Live checker: `ok=true`, `domain_count=12`, `gateway_count=12`, zero errors.
- Projection inventory: 24 files, each below 80 lines.
- Identity preservation: all 12 live `DOMAIN.yaml` files are byte-identical to
  their pre-change backup.
- Accepted MCP protocol smoke: 12 calls, 12 correct domain IDs, 12 `binding=ok`,
  12 `profile=content-domain`, 12 `execution_policy=workspace_only`, zero
  failures.
- Combined SHA-256 over the ordered 24-file post-change projection inventory:
  `b154728e16dbaffad0b608c03c982750a3dd7b9c4dc195df1f7262af52ab858d`.
- Recovery backup: `/Users/xiamingxing/.local/state/omostation/backups/20260812T142000+0800-12-domain-gateways`
  contains 27 pre-change files with owner-only permissions.

## Retrospective

1. A registry that lists 12 domains is not proof that 12 gateways work. The old
   CLI default performed no gateway validation and could return a misleading
   green result. Default-all coverage removes that gap.
2. Client configuration and project instructions are different control planes.
   Installing one user-scoped MCP avoids duplicating its command and environment
   in every domain, while the domain-local projection restores only the domain
   ID.
3. Replacing non-Git Documents instructions needs an explicit recovery artifact.
   The backup was created before any batch write, and manifest immutability was
   checked afterwards.
4. Protocol-level smoke is stronger than checking config-file presence, but it
   is still not visual UI evidence. Desktop applications may need a restart
   before showing the newly registered server.

## Remaining Work

- Perform one visual open/reload smoke in the installed Claude Desktop, Zed, and
  ZCode clients after restart; do not turn that manual UX check into another
  domain authority.
- Replace the current generic skill/workflow pointer with a machine-verifiable
  Workspace capability discovery response so a client can select a relevant
  route without reading a copied Documents inventory.
- Continue migration-family consumer cutover and retirement evidence. The
  runtime/cache migration registry remains pending and this gateway rollout
  does not imply T8 completion.
- Design a reviewed remote connector before claiming ChatGPT Web or Cowork
  access to private local Documents content.
