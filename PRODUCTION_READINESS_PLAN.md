# SalonAI — Production Readiness Plan

Source of truth for hardening SalonAI Workforce Platform from "works in dev" to
"works in production." Phases are dependency-ordered — do not skip ahead.
Each task has a **Verify** step; a task isn't done until Verify passes.

Conventions for whoever (human or Claude Code) executes this:
- One task at a time. Implement → Verify → check the box → `git commit`
  referencing the task → move to next unchecked task in the **current phase only**.
- If a task requires a judgment call with real tradeoffs (flagged **DECISION**),
  stop and surface the tradeoff instead of guessing.
- Never mark a box done without running its Verify step.

---

## Phase 0 — Baseline Audit (read-only, no code changes)

- [ ] Run `pytest`, `flake8 .`, `black --check .`, `isort --check .` in `backend/`
      and `npm run lint && npm run type-check` in `frontend/`. Record every
      failure verbatim in `docs/baseline_audit.md` — this is the "before" snapshot.
      **Verify:** `docs/baseline_audit.md` exists and lists a pass/fail per check.
- [ ] Grep the whole backend for `datetime.now()` / `datetime.datetime.now()`
      **without** `timezone.utc`, especially outside `application/services/`.
      List every hit in the audit doc.
- [ ] Grep for any `asyncio.create_task`, `threading.Thread(`, `run_in_executor`,
      or APScheduler job registration. For each, note whether it propagates
      `current_user_role` / `current_user_id` / `current_tenant_id_var`
      (contextvars) into the spawned context. List every hit that does NOT.
- [ ] Grep `ai/tools/` and `api/routes/` for direct SQLAlchemy model imports
      that bypass `application/services/*` and `mcp/salon_mcp*.py`. List them.
- [ ] List every `*_workflow_v2` action that has zero negative-path tests
      (invalid UUID, past date, wrong role, missing param).

---

## Phase 1 — Correctness & Tenant Safety (highest priority — data integrity/security)

- [ ] **Contextvar leak fix.** For every async boundary found in Phase 0 (APScheduler
      jobs in `main.py`, `EventBus` subscriber callbacks, any `create_task`/`gather`),
      explicitly propagate `current_user_role`/`current_user_id`/`current_tenant_id_var`
      via `contextvars.copy_context()` before the work runs.
      **Verify:** new test that fires two simulated tenants' requests concurrently
      (e.g. `asyncio.gather` of two full orchestrator `.process()` calls with
      different `tenant_id`s) and asserts neither response/DB write leaks the
      other tenant's data.
- [ ] **DECISION — resolve the dead-agent-class ambiguity.** `ai/agents/*.py`
      Agent subclasses (`ReceptionistAgent`, `BIAgent`, etc.) are never
      instantiated in production; only their standalone module-level functions
      (`get_dashboard_summary`, etc.) are live. Pick one:
      (a) delete the unused `Agent` subclasses and their dedicated test files,
      keeping only the live standalone functions (move them somewhere obviously
      named, e.g. `ai/tools/analytics_helpers.py`), or
      (b) if `ReceptionistAgent.process()`'s deterministic state machine is
      actually more robust than the live inline-orchestrator booking flow,
      replace the inline flow with it.
      Do not leave both versions coexisting — surface this choice, don't guess.
      **Verify:** `grep -r "ReceptionistAgent\|BIAgent\|LeadFollowupAgent\|ReputationAgent\|StaffAssistantAgent\|UpsellAgent" backend/` shows either zero production references (option a) or exactly one call site in `orchestrator.py` (option b), and CLAUDE.md is updated to match.
- [ ] **Fail loud on DB fallback in prod.** `infrastructure/db/database.py` should
      raise and exit (not silently fall back to SQLite) when
      `ENVIRONMENT=production` and Supabase is unreachable.
      **Verify:** test that simulates prod env + unreachable DB and asserts
      startup fails with a clear error instead of booting on SQLite.
- [ ] **Datetime hardening.** Keep or collapse the 3-layer past-date check, but
      add a test matrix: DST transition dates, a salon in a different timezone
      than the server, midnight-boundary bookings. Add a pre-commit/CI grep
      that fails the build if a naive `datetime.now()` appears in
      `application/services/**`.
      **Verify:** new tests pass; CI grep step added and demonstrated failing
      on a deliberately-reintroduced naive call, then removed.
- [ ] **Replace the placeholder blocklist with a positive check.**
      `_PLACEHOLDER_VALUES` in the prompt-injection guard is a blocklist of
      known-bad strings. Replace/augment with a positive validator: every
      `*_id` param must be a syntactically valid UUID AND must resolve to a
      real row scoped to the caller's `tenant_id` before any handler runs.
      **Verify:** test with a well-formed-but-nonexistent UUID and with a
      UUID belonging to a different tenant — both must be rejected.

---

## Phase 2 — Resilience (behavior under real-world failure)

- [ ] **LLM provider fallback hardening.** In `core/llm_config.py` add timeouts,
      retry-with-backoff, and a circuit breaker (open after N consecutive
      Groq failures, cool down, retry) across the Groq → HuggingFace → Gemini
      chain. Emit a metric/log every time a fallback occurs — silent
      degradation to a weaker model shouldn't be invisible.
      **Verify:** test that simulates the primary provider failing and asserts
      (a) fallback is used, (b) a fallback event is logged/counted.
