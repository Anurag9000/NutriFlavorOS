# NutriFlavorOS Engineering and Research Roadmap

**Roadmap date:** 2026-08-03  
**Execution rule:** implement directly on `main` in coherent commits; keep code, tests, migrations, contracts, frontend clients, CI, and documentation synchronized; never rewrite history.  
**Current migration head:** `20260802_0018`  
**Current API:** `0.15.4`  
**Current OpenAPI contract:** `2026-08-03.2`

Current catalog boundary: 37 task contracts, 30 dataset families, 75 model or algorithm families, 29 experiment contracts, and 39 feature contracts.

A class, endpoint, fixture, configured workflow, or catalog row is not completion or executed evidence by itself.

## Completed architecture milestones

### C1 — Transactional household platform

Authentication, explicit profile completion, household roles, hashed invitations, transactional pantry/leftovers, reservations, optimistic versions, exact idempotency, and PostgreSQL race probes.

### C2 — Quantity-aware meal planning

Deterministic horizon planning, hard restrictions, household target aggregation, pantry-aware objectives, persisted plans, shopping reconciliation, reservations, batch grouping, Pareto, optional CP-SAT/MILP, robust scenarios, and exact comparators.

### C3 — Human-reviewed plan lifecycle

Draft/approved/cancelled states, owner approval, editor/owner cancellation, append-only events, stale-version and contradictory-key rejection, reservation release, dependent schedule invalidation, protected review, and exact approved source-plan references.

### C4 — Reviewed preparation operations

Immutable resource calendars, complete occurrence/profile/request/response provenance, deterministic replay, schedule hashes, lifecycle states, protected final review, append-only schedule events, and user-confirmed task execution.

### C5 — Minimal-change preparation repair

Deterministic greedy repair, bounded exact comparator, immutable anchors, predecessor closure, capacity/window/deadline validation, structured conflicts, outcome partitions, hashes, authenticated API, offline CLI, and advisory non-persistence.

### C6 — Repair proposal and accepted-draft lifecycle

Immutable server-recomputed proposals, exact changed-task acknowledgements, one-new-draft-only acceptance, source immutability, separate method-aware owner approval, tamper/staleness checks, and append-only proposal/schedule evidence.

The **one-replacement-per-source invariant is implemented** through migration `20260802_0018`.

### C7 — Derivation and execution authority

**Schedule derivation evidence is implemented** through per-schedule and household-coverage endpoints plus a protected inspector.

**Task-execution eligibility is implemented** through a viewer-authorized endpoint and proactive frontend gate. Replaced sources remain readable but cannot receive new task events or completion.

### C8 — Proposal invalidation authority and administration

**Owner-only proposal invalidation is implemented** through an authenticated API, strict request contract, append-only event, server-observed stale reasons, exact idempotency, optimistic versioning, typed frontend client, protected owner workspace, editor/viewer read-only behavior, static contracts, Vitest coverage, and real PostgreSQL terminal-outcome races.

Invalidation cannot accept, persist, approve, execute, complete, or mutate a source schedule. It permanently closes only a `proposed` review record.

### C9 — Lowest-layer schedule completion authority

**Lowest-layer task terminality** is implemented in the exported `transition_schedule` service. Direct completion requires terminal deterministic task evidence, existing error precedence is preserved, lower-level bypass is statically forbidden, and a real PostgreSQL race proves completion cannot commit ahead of the final task event.

### C10 — PostgreSQL lifecycle, migration, and transient-failure evidence

Configured real-database evidence includes:

- acceptance versus rejection, invalidation, source execution, plan cancellation, calendar supersession, and owner approval;
- final task completion versus schedule completion;
- discarded committed-response exact retry for acceptance, invalidation, and completion;
- populated `0017 → 0018` migration rehearsal with 64 production-service acceptances, exact identity/hash preservation, catalog verification, and lower-level bypass rollback;
- `statement_timeout` SQLSTATE `57014` recovery;
- genuine SQLSTATE `40P01` deadlock recovery;
- real **post-commit connection-loss recovery** after `pg_terminate_backend()` terminates the service backend between commit and response materialization;
- real **checked-out pool connection recovery** after a worker backend is terminated before mutation: SQLAlchemy marks `connection_invalidated=true`, the conservative response reports `retry_safe=false`, independent evidence proves zero mutation, a fresh backend PID succeeds, and exact retry returns the same accepted lifecycle;
- an explicit public distinction between `retryable` recovery action and `retry_safe` proof strength;
- `automatic_retry_performed=false` so the server never conceals duplicate or unknown outcomes.

Configured workflows retain JUnit and migration JSON evidence. None is represented as hosted green evidence until the exact current runs and artifacts are observed.

### C11 — Read-only support evidence export

A viewer-authorized and operator-CLI preparation schedule support export is implemented.

- Captures schedule provenance, lifecycle events, derivation, task-execution eligibility, deterministic task history, related proposals, acceptances, and proposal events.
- PostgreSQL uses a dedicated `REPEATABLE READ`, `SET TRANSACTION READ ONLY` snapshot and records `txid_current_snapshot()`.
- Canonical SHA-256 binds domain evidence and explicit non-claims while excluding transaction metadata.
- The request session enforces viewer access and `404` non-disclosure; PostgreSQL repeats viewer authorization inside the exact export snapshot.
- The authenticated user ID is server-derived, while the operator CLI remains a separate privileged path.
- The protected browser requires explicit generation, clears stale scope, restores focus, and downloads complete hash-addressed JSON without browser storage.
- SQLite/API regressions prove owner success, nonmember `404`, operator separation, complete evidence chains, and no mutation.
- A real PostgreSQL acceptance race proves snapshot consistency across concurrent lifecycle mutation.

## P0 — Observe and repair exact hosted verification

1. Inspect exact latest `main` runs for SQLite, PostgreSQL, backend, frontend, OpenAPI, container, and focused repair workflows.
2. Inspect benchmark, JUnit, migration, and build artifacts.
3. Record exact commit SHA, run IDs, artifact IDs, durations, and failures.
4. Repair every failure without deleting, skipping, xfail-ing, weakening, or narrowing requirements.
5. Re-run failed jobs and verify the exact replacement run.
6. Do not report green until the exact current commit and artifacts are observed.

## P0 — Finish PostgreSQL operational recovery evidence

Remaining real-database work:

- connection loss while COMMIT acknowledgement itself is in flight, where neither client nor response can safely establish the outcome;
- PostgreSQL primary loss, replica promotion, DNS/service-discovery changes, and multi-node failover;
- sustained pool exhaustion, pool timeout, recycle/lifetime behavior, process restart, and recovery under concurrent load;
- repeated serialization failures and a bounded, observable client retry policy;
- production-snapshot or production-scale migration rehearsal beyond the 64-lifecycle synthetic corpus;
- SQLSTATE, retry, ambiguous-outcome, pool, and lock-wait metrics and alerts.

Each probe must retain proposal, acceptance, schedule, event, version, hash, SQLSTATE, structured error, and retry identity evidence. The HTTP exception boundary must never perform automatic mutation retries.

## P0 — Complete authenticated browser and accessibility evidence

PostgreSQL-backed Playwright must cover signup/login/profile completion, household roles, plan review/approval/cancellation, occurrence confirmation, reviewed calendars, schedule persistence/approval, task execution/completion, advisory repair, proposal creation, acceptance, invalidation, method-aware approval, replacement eligibility, support-export download, stale versions, tamper, and `404` non-disclosure.

Accessibility evidence must include axe, keyboard-only operation, focus restoration, error summaries, live regions, labels, table semantics, reduced motion, zoom/reflow, and contrast.

## P0 — Harden support evidence packaging

The read-only snapshot, authorization boundary, viewer endpoint, CLI, and protected download workspace are implemented. Remaining:

- configurable field-level redaction and least-privilege support roles;
- signed/encrypted packages and independent verification tooling;
- secure object storage, retention, revocation, and deletion policies;
- support-case linkage and download audit events;
- pagination, streaming, and size limits for large histories;
- household-level multi-schedule bundles;
- production load, memory, and latency evidence.

## P1 — Execution-aware repair

A future engine must treat task events as immutable facts, preserve completed/skipped states and confirmed starts, prohibit moving executed work, distinguish historical actual work from remaining planned work, preserve dependency chronology, model in-progress/passive/supervision states, replan only remaining work, retain event identities, create a new draft without rewriting source history, expose structured infeasibility, and race execution onset against computation/proposal/acceptance/approval.

## P1 — Joint meal, inventory, shopping, and preparation repair

Jointly repair meals, servings, pantry allocations, reservations, shopping, leftovers, and tasks; preserve approved-plan/source history; release old reservations and create replacements only after explicit acceptance; add minimum-change objectives across meals, quantities, lots, purchases, and starts; and add partial repair with precise conflicts and exact/relaxed lower bounds.

## P1/P2 — Scheduling and optimization frontier

Optional interval-variable CP-SAT, MILP relaxation and infeasibility diagnosis, min-cost flow, LNS, conflict-targeted ruin-and-recreate, logic-based Benders, robust/stochastic durations/attendance/demand/prices, chance constraints, epsilon-constraint Pareto frontiers, unsat cores, and representative latency/memory/gap/failure reports.

## P2 — Evidence, inventory, forecasting, and personalization

Expand reviewed evidence and multilingual normalization; add receipt/barcode ingestion, lot split/merge, recall/quarantine, offline reconciliation, substitutions and packs/prices; add classical/neural forecasting with calibration and drift/OOD detection; and add retrieval, sequential, graph, and constrained reranking models only through explicit evaluation and rollback gates.

## P2 — Security, privacy, operations, and release engineering

Verified email/password reset, MFA, token rotation/revocation, rate limiting, ownership recovery, archive/delete/export, audit retention, secret rotation, backup/PITR, PostgreSQL pooling/failover, logs/metrics/traces/SLOs, SBOM/scans, signed artifacts, canary/kill switches, incident response, rollback, and postmortems.

## P3 — High-risk blocked areas

Clinical nutrition, medication decisions, allergy-safety guarantees, microbial/contamination conclusions, autonomous appliance control, autonomous procurement/payment, food-safety certification, and verified sustainability claims remain disabled without specialist review, qualified data, consent, instrumentation, monitoring, rollback, and jurisdictional analysis.

## Non-negotiable release rules

- No clinical, allergy, medication, contamination, temperature, or food-safety claim without qualified evidence and review.
- No task execution, presence, appliance, or sensor inference from plans, schedules, or user-entered events.
- Advisory computation never reports acceptance or persistence.
- Proposal creation never creates a schedule.
- Proposal acceptance creates only one new draft and never implies approval, execution, or completion.
- Proposal invalidation creates no schedule and permanently prevents later acceptance.
- Repair-derived approval requires exact acceptance evidence and method-aware replay.
- Replaced sources remain readable but cannot receive new execution events.
- Every new completion transition requires explicit terminal task evidence at the lowest exported authority.
- Support export is read-only, hash-addressed, snapshot-authorized, and never upgrades user-entered evidence into execution or safety verification.
- Retryable or ambiguous database failures never trigger automatic server-side mutation retry; exact clients repeat the same idempotency key.
- `retry_safe=true` is reserved for proven transaction aborts; connection ambiguity remains `retry_safe=false`.
- Frontend preflight never replaces server authority.
- No global-optimality or model-readiness claim from greedy/truncated search, catalog registration, importability, or synthetic tests.
- No green-build claim until exact hosted workflows and artifacts are observed.
- No force push, history rewrite, feature branch, or feature PR.
