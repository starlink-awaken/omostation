// --- Jobs (Minions) ---
import type { Operation, OperationContext, ErrorCode } from "../operations-types";
import { OperationError } from "../operations-types";
import { clampSearchLimit } from "../engine";
import type { BrainEngine } from "../engine";

export const submit_job: Operation = {
  name: 'submit_job',
  description: 'Submit a background job to the Minions queue. Built-in types: sync, embed, lint, import, extract, backlinks, autopilot-cycle. The `shell` type is CLI-only and rejected over MCP.',
  params: {
    name: { type: 'string', required: true, description: 'Job type (sync, embed, lint, import, extract, backlinks, autopilot-cycle; shell is CLI-only)' },
    data: { type: 'object', description: 'Job payload (JSON)' },
    queue: { type: 'string', description: 'Queue name (default: "default")' },
    priority: { type: 'number', description: 'Priority (0 = highest, default: 0)' },
    max_attempts: { type: 'number', description: 'Max retry attempts (default: 3)' },
    delay: { type: 'number', description: 'Delay in ms before eligible' },
    timeout_ms: { type: 'number', description: 'Per-job wall-clock timeout in ms; aborted job goes to dead' },
  },
  mutating: true,
  scope: 'admin',
  handler: async (ctx, p) => {
    const name = typeof p.name === 'string' ? p.name.trim() : '';
    if (ctx.dryRun) return { dry_run: true, action: 'submit_job', name };

    // Submit-side MCP guard: reject protected job names from untrusted callers
    // BEFORE we touch the DB. This is the first of the two security layers
    // (the second is MinionQueue.add's check). Independent of the worker-side
    // GBRAIN_ALLOW_SHELL_JOBS env flag — even if that flag is on, MCP callers
    // cannot submit protected-type jobs.
    const { isProtectedJobName } = await import('../minions/protected-names.ts');
    // F7b fail-closed: anything that is not strictly false (i.e., remote=true OR
    // the field somehow leaks in undefined despite the required type) rejects
    // protected job submissions. Closes the HTTP MCP shell-job RCE that surfaced
    // when the HTTP transport's OperationContext literal forgot to set remote.
    if (ctx.remote !== false && isProtectedJobName(name)) {
      throw new OperationError('permission_denied', `'${name}' jobs cannot be submitted over MCP (CLI-only for security)`);
    }

    const { MinionQueue } = await import('../minions/queue.ts');
    const queue = new MinionQueue(ctx.engine);
    // Trusted flag fires ONLY for an explicit local CLI submission of a protected
    // name. Strict `=== false` so an untyped/cast context can't escalate.
    const trusted = ctx.remote === false && isProtectedJobName(name) ? { allowProtectedSubmit: true } : undefined;

    const jobData = (p.data as Record<string, unknown>) || {};

    // v0.35.8.0: pre-enqueue shell-job validation, parity with the CLI submit
    // path. Closes the bug class where shell.ts handler-time validation ran
    // AFTER queue.add() persisted the row (codex F-CDX-1). Note: this branch
    // only fires for trusted local submitters (`ctx.remote === false` AND
    // protected-name allowlist), so remote MCP callers never reach it — but
    // it stays here as defense-in-depth in case a future code path widens
    // the trust gate above.
    if (name === 'shell' && trusted) {
      const { validateShellJobParams } = await import('../minions/handlers/shell-validate.ts');
      validateShellJobParams(jobData);
    }

    const job = await queue.add(name, jobData, {
      queue: (p.queue as string) || 'default',
      priority: (p.priority as number) || 0,
      max_attempts: (p.max_attempts as number) || 3,
      delay: (p.delay as number) || undefined,
      timeout_ms: (p.timeout_ms as number) || undefined,
    }, trusted);

    // v0.35.8.0: submit_job audit-log parity with the CLI path (codex F-CDX-4).
    // Pre-v0.35.8.0 the op handler bypassed the shell-audit JSONL writer
    // entirely. Lift the call here so both submit surfaces produce one
    // operational-trace line per shell submission. Best-effort; audit
    // failures never block submission.
    if (name === 'shell' && trusted) {
      try {
        const { logShellSubmission } = await import('../minions/handlers/shell-audit.ts');
        const inheritNames = Array.isArray(jobData.inherit)
          ? (jobData.inherit as unknown[]).filter((s): s is string => typeof s === 'string')
          : undefined;
        logShellSubmission({
          caller: 'mcp',
          // Gated on `trusted` (which requires ctx.remote === false), so
          // we know this path is a local trusted submitter — log it that way.
          remote: false,
          job_id: job.id,
          cwd: typeof jobData.cwd === 'string' ? jobData.cwd : '',
          cmd_display: typeof jobData.cmd === 'string' ? (jobData.cmd as string).slice(0, 80) : undefined,
          argv_display: Array.isArray(jobData.argv)
            ? (jobData.argv as unknown[]).filter((a): a is string => typeof a === 'string').map((a) => a.slice(0, 80))
            : undefined,
          inherit: inheritNames && inheritNames.length > 0 ? inheritNames : undefined,
        });
      } catch { /* audit failures never block submission */ }
    }

    return job;
  },
};