- [ ] **RAG missing-index visibility.** Replace the "warn-once" log for a
      missing FAISS index with a counter/metric, and add a startup
      health-check that reports which of the 5 domains (`POLICY_RAG`,
      `CUSTOMER_RAG`, `STAFF_RAG`, `LEAD_RAG`, `BUSINESS_RAG`) loaded.
      **Verify:** `/health` (see Phase 5) reports per-domain RAG status.
- [ ] **MCP rate limiter tenant scoping.** Confirm limits are per-tenant (not
      global) and configurable per role.
      **Verify:** test that a CUSTOMER hitting their rate limit doesn't affect
      a MANAGER's budget in the same tenant, or a CUSTOMER's budget in a
      different tenant.
- [ ] **Global exception handler.** Add a FastAPI exception handler returning a
      consistent error shape; assert no stack trace or raw DB error ever
      reaches the client when `ENVIRONMENT=production`.
      **Verify:** test that forces a DB exception and asserts the response
      body contains no traceback/internal detail in prod mode.

---

## Phase 3 — Observability

- [ ] **Request tracing.** Add a `request_id` in FastAPI middleware; propagate
      it through orchestrator → tools → MCP → `audit_log.py`; every log line
      includes `request_id` + `tenant_id` + `user_id`.
      **Verify:** grep a sample log output for a single request and confirm
      the same `request_id` appears at every layer.
- [ ] **Structured JSON logging** across backend (replace ad-hoc `print`/plain
      logs if any remain).
      **Verify:** log output is valid JSON per line.
- [ ] **Metrics.** Token usage & cost per tenant per agent, LLM latency,
      tool-call success/failure rate, MCP cache hit rate — surfaced via
      `mcp/metrics.py` and an aggregate endpoint (Prometheus-style `/metrics`
      or a simple query is fine for this scale).
      **Verify:** endpoint returns non-empty metrics after a test conversation.
- [ ] **Audit log is actually queryable.** Confirm an admin-only endpoint
      exists to read `audit_log` entries (who did what, when); add one if not.
      **Verify:** ADMIN role can query it; CUSTOMER/STAFF get 403.

---

## Phase 4 — Testing & CI

- [ ] **Finish the legacy-shim migration.** `tests/conftest.py` currently shims
      `agents.*`/`tools.*`/`services.*`/`rag.*` onto the real `ai.*`/
      `application.*`/`infrastructure.*` paths. Update the test files to import
      from the real paths directly, then delete the shim.
      **Verify:** full suite passes with the shim removed.
- [ ] **Add the concurrency/tenant-isolation suite** from Phase 1 as a
      permanent, always-run test file (not a one-off).
- [ ] **RBAC boundary matrix.** Add a parametrized test covering all 6 roles ×
      6 agents, asserting the CUSTOMER→booking/reputation/upsell,
      STAFF→+staff, MANAGER/OWNER/ADMIN→all matrix from CLAUDE.md is enforced
      exactly, not approximately.
- [ ] **CI pipeline** (GitHub Actions or equivalent): `black --check`,
      `isort --check`, `flake8`, `pytest --cov` with a coverage floor,
      frontend `lint` + `type-check` + `build`. Fails the build on any of these.
      **Verify:** pipeline runs on a test PR and fails when a check is broken
      on purpose, then passes when fixed.

---

## Phase 5 — Deployment Readiness

- [ ] **Containerize.** Dockerfile for backend, Dockerfile for frontend,
      `docker-compose.yml` for local parity with prod (the project is
      currently Windows-native only, which won't run on most cloud infra).
      **Verify:** `docker-compose up` boots both services and a request
      round-trips successfully.
- [ ] **Fail-fast startup config validation.** `main.py` lifespan should refuse
      to start (clear error message) if `SECRET_KEY`, `DATABASE_URL`, or *all*
      LLM provider keys are missing — instead of booting into a broken state.
      **Verify:** test that unsets required env vars and asserts startup
      raises with a readable message.
- [ ] **`/health` and `/ready` endpoints** — DB reachable, at least one LLM
      provider reachable, FAISS indices loaded (ties into Phase 2's RAG
      health check).
      **Verify:** endpoints return correct status under a simulated DB outage.
- [ ] **Alembic migration dry-run in CI** against a throwaway Postgres
      instance, so a broken migration is caught before merge.

---

## Phase 6 — Docs Cleanup

- [ ] Delete or clearly archive `backend/balu.md` (already known-stale per
      CLAUDE.md) and the unused `prisma/schema.prisma` files — remove the
      confusion rather than continuing to document around it.
- [ ] Re-generate the affected sections of `KETHAM_ARCHITECTURE.md` once
      Phase 1's dead-agent-class decision and datetime hardening land, so the
      doc matches the code again.
- [ ] Update `CLAUDE.md` to reflect anything changed above (contextvar
      propagation pattern, new health endpoints, CI pipeline).

---

## Definition of Done

All boxes checked, `docs/baseline_audit.md` re-run and diffed against the
Phase 0 snapshot with zero new failures, and CI green on a fresh clone.