// v0.38 Slice 3 — D13 — remote-callable submit_agent with registration-time
// binding enforcement. Distinct from `submit_job` because:
//   1. It's the FIRST op that lets remote MCP callers spawn paid LLM work
//      (cost concerns + audit trail differ from generic submit_job).
//   2. The trust boundary lives in oauth_clients.bound_* fields, not in the
//      protected-name guard. Bindings are enforced PER-OP, not per-name.
//   3. The dispatcher is the subagent handler with the gateway-native loop
//      (agent.use_gateway_loop is auto-on for submit_agent jobs).
export const submit_agent: Operation = {
  name: 'submit_agent',
  description: 'Submit an LLM agent job that the worker dispatches via the gateway-native tool loop. Requires the `agent` OAuth scope. Tools, source, slug prefixes, max concurrency, and daily budget are bound at OAuth client registration time.',
  params: {
    prompt: { type: 'string', required: true, description: 'User prompt for the agent' },
    model: { type: 'string', description: 'provider:model string (defaults to models.tier.subagent)' },
    allowed_tools: { type: 'array', description: 'Subset of bound_tools the agent may invoke', items: { type: 'string' } },
    allowed_slug_prefixes: { type: 'array', description: 'Subset of bound_slug_prefixes for put_page writes', items: { type: 'string' } },
    max_turns: { type: 'number', description: 'Max LLM turns (default 20, hard cap 100)' },
    queue: { type: 'string', description: 'Queue name (default "default")' },
  },
  mutating: true,
  scope: 'agent' as any,
  handler: async (ctx, p) => {
    // Remote-callable but only when the OAuth client has scope=agent AND
    // a binding row. Local CLI callers (ctx.remote === false) skip the
    // binding check — `gbrain agent run` already runs through subagent.ts
    // directly without going through this op.
    if (ctx.remote === false) {
      throw new OperationError('invalid_request', 'submit_agent over the local CLI: use `gbrain agent run` instead.');
    }

    const clientId = (ctx as { auth?: { clientId?: string } }).auth?.clientId;
    if (!clientId || typeof clientId !== 'string') {
      throw new OperationError('permission_denied', 'submit_agent requires an OAuth client with the `agent` scope.');
    }

    // Load the binding row.
    const { sqlQueryForEngine } = await import('../sql-query.ts');
    const sql = sqlQueryForEngine(ctx.engine);
    let bindingRows: Array<Record<string, unknown>>;
    try {
      bindingRows = await sql`
        SELECT bound_tools, bound_source_id, bound_brain_id, bound_slug_prefixes,
               bound_max_concurrent, budget_usd_per_day::text AS budget_cap
          FROM oauth_clients
         WHERE client_id = ${clientId}
      `;
    } catch (err) {
      throw new OperationError(
        'internal',
        `submit_agent: could not load OAuth client binding: ${err instanceof Error ? err.message : String(err)}`,
      );
    }
    if (bindingRows.length === 0) {
      throw new OperationError('permission_denied', `submit_agent: client_id ${clientId} not found.`);
    }
    const binding = bindingRows[0];
    const boundTools = (binding.bound_tools as string[] | null) ?? null;
    const boundSource = (binding.bound_source_id as string | null) ?? null;
    const boundSlugPrefixes = (binding.bound_slug_prefixes as string[] | null) ?? null;
    const boundMaxConcurrent = Number(binding.bound_max_concurrent ?? 1);
    const budgetCapText = (binding.budget_cap as string | null) ?? null;

    if (boundTools === null) {
      throw new OperationError(
        'permission_denied',
        `submit_agent: client ${clientId} has the agent scope but no bindings. Re-register with --bound-tools, --bound-source, --bound-slug-prefixes, --bound-max-concurrent, --budget-usd-per-day.`,
      );
    }

    // Validate each param against the binding.
    const requestedTools = (p.allowed_tools as string[] | undefined) ?? boundTools;
    for (const t of requestedTools) {
      if (!boundTools.includes(t)) {
        throw new OperationError(
          'permission_denied',
          `submit_agent: tool "${t}" is not in client ${clientId}'s bound_tools (${boundTools.join(', ')}).`,
        );
      }
    }
    const requestedSlugPrefixes = (p.allowed_slug_prefixes as string[] | undefined) ?? boundSlugPrefixes ?? [];
    if (boundSlugPrefixes !== null) {
      for (const sp of requestedSlugPrefixes) {
        if (!boundSlugPrefixes.some(bp => sp.startsWith(bp) || bp === sp)) {
          throw new OperationError(
            'permission_denied',
            `submit_agent: slug_prefix "${sp}" is not under any of client ${clientId}'s bound_slug_prefixes.`,
          );
        }
      }
    }

    // Concurrency cap: count active+waiting agent jobs for this client.
    const inflight = await sql`
      SELECT COUNT(*)::int AS n
        FROM minion_jobs j
       WHERE j.name = 'subagent'
         AND j.status IN ('waiting', 'active', 'waiting-children')
         AND j.data->>'__owner_client_id' = ${clientId}
    `;
    const inflightCount = Number((inflight[0]?.n as number | string | undefined) ?? 0);
    if (inflightCount >= boundMaxConcurrent) {
      throw new OperationError(
        'rate_limited',
        `submit_agent: client ${clientId} at concurrency cap (${inflightCount}/${boundMaxConcurrent}).`,
      );
    }

    // Dry-run echo.
    if (ctx.dryRun) {
      return {
        dry_run: true,
        action: 'submit_agent',
        client_id: clientId,
        bound_tools: boundTools,
        bound_source: boundSource,
        bound_max_concurrent: boundMaxConcurrent,
      };
    }

    // Submit via MinionQueue with allowProtectedSubmit (the agent op is
    // remote-callable but the underlying job name 'subagent' is protected;
    // the OAuth scope check above stands in for the protected-name guard).
    const { MinionQueue } = await import('../minions/queue.ts');
    const queue = new MinionQueue(ctx.engine);

    const jobData: Record<string, unknown> = {
      prompt: p.prompt as string,
      max_turns: Math.min((p.max_turns as number) ?? 20, 100),
      allowed_tools: requestedTools,
      allowed_slug_prefixes: requestedSlugPrefixes,
      __owner_client_id: clientId,
    };
    if (typeof p.model === 'string') jobData.model = p.model;
    if (boundSource) jobData.source_id = boundSource;
    const job = await queue.add(
      'subagent',
      jobData,
      { queue: (p.queue as string) || 'default' },
      { allowProtectedSubmit: true },
    );

    // Audit trail (D4) — best-effort JSONL.
    try {
      const { logAgentSubmission } = await import('../minions/agent-audit.ts');
      const budgetCapCents = budgetCapText ? Math.round(parseFloat(budgetCapText) * 100) : null;
      const promptText = typeof p.prompt === 'string' ? p.prompt : '';
      logAgentSubmission({
        client_id: clientId,
        job_id: job.id,
        model: typeof p.model === 'string' ? p.model : '<default>',
        bound_tools: requestedTools,
        bound_source: boundSource,
        slug_prefixes: requestedSlugPrefixes,
        max_concurrent: boundMaxConcurrent,
        budget_remaining_cents: budgetCapCents,
        prompt_byte_count: Buffer.byteLength(promptText, 'utf8'),
        outcome: 'submitted',
      });
    } catch { /* never block submission */ }

    return { id: job.id, name: 'subagent', client_id: clientId };
  },
};

export const get_job: Operation = {
  name: 'get_job',
  description: 'Get job status and details by ID',
  params: {
    id: { type: 'number', required: true, description: 'Job ID' },
  },
  scope: 'admin',
  handler: async (ctx, p) => {
    const { MinionQueue } = await import('../minions/queue.ts');
    const queue = new MinionQueue(ctx.engine);
    const job = await queue.getJob(p.id as number);
    if (!job) throw new OperationError('invalid_params', `Job not found: ${p.id}`);
    return job;
  },
};

export const list_jobs: Operation = {
  name: 'list_jobs',
  description: 'List jobs with optional filters',
  params: {
    status: { type: 'string', description: 'Filter by status (waiting, active, completed, failed, delayed, dead, cancelled)' },
    queue: { type: 'string', description: 'Filter by queue name' },
    name: { type: 'string', description: 'Filter by job type' },
    limit: { type: 'number', description: 'Max results (default: 50)' },
  },
  scope: 'admin',
  handler: async (ctx, p) => {
    const { MinionQueue } = await import('../minions/queue.ts');
    const queue = new MinionQueue(ctx.engine);
    return queue.getJobs({
      status: p.status as string | undefined,
      queue: p.queue as string | undefined,
      name: p.name as string | undefined,
      limit: (p.limit as number) || 50,
    } as Parameters<typeof queue.getJobs>[0]);
  },
};

export const cancel_job: Operation = {
  name: 'cancel_job',
  description: 'Cancel a waiting, active, or delayed job',
  params: {
    id: { type: 'number', required: true, description: 'Job ID' },
  },
  mutating: true,
  scope: 'admin',
  handler: async (ctx, p) => {
    if (ctx.dryRun) return { dry_run: true, action: 'cancel_job', id: p.id };
    const { MinionQueue } = await import('../minions/queue.ts');
    const queue = new MinionQueue(ctx.engine);
    const cancelled = await queue.cancelJob(p.id as number);
    if (!cancelled) throw new OperationError('invalid_params', `Cannot cancel job ${p.id} (may already be in terminal status)`);
    return cancelled;
  },
};

export const retry_job: Operation = {
  name: 'retry_job',
  description: 'Re-queue a failed or dead job for retry',
  params: {
    id: { type: 'number', required: true, description: 'Job ID' },
  },
  mutating: true,
  scope: 'admin',
  handler: async (ctx, p) => {
    if (ctx.dryRun) return { dry_run: true, action: 'retry_job', id: p.id };
    const { MinionQueue } = await import('../minions/queue.ts');
    const queue = new MinionQueue(ctx.engine);
    const retried = await queue.retryJob(p.id as number);
    if (!retried) throw new OperationError('invalid_params', `Cannot retry job ${p.id} (must be failed or dead)`);
    return retried;
  },
};

export const get_job_progress: Operation = {
  name: 'get_job_progress',
  description: 'Get structured progress for a running job',
  params: {
    id: { type: 'number', required: true, description: 'Job ID' },
  },
  scope: 'admin',
  handler: async (ctx, p) => {
    const { MinionQueue } = await import('../minions/queue.ts');
    const queue = new MinionQueue(ctx.engine);
    const job = await queue.getJob(p.id as number);
    if (!job) throw new OperationError('invalid_params', `Job not found: ${p.id}`);
    return { id: job.id, name: job.name, status: job.status, progress: job.progress };
  },
};

export const pause_job: Operation = {
  name: 'pause_job',
  description: 'Pause a waiting, active, or delayed job',
  params: {
    id: { type: 'number', required: true, description: 'Job ID' },
  },
  scope: 'admin',
  handler: async (ctx, p) => {
    const { MinionQueue } = await import('../minions/queue.ts');
    const queue = new MinionQueue(ctx.engine);
    const job = await queue.pauseJob(p.id as number);
    if (!job) throw new OperationError('invalid_params', `Job not found or not pausable: ${p.id}`);
    return { id: job.id, status: job.status };
  },
};

export const resume_job: Operation = {
  name: 'resume_job',
  description: 'Resume a paused job back to waiting',
  params: {
    id: { type: 'number', required: true, description: 'Job ID' },
  },
  scope: 'admin',
  handler: async (ctx, p) => {
    const { MinionQueue } = await import('../minions/queue.ts');
    const queue = new MinionQueue(ctx.engine);
    const job = await queue.resumeJob(p.id as number);
    if (!job) throw new OperationError('invalid_params', `Job not found or not paused: ${p.id}`);
    return { id: job.id, status: job.status };
  },
};

export const replay_job: Operation = {
  name: 'replay_job',
  description: 'Replay a completed/failed/dead job, optionally with modified data',
  params: {
    id: { type: 'number', required: true, description: 'Source job ID to replay' },
    data_overrides: { type: 'object', required: false, description: 'Data fields to override (merged with original)' },
  },
  scope: 'admin',
  handler: async (ctx, p) => {
    if (ctx.dryRun) return { dry_run: true, action: 'replay_job', id: p.id };
    const { MinionQueue } = await import('../minions/queue.ts');
    const queue = new MinionQueue(ctx.engine);
    const job = await queue.replayJob(p.id as number, p.data_overrides as Record<string, unknown> | undefined);
    if (!job) throw new OperationError('invalid_params', `Job not found or not in terminal state: ${p.id}`);
    return { id: job.id, name: job.name, status: job.status, source_id: p.id };
  },
};

export const send_job_message: Operation = {
  name: 'send_job_message',
  description: 'Send a sidechannel message to a running job\'s inbox',
  params: {
    id: { type: 'number', required: true, description: 'Job ID to message' },
    payload: { type: 'object', required: true, description: 'Message payload (arbitrary JSON)' },
    sender: { type: 'string', required: false, description: 'Sender identity (default: admin)' },
  },
  scope: 'admin',
  handler: async (ctx, p) => {
    if (ctx.dryRun) return { dry_run: true, action: 'send_job_message', id: p.id };
    const { MinionQueue } = await import('../minions/queue.ts');
    const queue = new MinionQueue(ctx.engine);
    const msg = await queue.sendMessage(p.id as number, p.payload, (p.sender as string) ?? 'admin');
    if (!msg) throw new OperationError('invalid_params', `Job not found, not messageable, or sender unauthorized: ${p.id}`);
    return { sent: true, message_id: msg.id, job_id: p.id };
  },
};

